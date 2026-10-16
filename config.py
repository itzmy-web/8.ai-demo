"""融合工作台 · 全局配置。

LLM 双链路：优先读环境变量 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL；
未配置时全系统自动降级为「规则 / 演示模式」（合同规则审查、关键词路由、FAQ 兜底），
保证云端沙箱无 Key 也能完整演示。
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "fusion.db"


def _load_dotenv() -> None:
    """加载根目录 .env（不覆盖已存在的环境变量）。"""
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()

# ---- LLM（OpenAI 兼容，双链路降级）----
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.siliconflow.cn/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen3-8B-27B")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))

# ---- 服务 ----
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("PORT", os.getenv("APP_PORT", "8020")))

# ---- 演示模式（无 LLM 时规则兜底）----
DEMO_MODE = not bool(LLM_API_KEY)
