"""三轨对话引擎（移植自 itzmy customer-service-backend engine/dialogue_engine.py）。

架构同原版：TurnPlanner(LLM 路由) → TurnPlanValidator(防幻觉) → 三轨分发
  - task 轨：flow 步骤执行（start/collect/action/end，支持条件分支）
  - knowledge 轨：FAQ / RAG 智库检索
  - chitchat 轨：LLM 闲聊
差异：会话持久化从 MySQL 换 SQLite；LLM 走 OpenAI 兼容客户端；无 LLM 时关键词规则路由降级。
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import yaml

from core import db, llm
from . import intents as intent_mod

FLOWS_PATH = Path(__file__).resolve().parent / "flows.yml"

SESSION_TIMEOUT = 60 * 60  # 1 小时

# 内置演示数据（替代原外部电商服务 COMMERCE_API）
DEMO_ORDERS = {
    "10001": {"status": "已发货", "summary": "无线降噪耳机 Pro × 1，11 月 1 日已发出。",
              "company": "顺丰速运", "tracking": "SF1234567890", "logistics_status": "运输中，预计明日送达"},
    "10002": {"status": "待付款", "summary": "智能扫地机器人 X2 × 1，请在 24 小时内完成支付。",
              "company": "-", "tracking": "-", "logistics_status": "未发货（付款后 48 小时内发出）"},
    "10003": {"status": "已完成", "summary": "便携蓝牙音箱 Mini × 2，已签收。",
              "company": "中通快递", "tracking": "ZT9876543210", "logistics_status": "已签收"},
    "10004": {"status": "待发货", "summary": "4K 高清投影仪 H1 × 1，仓库正在打包。",
              "company": "京东物流", "tracking": "JD5566778899", "logistics_status": "已揽收，等待发出"},
}

DEMO_PRODUCTS = {
    "P1001": "无线降噪耳机 Pro（¥899）",
    "P1002": "智能扫地机器人 X2（¥2599）",
    "P1003": "便携蓝牙音箱 Mini（¥299）",
    "P1004": "4K 高清投影仪 H1（¥3299）",
    "P1005": "运动智能手表 S7（¥699）",
}


def load_flows() -> dict:
    with open(FLOWS_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return {"slots": cfg.get("slots", {}), "flows": cfg.get("flows", {})}


FLOW_CFG = load_flows()
FLOWS = FLOW_CFG["flows"]
FLOW_LIST_JSON = json.dumps(
    [{"id": fid, "name": f["name"], "description": f.get("description", "")} for fid, f in FLOWS.items()],
    ensure_ascii=False,
)
INTENTS_JSON = json.dumps(
    [{"id": i["id"], "description": i["description"]} for i in intent_mod.KNOWLEDGE_INTENTS.values()],
    ensure_ascii=False,
)


# ---------------- 会话状态（SQLite 持久化） ----------------

def _blank_state(sender_id: str) -> dict:
    return {
        "sender_id": sender_id, "history": [], "active_task": None,
        "slots": {}, "flow_id": None, "step_id": None, "last_active": time.time(),
    }


def load_state(sender_id: str) -> dict:
    row = db.query_one("SELECT * FROM cs_sessions WHERE sender_id=?", (sender_id,))
    now = time.time()
    if row is None:
        state = _blank_state(sender_id)
        _save_state(state)
        return state
    if now - row["last_active"] > SESSION_TIMEOUT:
        state = _blank_state(sender_id)
        _save_state(state)
        return state
    return {
        "sender_id": sender_id,
        "history": json.loads(row["history"] or "[]"),
        "active_task": json.loads(row["active_task"]) if row["active_task"] else None,
        "slots": json.loads(row["slots"] or "{}"),
        "flow_id": row["flow_id"], "step_id": row["step_id"],
        "last_active": now,
    }


def _save_state(state: dict) -> None:
    db.execute(
        "INSERT INTO cs_sessions(sender_id, history, active_task, slots, flow_id, step_id, last_active)"
        " VALUES (?,?,?,?,?,?,?)"
        " ON CONFLICT(sender_id) DO UPDATE SET history=excluded.history, active_task=excluded.active_task,"
        " slots=excluded.slots, flow_id=excluded.flow_id, step_id=excluded.step_id,"
        " last_active=excluded.last_active, updated_at=datetime('now','localtime')",
        (
            state["sender_id"], json.dumps(state["history"], ensure_ascii=False),
            json.dumps(state["active_task"], ensure_ascii=False) if state["active_task"] else None,
            json.dumps(state["slots"], ensure_ascii=False),
            state["flow_id"], state["step_id"], time.time(),
        ),
    )


def reset_state(sender_id: str) -> None:
    db.execute("DELETE FROM cs_sessions WHERE sender_id=?", (sender_id,))
    db.execute("DELETE FROM cs_messages WHERE sender_id=?", (sender_id,))


# ---------------- TurnPlanner（LLM 路由 + 规则降级） ----------------

PLANNER_SYSTEM = """你是电商客服对话路由引擎。根据用户消息与上下文，输出 TurnPlan JSON。
TurnPlan 只允许三个字段：task / knowledge / chitchat，值为对象或 null。
- 用户在办理业务（查订单/查物流/退款/推荐/转人工）→ task：{"commands":[{"command":"start_flow","flow":"<flow_id>"}]}
- 用户在流程进行中补充信息 → task：{"commands":[{"command":"set_slots","slots":{"<slot>":"<值>"}}]}
- 用户要取消当前流程 → task：{"commands":[{"command":"cancel_flow"}]}
- 用户要回到之前中断的流程 → task：{"commands":[{"command":"resume_flow","flow":"<flow_id>"}]}
- 用户在咨询信息 → knowledge：{"intents":["<intent_id>"]}
- 用户在闲聊 → chitchat：{}
只输出合法 JSON，不要 markdown。"""


def _keyword_plan(text: str, state: dict) -> dict:
    """无 LLM 时的关键词规则路由（防幻觉天然成立：全部来自白名单）。"""
    # 疑问词优先走咨询轨：「退款要多久到账」是咨询而非办理
    consult_words = ("多久", "怎么", "如何", "多少", "什么时候", "几天", "几天能")
    if any(w in text for w in consult_words):
        hits = intent_mod.match_intents_by_keywords(text)
        if hits:
            return {"knowledge": {"intents": hits[:2]}}
    if state.get("active_task"):
        # 流程进行中：取消 / 继续填槽
        if any(k in text for k in ("取消", "算了", "不办了", "退出")):
            return {"task": {"commands": [{"command": "cancel_flow"}]}}
        return {"task": {"commands": [{"command": "set_slots", "slots": {"_raw_input": text}}]}}
    if any(k in text for k in ("转人工", "人工客服", "找客服")):
        return {"task": {"commands": [{"command": "start_flow", "flow": "human_handoff"}]}}
    if any(k in text for k in ("退款", "退钱")):
        return {"task": {"commands": [{"command": "start_flow", "flow": "refund_request"}]}}
    if any(k in text for k in ("物流", "快递", "到哪了", "发货了吗")):
        return {"task": {"commands": [{"command": "start_flow", "flow": "logistics_tracking"}]}}
    if any(k in text for k in ("订单状态", "查订单", "订单到哪", "我的订单")):
        return {"task": {"commands": [{"command": "start_flow", "flow": "order_status_query"}]}}
    if any(k in text for k in ("推荐", "类似的", "相似")):
        return {"task": {"commands": [{"command": "start_flow", "flow": "similar_product_recommendation"}]}}
    hits = intent_mod.match_intents_by_keywords(text)
    if hits:
        return {"knowledge": {"intents": hits[:2]}}
    return {"chitchat": {}}


async def plan_turn(text: str, state: dict) -> dict:
    if llm.enabled():
        hist = "\n".join(
            f"{'用户' if h['role']=='user' else '客服'}: {h['text']}" for h in state["history"][-10:]
        )
        active = json.dumps({"flow_id": state.get("flow_id"), "step_id": state.get("step_id"),
                             "slots": state.get("slots")}, ensure_ascii=False) if state.get("active_task") else "null"
        user = (
            f"## 当前状态\n活跃任务：{active}\n\n## 可用 flows\n{FLOW_LIST_JSON}\n\n"
            f"## 可用知识意图\n{INTENTS_JSON}\n\n## 对话历史\n{hist or '（无）'}\n\n"
            f"## 当前用户消息\n{text}\n\n请输出 TurnPlan JSON："
        )
        try:
            plan = await llm.chat_json(
                [{"role": "system", "content": PLANNER_SYSTEM},
                 {"role": "user", "content": user}],
                temperature=0.1,
            )
            if isinstance(plan, dict):
                return plan
        except Exception:  # noqa: BLE001
            pass
    return _keyword_plan(text, state)


# ---------------- TurnPlanValidator（防幻觉校验） ----------------

def validate_plan(plan: dict, state: dict) -> tuple[bool, str]:
    task = plan.get("task")
    knowledge = plan.get("knowledge")
    if task is None and knowledge is None and plan.get("chitchat") is None:
        return False, "empty_plan"
    if task is not None:
        if not isinstance(task, dict) or not isinstance(task.get("commands"), list):
            return False, "bad_task_shape"
        for cmd in task["commands"]:
            name = cmd.get("command")
            if name not in ("start_flow", "resume_flow", "cancel_flow", "set_slots"):
                return False, f"unknown_command:{name}"
            if name in ("start_flow", "resume_flow") and cmd.get("flow") not in FLOWS:
                return False, f"unknown_flow:{cmd.get('flow')}"
            if name == "set_slots" and not isinstance(cmd.get("slots"), dict):
                return False, "bad_slots"
    if knowledge is not None:
        if not isinstance(knowledge, dict) or not isinstance(knowledge.get("intents"), list):
            return False, "bad_knowledge_shape"
        for it in knowledge["intents"]:
            if it not in intent_mod.KNOWLEDGE_INTENTS:
                return False, f"unknown_intent:{it}"
    return True, ""


# ---------------- Flow 执行器 ----------------

def _render_template(text: str, slots: dict) -> str:
    def repl(m: re.Match) -> str:
        key = m.group(1).strip()
        return str(slots.get(key, ""))
    return re.sub(r"\{\{\s*slots\.([a-zA-Z_]+)\s*\}\}", repl, text)


def _resolve_next(step: dict, slots: dict) -> str | None:
    nxt = step.get("next")
    if isinstance(nxt, str):
        return nxt
    if isinstance(nxt, list):
        for branch in nxt:
            cond = branch.get("if", "")
            if "slots.get('" in cond:
                key = cond.split("slots.get('")[1].split("')")[0]
                hit = bool(slots.get(key))
            else:
                hit = bool(cond) and cond != "False"
            if hit:
                return branch.get("then")
            if "else" in branch:
                return branch.get("else")
    return None


def _run_action(action: str, args: dict, slots: dict) -> str:
    if action == "action_response":
        return _render_template(args.get("text", ""), slots)
    if action == "action_lookup_order_status":
        order = DEMO_ORDERS.get(str(slots.get("order_number", "")).strip())
        if order:
            slots["order_status"] = order["status"]
            slots["order_summary"] = order["summary"]
            return ""
        return f"没有查到订单 {slots.get('order_number')} 的记录，请确认订单号是否正确。"
    if action == "action_lookup_logistics":
        order = DEMO_ORDERS.get(str(slots.get("order_number", "")).strip())
        if order:
            slots["logistics_company"] = order["company"]
            slots["tracking_number"] = order["tracking"]
            slots["logistics_status"] = order["logistics_status"]
            return ""
        return f"没有查到订单 {slots.get('order_number')} 的物流信息，请确认订单号是否正确。"
    if action == "action_recommend_similar_products":
        pid = str(slots.get("product_id", "")).strip()
        name = DEMO_PRODUCTS.get(pid)
        if name:
            return f"您正在看「{name}」。为您推荐：无线降噪耳机 Pro（¥899）、运动智能手表 S7（¥699），目前在「商品池」均有现货。"
        return "为您推荐：无线降噪耳机 Pro（¥899）、智能扫地机器人 X2（¥2599），可在「商品池」查看详情。"
    return ""


def _advance_flow(state: dict, raw_input: str | None = None) -> str:
    """推进当前 flow 一步，返回机器人回复文本。"""
    flow = FLOWS.get(state["flow_id"])
    if flow is None:
        state.update(active_task=None, flow_id=None, step_id=None)
        return "流程已重置。"
    steps = {s["id"]: s for s in flow["steps"]}
    step = steps.get(state["step_id"])
    if step is None:
        state.update(active_task=None, flow_id=None, step_id=None)
        return "流程状态异常，已重置。"

    stype = step["type"]
    if stype == "collect":
        slot_name = step.get("slot_name", "")
        current = str(state["slots"].get(slot_name, "")).strip()
        if not current and raw_input:
            state["slots"][slot_name] = raw_input.strip()
        if not str(state["slots"].get(slot_name, "")).strip():
            # 槽未填 → 向用户索要
            return _render_template(step.get("response", {}).get("text", ""), state["slots"])
        nxt = _resolve_next(step, state["slots"])
        state["step_id"] = nxt
        return _advance_flow(state)
    if stype == "action":
        reply = _run_action(step.get("action", ""), step.get("args", {}) or {}, state["slots"])
        nxt = _resolve_next(step, state["slots"])
        state["step_id"] = nxt
        if reply:
            return reply
        if nxt is None:
            state.update(active_task=None, flow_id=None, step_id=None)
            return "已处理完成，还有别的可以帮您？"
        return _advance_flow(state)
    if stype == "start":
        nxt = _resolve_next(step, state["slots"])
        state["step_id"] = nxt
        return _advance_flow(state)
    # end
    state.update(active_task=None, flow_id=None, step_id=None)
    return "已处理完成，还有别的可以帮您？"


def _start_flow(state: dict, flow_id: str) -> str:
    state.update(active_task={"flow_id": flow_id}, flow_id=flow_id, step_id=None, slots={})
    flow = FLOWS[flow_id]
    first = flow["steps"][0]
    state["step_id"] = first["id"]
    return _advance_flow(state)


def _cancel_flow(state: dict) -> str:
    state.update(active_task=None, flow_id=None, step_id=None, slots={})
    return "好的，已取消当前办理。还有什么可以帮您？"


# ---------------- 三轨分发 ----------------

async def handle_message(sender_id: str, text: str) -> dict:
    state = load_state(sender_id)
    state["last_active"] = time.time()

    # 流程进行中且没有新的明确意图 → 优先把消息当作槽值/流程输入
    plan = await plan_turn(text, state)
    valid, reason = validate_plan(plan, state)
    if not valid:
        reply = "没太明白您的意思，您可以：查订单、查物流、申请退款、转人工，或直接咨询商品与政策问题。"
        _record(state, text, reply, track="clarify")
        return {"reply": reply, "track": "clarify", "reason": reason}

    task = plan.get("task")
    knowledge = plan.get("knowledge")
    track = ""
    reply = ""

    if task is not None:
        track = "task"
        for cmd in task.get("commands", []):
            name = cmd.get("command")
            if name == "start_flow":
                reply = _start_flow(state, cmd["flow"])
            elif name == "cancel_flow":
                reply = _cancel_flow(state)
            elif name == "set_slots":
                raw = cmd.get("slots", {}).get("_raw_input", text)
                if state.get("active_task"):
                    reply = _advance_flow(state, raw)
                else:
                    reply = "您想办理哪项业务？可以说：查订单、查物流、申请退款或转人工。"
            elif name == "resume_flow":
                fid = cmd.get("flow")
                if state.get("active_task") and state.get("flow_id") == fid:
                    reply = _advance_flow(state)
                else:
                    reply = f"好的，为您打开「{FLOWS.get(fid, {}).get('name', fid)}」流程。"
                    reply = _start_flow(state, fid) + ""
    elif knowledge is not None:
        track = "knowledge"
        reply = await _handle_knowledge(knowledge.get("intents", []), text)
    else:
        track = "chitchat"
        reply = await _handle_chitchat(text, state)

    _record(state, text, reply, track=track)
    return {"reply": reply, "track": track, "plan": plan}


async def _handle_knowledge(intent_ids: list[str], text: str) -> str:
    if not intent_ids:
        intent_ids = intent_mod.match_intents_by_keywords(text)[:1]
    if not intent_ids:
        return "这个问题我还在学习中，您可以换个问法，或者说「转人工」联系人工客服。"
    parts = []
    for iid in intent_ids[:2]:
        faq = intent_mod.faq_answer(iid)
        if "rag.default" in intent_mod.KNOWLEDGE_INTENTS[iid]["providers"]:
            # 尝试从融合版 RAG 智库补充检索
            try:
                from modules.kb import rag
                hits = rag.search(text, top_k=1)
                if hits:
                    faq += f"\n\n📚 知识库补充：{hits[0]['text'][:200]}（来源：{hits[0]['doc_name']}）"
            except Exception:  # noqa: BLE001
                pass
        parts.append(faq)
    return "\n\n".join(parts)


async def _handle_chitchat(text: str, state: dict) -> str:
    if llm.enabled():
        try:
            hist = [{"role": "user" if h["role"] == "user" else "assistant", "content": h["text"]}
                    for h in state["history"][-6:]]
            hist.append({"role": "user", "content": text})
            return await llm.chat(
                [{"role": "system", "content": "你是亲和力强的电商客服助手「小二」，回答简洁自然，不啰嗦。"}] + hist,
                temperature=0.6,
            )
        except Exception:  # noqa: BLE001
            pass
    if any(k in text for k in ("你好", "在吗", "hi", "hello", "嗨")):
        return "您好呀，我是电商小二～查订单、查物流、退款退货、商品咨询都可以找我。"
    if any(k in text for k in ("谢谢", "感谢", "辛苦了")):
        return "不客气，能帮到您就好～还有别的需要随时说。"
    if any(k in text for k in ("再见", "拜拜", "bye")):
        return "再见，祝您购物愉快，欢迎随时来找我！"
    return "嗯嗯，我在听。您可以问我订单、物流、退款政策，或者说「转人工」找人工客服。"


def _record(state: dict, user_text: str, bot_text: str, track: str) -> None:
    state["history"].append({"role": "user", "text": user_text})
    state["history"].append({"role": "bot", "text": bot_text})
    state["history"] = state["history"][-40:]
    _save_state(state)
    db.execute(
        "INSERT INTO cs_messages(sender_id, role, text, track) VALUES (?,?,?,?)",
        (state["sender_id"], "user", user_text, track),
    )
    db.execute(
        "INSERT INTO cs_messages(sender_id, role, text, track) VALUES (?,?,?,?)",
        (state["sender_id"], "bot", bot_text, track),
    )


def get_history(sender_id: str) -> list[dict]:
    rows = db.query_all(
        "SELECT role, text, track, created_at FROM cs_messages WHERE sender_id=? ORDER BY id",
        (sender_id,),
    )
    return rows


def onboarding_message() -> str:
    flow = FLOWS["onboarding"]
    step = flow["steps"][1]
    return _render_template(step["args"]["text"], {})
