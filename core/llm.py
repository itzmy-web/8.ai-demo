"""LLM 客户端（OpenAI 兼容，httpx 直连，双链路降级）。

- 配置了 LLM_API_KEY → 走 SiliconFlow / TokenHub 等 OpenAI 兼容端点；
- 未配置 → enabled() 为 False，各模块自动降级为规则 / 演示模式。
"""
from __future__ import annotations

import json
import logging

import httpx

import config

logger = logging.getLogger("fusion.llm")


def enabled() -> bool:
    return bool(config.LLM_API_KEY)


async def chat(
    messages: list[dict],
    *,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    response_json: bool = False,
) -> str:
    """调用 OpenAI 兼容 /chat/completions，返回文本内容。"""
    if not enabled():
        raise RuntimeError("LLM 未配置（DEMO 模式）")
    payload: dict = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_json:
        payload["response_format"] = {"type": "json_object"}
    async with httpx.AsyncClient(timeout=config.LLM_TIMEOUT) as client:
        resp = await client.post(
            f"{config.LLM_BASE_URL.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {config.LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"] or ""


async def chat_json(messages: list[dict], **kw) -> dict | list | None:
    """调用并解析 JSON（容忍 ```json 包裹与前后杂质）。"""
    text = await chat(messages, response_json=True, **kw)
    return parse_json(text)


def parse_json(text: str) -> dict | list | None:
    text = (text or "").strip()
    if text.startswith("```"):
        lines = [l for l in text.splitlines() if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 截取第一个 [ 或 { 到最后一个 ] 或 }
    starts = [i for i in (text.find("["), text.find("{")) if i != -1]
    if not starts:
        return None
    s = min(starts)
    ends = [i for i in (text.rfind("]"), text.rfind("}")) if i != -1]
    if not ends:
        return None
    e = max(ends)
    try:
        return json.loads(text[s : e + 1])
    except json.JSONDecodeError:
        return None
