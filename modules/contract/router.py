"""合同审批路由。"""
from __future__ import annotations

from fastapi import APIRouter, Form, UploadFile
from fastapi.responses import PlainTextResponse

from . import review

router = APIRouter(tags=["合同审批"])


@router.get("/rules")
def rules():
    return {"rules": review.rule_engine.list_rules()}


@router.get("/contracts")
def contracts(status: str = ""):
    return {"contracts": review.list_contracts(status)}


@router.post("/contracts")
async def create(
    name: str = Form(...),
    biz_type: str = Form("procurement"),
    applicant: str = Form("业务经办人"),
    text: str = Form(""),
    file: UploadFile | None = None,
):
    if file is not None and not text:
        raw = await file.read()
        for enc in ("utf-8", "gbk", "gb18030"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = raw.decode("utf-8", errors="ignore")
        if name == "未命名合同":
            name = file.filename or name
    if not text.strip():
        return {"ok": False, "error": "合同内容为空"}
    c = await review.review_contract(name=name, text=text, biz_type=biz_type, applicant=applicant)
    return {"ok": True, "contract": c}


@router.get("/contracts/{contract_id}")
def detail(contract_id: int):
    c = review.get_contract(contract_id)
    if not c:
        return {"ok": False, "error": "合同不存在"}
    return {"ok": True, "contract": c}


@router.post("/contracts/{contract_id}/decide")
def decide(
    contract_id: int,
    action: str = Form(...),
    operator: str = Form("张三"),
    role: str = Form("admin"),
    comment: str = Form(""),
):
    c = review.decide(contract_id, action, operator, role, comment)
    return {"ok": True, "contract": c}


@router.get("/contracts/{contract_id}/writeback")
def writeback(contract_id: int):
    c = review.get_contract(contract_id)
    if not c:
        return {"ok": False, "error": "合同不存在"}
    return {"ok": True, "comment": review.build_writeback_comment(c)}


@router.get("/contracts/{contract_id}/export", response_class=PlainTextResponse)
def export(contract_id: int):
    c = review.get_contract(contract_id)
    if not c:
        return "合同不存在"
    return PlainTextResponse(
        review.export_markdown(c),
        headers={"Content-Disposition": f"attachment; filename=contract-{contract_id}-review.md"},
    )


@router.get("/audit")
def audit(limit: int = 50):
    return {"logs": review.db.query_all("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,))}
