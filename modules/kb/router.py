"""RAG 智库路由。"""
from __future__ import annotations

from fastapi import APIRouter, Form, UploadFile

from . import rag

router = APIRouter(tags=["RAG智库"])


@router.get("/documents")
def documents():
    return {"documents": rag.list_documents()}


@router.post("/documents/text")
def add_text(name: str = Form(...), text: str = Form(...)):
    doc = rag.add_document(name=name, text=text)
    return {"ok": True, "document": doc}


@router.post("/documents/upload")
async def upload(file: UploadFile):
    raw = await file.read()
    for enc in ("utf-8", "gbk", "gb18030"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="ignore")
    doc = rag.add_document(name=file.filename or "未命名文档", text=text)
    return {"ok": True, "document": doc}


@router.delete("/documents/{doc_id}")
def remove(doc_id: int):
    rag.delete_document(doc_id)
    return {"ok": True}


@router.get("/ask")
async def ask(question: str, top_k: int = 4):
    result = await rag.ask(question, top_k)
    if result.get("mode") != "empty":
        rag.save_qa(result["question"], result["answer"], result["refs"])
    return result


@router.get("/history")
def history():
    return {"history": rag.qa_history()}
