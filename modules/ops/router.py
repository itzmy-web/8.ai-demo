"""电商运营助手路由。"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form
from pydantic import BaseModel

from . import agent as agent_mod
from . import store as store_mod

router = APIRouter(tags=["电商运营助手"])


class ProductUpdate(BaseModel):
    name: str | None = None
    platform: str | None = None
    price: float | None = None
    stock: int | None = None
    status: str | None = None
    category: str | None = None


class StoreUpdate(BaseModel):
    name: str | None = None
    platform: str | None = None
    status: str | None = None


# ---- 看板 ----
@router.get("/dashboard")
def dashboard():
    return store_mod.dashboard()


# ---- 商品 ----
@router.get("/products")
def products(keyword: str = "", platform: str = ""):
    return {"products": store_mod.list_products(keyword, platform)}


@router.post("/products")
def create_product(
    name: Annotated[str, Form()],
    platform: Annotated[str, Form()] = "taobao",
    price: Annotated[float, Form()] = 0,
    stock: Annotated[int, Form()] = 0,
    category: Annotated[str, Form()] = "",
):
    return {"ok": True, "product": store_mod.create_product(name, platform, price, stock, category)}


@router.put("/products/{pid}")
def update_product(pid: int, body: ProductUpdate):
    p = store_mod.update_product(pid, **body.model_dump(exclude_unset=True))
    return {"ok": True, "product": p}


@router.delete("/products/{pid}")
def delete_product(pid: int):
    store_mod.delete_product(pid)
    return {"ok": True}


# ---- 店铺 ----
@router.get("/stores")
def stores():
    return {"stores": store_mod.list_stores()}


@router.post("/stores")
def create_store(name: Annotated[str, Form()], platform: Annotated[str, Form()] = "taobao"):
    return {"ok": True, "store": store_mod.create_store(name, platform)}


@router.put("/stores/{sid}")
def update_store(sid: int, body: StoreUpdate):
    s = store_mod.update_store(sid, **body.model_dump(exclude_unset=True))
    return {"ok": True, "store": s}


@router.delete("/stores/{sid}")
def delete_store(sid: int):
    store_mod.delete_store(sid)
    return {"ok": True}


# ---- Agent ----
@router.get("/agents")
def agents():
    return {"agents": agent_mod.list_agents()}


@router.post("/agents/run")
async def run_agent(agent_id: Annotated[str, Form()], task: Annotated[str, Form()]):
    return await agent_mod.run_agent(agent_id, task)


@router.get("/agents/runs")
def runs():
    return {"runs": agent_mod.list_runs()}


# ---- 工作流 ----
@router.get("/workflows")
def workflows():
    return {"workflows": agent_mod.list_workflows()}


@router.post("/workflows")
def create_workflow(name: Annotated[str, Form()], trigger: Annotated[str, Form()] = "manual"):
    return {"ok": True, "workflow": agent_mod.create_workflow(name, trigger, ["待配置步骤"])}


@router.post("/workflows/{wid}/toggle")
def toggle_workflow(wid: int):
    w = agent_mod.toggle_workflow(wid)
    return {"ok": True, "workflow": w}


@router.delete("/workflows/{wid}")
def delete_workflow(wid: int):
    agent_mod.delete_workflow(wid)
    return {"ok": True}
