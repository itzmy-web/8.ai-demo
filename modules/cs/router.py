"""电商小二（智能客服）路由。"""
from __future__ import annotations

from fastapi import APIRouter, Form

from . import engine

router = APIRouter(tags=["电商小二"])


@router.get("/flows")
def flows():
    return {
        "flows": [
            {"id": fid, "name": f["name"], "description": f.get("description", "")}
            for fid, f in engine.FLOWS.items()
        ]
    }


@router.get("/intents")
def intents():
    from . import intents as intent_mod
    return {"intents": list(intent_mod.KNOWLEDGE_INTENTS.values())}


@router.post("/chat")
async def chat(sender_id: str = Form("guest"), text: str = Form(...)):
    return await engine.handle_message(sender_id, text)


@router.get("/history")
def history(sender_id: str = "guest"):
    return {"history": engine.get_history(sender_id)}


@router.post("/reset")
def reset(sender_id: str = Form("guest")):
    engine.reset_state(sender_id)
    return {"ok": True}


@router.get("/onboarding")
def onboarding():
    return {"text": engine.onboarding_message()}
