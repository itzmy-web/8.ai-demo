"""四合一融合工作台 · 单端口入口。

模块：RAG 智库 / 合同审批 / 电商小二 / 电商运营助手 + 统一工作台前端。
启动：uvicorn main:app --host 0.0.0.0 --port $PORT
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import config
from core.db import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="四合一融合工作台", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BUILD_MARK = "2026-10-17-fusion-v3-code6"


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/health")
def health():
    return {"status": "ok", "build": BUILD_MARK, "demo_mode": config.DEMO_MODE}


# ---- 模块路由 ----
from modules.kb.router import router as kb_router
from modules.contract.router import router as contract_router
from modules.cs.router import router as cs_router
from modules.ops.router import router as ops_router

app.include_router(kb_router, prefix="/api/kb")
app.include_router(contract_router, prefix="/api/contract")
app.include_router(cs_router, prefix="/api/cs")
app.include_router(ops_router, prefix="/api/ops")

# ---- 工作台前端 ----
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")


@app.get("/")
def index():
    from fastapi.responses import FileResponse
    return FileResponse(str(config.STATIC_DIR / "index.html"))


# ---- 个人作品集（子路径 /portfolio，与工作台共用同一条发布链接）----
PORTFOLIO_DIR = config.STATIC_DIR / "portfolio"

if PORTFOLIO_DIR.exists():
    from fastapi.responses import FileResponse

    @app.get("/portfolio", include_in_schema=False)
    def portfolio_page():
        return FileResponse(str(PORTFOLIO_DIR / "index.html"))

    app.mount("/portfolio", StaticFiles(directory=str(PORTFOLIO_DIR), html=True), name="portfolio")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=config.APP_HOST, port=config.APP_PORT, log_level="info")
