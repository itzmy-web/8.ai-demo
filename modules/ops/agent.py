"""运营 Agent + 自动化工作流（移植自运营助手 agent / workflows / automation 页面）。

预置 4 个运营 Agent；run 时分步骤执行，LLM 可用走 LLM，否则规则模板演示。
"""
from __future__ import annotations

import json
import time

from core import db, llm

AGENTS = [
    {"id": "selection_analyst", "name": "选品分析师",
     "desc": "分析商品池价格带与库存结构，给出选品与补货建议",
     "steps": ["拉取商品池数据", "价格带与库存分析", "生成选品建议"]},
    {"id": "inventory_inspector", "name": "库存巡检员",
     "desc": "扫描低库存商品，生成补货优先级清单",
     "steps": ["扫描库存", "标记低库存商品", "生成补货清单"]},
    {"id": "competitor_tracker", "name": "竞品追踪员",
     "desc": "对比竞品价格与卖点，输出调价与差异化建议",
     "steps": ["确定竞品范围", "价格对比分析", "输出调价建议"]},
    {"id": "copywriter", "name": "文案写手",
     "desc": "为指定商品生成标题与卖点文案",
     "steps": ["读取商品信息", "提炼卖点", "生成标题文案"]},
]


def list_agents() -> list[dict]:
    return AGENTS


async def run_agent(agent_id: str, task: str) -> dict:
    agent = next((a for a in AGENTS if a["id"] == agent_id), None)
    if not agent:
        return {"ok": False, "error": "Agent 不存在"}
    run_id = db.execute(
        "INSERT INTO ops_agent_runs(agent, task, status, steps) VALUES (?,?, 'running', '[]')",
        (agent["name"], task),
    )
    steps_done: list[dict] = []
    products = db.query_all("SELECT * FROM ops_products")
    for step in agent["steps"]:
        detail = _step_detail(agent_id, step, task, products)
        steps_done.append({"step": step, "detail": detail, "at": time.strftime("%H:%M:%S")})
        db.execute(
            "UPDATE ops_agent_runs SET steps=? WHERE id=?",
            (json.dumps(steps_done, ensure_ascii=False), run_id),
        )
    result = await _final_result(agent_id, task, steps_done, products)
    db.execute(
        "UPDATE ops_agent_runs SET status='done', result=? WHERE id=?",
        (result, run_id),
    )
    return {"ok": True, "run_id": run_id, "agent": agent["name"],
            "steps": steps_done, "result": result}


def _step_detail(agent_id: str, step: str, task: str, products: list[dict]) -> str:
    if "拉取商品池数据" in step or "扫描库存" in step:
        return f"商品池共 {len(products)} 个商品，覆盖 {len({p['platform'] for p in products})} 个平台。"
    if "价格带与库存分析" in step:
        prices = [p["price"] for p in products]
        return f"价格区间 ¥{min(prices):.0f} - ¥{max(prices):.0f}，均价 ¥{sum(prices)/len(prices):.0f}；总库存 {sum(p['stock'] for p in products)} 件。"
    if "生成选品建议" in step:
        return "建议补充 300-800 元价位段爆款；高客单商品加强内容种草。"
    if "标记低库存商品" in step:
        low = [p["name"] for p in products if p["stock"] < 100]
        return f"低库存商品 {len(low)} 个：" + ("、".join(low) if low else "无")
    if "生成补货清单" in step:
        low = [p for p in products if p["stock"] < 100]
        return "；".join(f"{p['name']}（当前 {p['stock']} 件，建议补至 300）" for p in low) or "库存健康，无需补货"
    if "确定竞品范围" in step:
        return "已锁定同价位段竞品 3 个（演示数据）。"
    if "价格对比分析" in step:
        return "本店主力商品价格处于同价位段中游，具备 5%-8% 调价空间。"
    if "输出调价建议" in step:
        return "建议对低周转商品小幅降价 3%-5% 冲量，爆款维持现价保利润。"
    if "读取商品信息" in step:
        target = next((p for p in products if p["name"] in task), None) or (products[0] if products else None)
        return f"目标商品：{target['name']}（¥{target['price']}，库存 {target['stock']}）" if target else "商品池为空"
    if "提炼卖点" in step:
        return "卖点：品质可靠、物流快捷、售后无忧。"
    if "生成标题文案" in step:
        return "推荐标题：「【旗舰新品】高性价比之选 顺丰包邮 7天无理由退」"
    return "执行完成"


async def _final_result(agent_id: str, task: str, steps: list[dict], products: list[dict]) -> str:
    if llm.enabled():
        try:
            ctx = "\n".join(f"- {s['step']}：{s['detail']}" for s in steps)
            return await llm.chat(
                [{"role": "system", "content": "你是电商运营专家，根据执行步骤输出一份简洁的结论报告（200字内）。"},
                 {"role": "user", "content": f"任务：{task}\n执行过程：\n{ctx}\n\n请输出结论："}],
                temperature=0.4,
            )
        except Exception:  # noqa: BLE001
            pass
    return "；".join(s["detail"] for s in steps)


def list_runs(limit: int = 20) -> list[dict]:
    rows = db.query_all("SELECT * FROM ops_agent_runs ORDER BY id DESC LIMIT ?", (limit,))
    for r in rows:
        r["steps"] = json.loads(r["steps"] or "[]")
    return rows


# ---------------- 工作流 ----------------

def list_workflows() -> list[dict]:
    rows = db.query_all("SELECT * FROM ops_workflows ORDER BY id DESC")
    for r in rows:
        r["steps"] = json.loads(r["steps"] or "[]")
    return rows


def create_workflow(name: str, trigger: str, steps: list[str]) -> dict:
    wid = db.execute(
        "INSERT INTO ops_workflows(name, trigger, steps, enabled) VALUES (?,?,?,1)",
        (name, trigger, json.dumps(steps, ensure_ascii=False)),
    )
    return db.query_one("SELECT * FROM ops_workflows WHERE id=?", (wid,))


def toggle_workflow(wid: int) -> dict | None:
    row = db.query_one("SELECT * FROM ops_workflows WHERE id=?", (wid,))
    if not row:
        return None
    new = 0 if row["enabled"] else 1
    db.execute("UPDATE ops_workflows SET enabled=? WHERE id=?", (new, wid))
    return db.query_one("SELECT * FROM ops_workflows WHERE id=?", (wid,))


def delete_workflow(wid: int) -> None:
    db.execute("DELETE FROM ops_workflows WHERE id=?", (wid,))
