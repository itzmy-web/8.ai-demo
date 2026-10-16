"""合同审查引擎（移植自 D:/审批合同 backend/review.py）。

流程：规则引擎 → [可选]LLM 语义研判 → [可选]LLM 条款推荐 → 风险汇总。
未配置 LLM 时全程规则驱动，开箱即跑。
"""
from __future__ import annotations

import json
import re

from core import db, llm
from . import rules as rule_engine

MAX_LLM_RISKS = 20
SNIPPET_LIMIT = 120

VERDICT = {"high": "建议拒绝/重大整改", "medium": "需整改后通过", "low": "原则通过", "none": "通过"}


async def _llm_semantic_async(text: str) -> list[rule_engine.Risk]:
    if not llm.enabled():
        return []
    prompt = (
        "你是企业法务 AI。请审查以下合同，识别法律合规与商业风险，"
        '仅输出 JSON 数组，每项含：title/clause_type/level(high|medium|low)/'
        "reason/legal_basis/suggestion/locate（locate 填合同原文中出现过的、用于定位的短句，"
        "找不到可填空字符串）。\n" + text[:6000]
    )
    try:
        items = await llm.chat_json([{"role": "user", "content": prompt}])
    except Exception:  # noqa: BLE001
        return []
    if not isinstance(items, list):
        return []
    out: list[rule_engine.Risk] = []
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            continue
        lvl = it.get("level", "medium")
        if lvl not in rules_levels:
            lvl = "medium"
        out.append(rule_engine.Risk(
            risk_id=f"llm-{i:03d}", title=it.get("title", "大模型识别风险"),
            clause_type=it.get("clause_type", "其他条款"), level=lvl,
            reason=it.get("reason", ""), legal_basis=it.get("legal_basis", ""),
            snippet=it.get("locate", "") or "（大模型语义研判）",
            suggestion=it.get("suggestion", ""), by_llm=True,
        ))
    return out


rules_levels = {"high", "medium", "low"}


async def _llm_recommend(risks: list[rule_engine.Risk]) -> int:
    if not llm.enabled() or not risks:
        return 0
    batch = risks[:MAX_LLM_RISKS]
    payload = [
        {"index": i, "title": r.title, "clause_type": r.clause_type,
         "level": r.level, "reason": r.reason[:SNIPPET_LIMIT],
         "原文": (r.snippet or "")[:SNIPPET_LIMIT]}
        for i, r in enumerate(batch)
    ]
    prompt = (
        "你是企业法务 AI。下面是一份合同的风险清单。请为每条风险给出可直接采用的中文示范条款，"
        "要求具体、可落地（1-2 句，含明确的数字/比例/期限等）。\n"
        '只输出 JSON：{"suggestions":[{"index":<与输入一致的整数>,"suggestion":"<示范条款文本>"}]}\n\n'
        "风险清单：\n" + json.dumps(payload, ensure_ascii=False)
    )
    try:
        data = await llm.chat_json(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
        )
    except Exception:  # noqa: BLE001
        return 0
    if not isinstance(data, dict):
        return 0
    changed = 0
    for it in data.get("suggestions", []):
        try:
            idx = int(it.get("index"))
        except (TypeError, ValueError):
            continue
        sug = (it.get("suggestion") or "").strip()
        if 0 <= idx < len(batch) and sug:
            batch[idx].suggestion = sug
            batch[idx].by_llm = True
            changed += 1
    return changed


def build_summary(risks: list[rule_engine.Risk], level: str) -> str:
    highs = [r for r in risks if r.level == "high"]
    meds = [r for r in risks if r.level == "medium"]
    lows = [r for r in risks if r.level == "low"]
    parts = [
        f"综合风险等级：{level}（{VERDICT.get(level, '通过')}）。",
        f"共识别风险 {len(risks)} 项：高风险 {len(highs)}、中风险 {len(meds)}、低风险 {len(lows)}。",
    ]
    if highs:
        parts.append("高风险要点：" + "；".join(r.title for r in highs[:5]) + "。")
    if not risks:
        parts.append("未发现规则库命中项，合同条款完整度良好。")
    return "".join(parts)


async def review_contract(name: str, text: str, biz_type: str, applicant: str) -> dict:
    risks = rule_engine.evaluate(text, biz_type)
    risks += await _llm_semantic_async(text)
    await _llm_recommend(risks)
    level = rule_engine.overall_level(risks)
    summary = build_summary(risks, level)
    contract_id = db.execute(
        "INSERT INTO contracts(name, biz_type, text, applicant, risk_level, summary, status)"
        " VALUES (?,?,?,?,?,?, 'pending')",
        (name, biz_type, text, applicant, level, summary),
    )
    for r in risks:
        db.execute(
            "INSERT INTO contract_risks(contract_id, risk_id, title, clause_type, level,"
            " reason, legal_basis, snippet, suggestion, by_llm) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (contract_id, r.risk_id, r.title, r.clause_type, r.level,
             r.reason, r.legal_basis, r.snippet, r.suggestion, int(r.by_llm)),
        )
    db.audit(applicant, "applicant", "提交审查", name, f"风险等级 {level}，{len(risks)} 项")
    return get_contract(contract_id)


def get_contract(contract_id: int) -> dict | None:
    c = db.query_one("SELECT * FROM contracts WHERE id=?", (contract_id,))
    if not c:
        return None
    c["risks"] = db.query_all(
        "SELECT * FROM contract_risks WHERE contract_id=? ORDER BY id", (contract_id,)
    )
    c["approvals"] = db.query_all(
        "SELECT * FROM approvals WHERE contract_id=? ORDER BY id", (contract_id,)
    )
    return c


def list_contracts(status: str = "") -> list[dict]:
    if status:
        return db.query_all(
            "SELECT id, name, biz_type, applicant, risk_level, status, created_at"
            " FROM contracts WHERE status=? ORDER BY id DESC", (status,)
        )
    return db.query_all(
        "SELECT id, name, biz_type, applicant, risk_level, status, created_at"
        " FROM contracts ORDER BY id DESC"
    )


def decide(contract_id: int, action: str, operator: str, role: str, comment: str = "") -> dict:
    """审批决策：approve / reject / rectify。"""
    status_map = {"approve": "approved", "reject": "rejected", "rectify": "rectifying"}
    new_status = status_map.get(action, "pending")
    db.execute("UPDATE contracts SET status=? WHERE id=?", (new_status, contract_id))
    db.execute(
        "INSERT INTO approvals(contract_id, action, operator, role, comment) VALUES (?,?,?,?,?)",
        (contract_id, action, operator, role, comment),
    )
    db.audit(operator, role, f"审批-{action}", str(contract_id), comment)
    return get_contract(contract_id)


def build_writeback_comment(c: dict) -> str:
    """格式化审查意见（回写审批系统评论区用）。"""
    lines = [
        f"## 合同智能审查意见 · {c['name']}",
        f"**综合风险等级**：{c['risk_level']}",
        "",
        "### 一、风险总评",
        c.get("summary") or "无",
        "",
        "### 二、需重点关注事项",
    ]
    for i, r in enumerate(c.get("risks", []), 1):
        lines.append(f"{i}. 【{r['level']}】{r['title']} —— {r['reason']}")
        lines.append(f"   建议：{r['suggestion']}")
    return "\n".join(lines)


def export_markdown(c: dict) -> str:
    return build_writeback_comment(c) + "\n\n### 三、审批记录\n" + (
        "\n".join(
            f"- {a['created_at']} {a['operator']}（{a['role']}）：{a['action']} {a['comment']}"
            for a in c.get("approvals", [])
        ) or "（暂无审批记录）"
    )
