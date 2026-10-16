"""合同审查规则引擎（移植自 D:/审批合同 backend/rules.py）。

数据驱动：mode=keyword/regex/absence/custom 四种规则，新增规则只加数据不改逻辑。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

LEVELS = ("high", "medium", "low")

REQUIRED_CLAUSES = {
    "procurement": ["标的物条款", "付款进度", "验收标准", "违约责任", "保密义务", "争议解决管辖", "知识产权"],
    "sales": ["标的物条款", "付款进度", "验收标准", "违约责任", "争议解决管辖"],
    "service": ["标的物条款", "付款进度", "验收标准", "违约责任", "保密义务", "争议解决管辖"],
    "labor": ["标的物条款", "付款进度", "违约责任", "保密义务", "争议解决管辖"],
}


@dataclass
class Risk:
    risk_id: str
    title: str
    clause_type: str
    level: str  # high / medium / low
    reason: str
    legal_basis: str
    snippet: str = ""
    suggestion: str = ""
    by_llm: bool = False


@dataclass
class Rule:
    rule_id: str
    name: str
    level: str
    clause_types: list[str] = field(default_factory=list)
    mode: str = "keyword"  # keyword / regex / absence / custom
    pattern: str = ""
    biz_types: list[str] = field(default_factory=list)
    reason: str = ""
    legal_basis: str = ""
    suggestion: str = ""
    detector: str = ""  # custom 模式的检测器名


DEFAULT_RULES = [
    Rule("R-H1", "主体资质缺失/经营异常", "high", ["其他条款"], "custom",
         detector="party_missing",
         reason="签约主体名称或统一社会信用代码缺失，或相对方被列入经营异常，合同效力与履约能力存疑。",
         legal_basis="《民法典》第143条（民事法律行为有效要件）。",
         suggestion="补充完整签约主体名称与统一社会信用代码，并核实相对方经营状态后签署。"),
    Rule("R-H2", "违约责任严重不对等", "high", ["违约责任"], "keyword",
         pattern="无限责任|由甲方承担全部责任|甲方承担无限|甲方承担全部赔偿责任|无上限的赔偿责任",
         reason="违约责任严重不对等，我方单方承担无限/全部责任，显失公平。",
         legal_basis="《民法典》第6条（公平原则）、第497条（格式条款无效情形）。",
         suggestion="修改为对等责任，如「双方对因各自过错造成的损失分别承担责任，任一方赔偿责任不超过合同总额的 20%」。"),
    Rule("R-H3", "争议管辖条款缺失", "high", ["争议解决管辖"], "absence",
         pattern="争议解决管辖",
         reason="缺少争议解决与管辖约定，维权时管辖法院不明，增加诉讼成本与不确定性。",
         legal_basis="《民事诉讼法》第35条（协议管辖）。",
         suggestion="约定由我方所在地有管辖权的人民法院诉讼，或约定境内仲裁机构仲裁。"),
    Rule("R-H4", "付款无前置验收条件", "high", ["付款进度"], "custom",
         detector="payment_without_acceptance",
         biz_types=["procurement", "sales", "service"],
         reason="未设置付款前置验收条件，付款后即丧失质量抗辩权，资金风险高。",
         legal_basis="《民法典》第626条（买受人检验义务）、第628条。",
         suggestion="增加「买方在验收合格并出具验收报告后 X 个工作日内支付对应款项」的付款前置条件。"),
    Rule("R-H5", "知识产权归属不利", "high", ["知识产权"], "keyword",
         pattern="知识产权归乙方|知识产权由乙方|知识产权归属乙方|知识产权归供应商|归乙方所有",
         reason="核心知识产权（含定制开发源代码）归属相对方，我方投入无法沉淀资产。",
         legal_basis="《民法典》第123条（知识产权客体）；委托开发合同相关规定。",
         suggestion="修改为「定制开发部分之源代码及全部知识产权归甲方所有，乙方保留为履行本合同所必需的使用许可」。"),
    Rule("R-M1", "保密义务缺期限", "medium", ["保密义务"], "custom",
         detector="nda_without_term",
         reason="保密义务未明确期限，约束期不明，存在泄密后无法追责风险。",
         legal_basis="《反不正当竞争法》第9条（商业秘密保护）。",
         suggestion="明确保密期限，如「保密义务在本合同终止后持续 3 年」。"),
    Rule("R-M2", "不可抗力未约通知时效", "medium", ["其他条款"], "custom",
         detector="force_majeure_without_notice",
         reason="不可抗力条款未明确通知时效，争议时难以举证免责。",
         legal_basis="《民法典》第590条（不可抗力通知与证明）。",
         suggestion="补充「受影响方应在不可抗力发生后 5 个工作日内书面通知对方并提供证明」。"),
    Rule("R-M3", "违约金比例超合理范围", "medium", ["违约责任"], "custom",
         detector="penalty_over_cap",
         reason="违约金比例超出法定合理范围或约定无上限，可能被认定过高/显失公平。",
         legal_basis="《民法典》第585条（违约金调整：过分高于损失的可请求酌减）。",
         suggestion="将违约金调整为「不超过合同总额的 20%」，并以实际损失为赔偿上限。"),
    Rule("R-M4", "验收标准与期限缺失", "medium", ["验收条款"], "absence",
         pattern="验收",
         reason="缺少验收标准与验收期限，交付质量与付款节点将无从认定，极易产生扯皮。",
         legal_basis="《民法典》第620条（买受人检验义务）、第621条。",
         suggestion="补充：「乙方交付后 10 个工作日内，甲方按《功能需求说明书》完成验收并出具书面验收报告；逾期未提出书面异议视为验收合格。」"),
    Rule("R-L1", "争议管辖约定不利", "low", ["争议解决管辖"], "keyword",
         pattern="由乙方所在地|由相对方所在地|境外仲裁|乙方所在地人民法院",
         reason="管辖地约定对我方不利（约定相对方所在地或境外机构），诉讼/仲裁成本与结果不确定性显著增加。",
         legal_basis="《民事诉讼法》第35条（协议管辖应选择与争议有实际联系地点的法院）。",
         suggestion="修改为「因本合同发生争议，提交甲方所在地有管辖权的人民法院诉讼解决」。"),
]


# ---------- 自定义检测器（跨字段判断） ----------

def _det_party_missing(text: str, segments: dict) -> str:
    if "经营异常" in text:
        return "文本含「经营异常」"
    if not re.search(r"(甲方|买方|委托方|采购方)[:：\s]*[一-龥A-Za-z0-9（）()]{2,}", text):
        return "未识别到甲方（买方）主体名称"
    return ""


def _det_payment_without_acceptance(text: str, segments: dict) -> str:
    has_payment = any(k in text for k in ("付款", "支付", "结算"))
    has_acceptance = "验收" in text or "检验" in text
    if has_payment and not has_acceptance:
        return "存在付款条款但缺少验收标准条款（付款前置验收缺失）"
    return ""


def _det_nda_without_term(text: str, segments: dict) -> str:
    if "保密" not in text:
        return ""
    if not re.search(r"保密[^。]{0,40}(\d+\s*年|\d+\s*个月|期限)", text):
        return "存在保密条款但未约定保密期限（年/月）"
    return ""


def _det_force_majeure_without_notice(text: str, segments: dict) -> str:
    if "不可抗力" not in text:
        return ""
    if not re.search(r"不可抗力[^。]{0,60}(通知|书面)", text):
        return "文本含「不可抗力」但未约定通知时限"
    return ""


def _det_penalty_over_cap(text: str, segments: dict) -> str:
    m = re.search(r"违约金[^。]{0,30}?(\d+(?:\.\d+)?)\s*%", text)
    if not m:
        # 百分比在前：「每日按合同总额的0.5%支付违约金」
        m = re.search(r"(\d+(?:\.\d+)?)\s*%[^。]{0,20}违约金", text)
    if m and float(m.group(1)) > 20:
        return f"违约金比例 {m.group(1)}% 超过合同总额 20%"
    if "赔偿全部损失" in text or "赔偿一切损失" in text:
        return "约定「赔偿全部损失」无上限"
    return ""


DETECTORS = {
    "party_missing": _det_party_missing,
    "payment_without_acceptance": _det_payment_without_acceptance,
    "nda_without_term": _det_nda_without_term,
    "force_majeure_without_notice": _det_force_majeure_without_notice,
    "penalty_over_cap": _det_penalty_over_cap,
}


def segment_text(text: str) -> dict[str, str]:
    """按条款类型粗分（用于 absence 规则判断）。"""
    seg_map = {
        "标的物条款": ["标的", "货物", "服务内容", "采购内容"],
        "付款进度": ["付款", "支付", "结算"],
        "验收标准": ["验收", "检验"],
        "违约责任": ["违约", "赔偿责任"],
        "保密义务": ["保密"],
        "争议解决管辖": ["争议", "管辖", "仲裁"],
        "知识产权": ["知识产权"],
    }
    segments: dict[str, str] = {}
    for ctype, kws in seg_map.items():
        hits = [ln for ln in text.splitlines() if any(k in ln for k in kws)]
        if hits:
            segments[ctype] = "\n".join(hits[:5])
    return segments


def _locate(text: str, keyword: str) -> tuple[str, int, int]:
    idx = text.find(keyword)
    if idx < 0:
        return "", 0, 0
    start = max(0, idx - 12)
    end = min(len(text), idx + len(keyword) + 12)
    return text[start:end].replace("\n", " "), start, end


def evaluate(text: str, biz_type: str = "procurement", rules: list[Rule] | None = None) -> list[Risk]:
    rules = rules or DEFAULT_RULES
    segments = segment_text(text)
    risks: list[Risk] = []
    for rule in rules:
        if rule.biz_types and biz_type not in rule.biz_types:
            continue
        hit = ""
        if rule.mode == "keyword":
            m = re.search(rule.pattern, text)
            if m:
                hit = m.group(0)
        elif rule.mode == "regex":
            m = re.search(rule.pattern, text)
            if m:
                hit = m.group(0)
        elif rule.mode == "absence":
            for kw in re.split(r"[|,]", rule.pattern):
                kw = kw.strip()
                if not kw:
                    continue
                if not any(kw in seg for seg in segments.values()):
                    hit = f"缺少「{kw}」相关条款"
                    break
        elif rule.mode == "custom":
            det = DETECTORS.get(rule.detector)
            if det:
                hit = det(text, segments) or ""
        if hit:
            snippet, s, e = _locate(text, hit) if rule.mode in ("keyword", "regex") else ("", 0, 0)
            risks.append(Risk(
                risk_id=f"{rule.rule_id}-{len(risks)+1:02d}",
                title=rule.name, clause_type=(rule.clause_types or ["其他条款"])[0],
                level=rule.level, reason=rule.reason, legal_basis=rule.legal_basis,
                snippet=snippet or hit, suggestion=rule.suggestion,
            ))
    return risks


def overall_level(risks: list[Risk]) -> str:
    if any(r.level == "high" for r in risks):
        return "high"
    if any(r.level == "medium" for r in risks):
        return "medium"
    if risks:
        return "low"
    return "none"


def list_rules() -> list[dict]:
    return [
        {
            "rule_id": r.rule_id, "name": r.name, "level": r.level,
            "mode": r.mode, "clause_types": r.clause_types,
            "biz_types": r.biz_types, "reason": r.reason,
            "legal_basis": r.legal_basis, "suggestion": r.suggestion,
        }
        for r in DEFAULT_RULES
    ]
