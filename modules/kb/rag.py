"""RAG 智库模块（移植自 D:/knowledge_base 掌柜智库）。

云端轻量化实现：
- 原 Milvus + BGE embedding → SQLite FTS5 全文检索（BM25）
- 原 MinIO/Mongo → SQLite 单文件
- LLM 问答保留，无 Key 时降级为「检索摘录 + 拼接回答」演示模式
"""
from __future__ import annotations

import re
import time

from core import db, llm

CHUNK_SIZE = 380
CHUNK_OVERLAP = 60


def split_text(text: str) -> list[str]:
    """按段落聚合切块（优先段落边界，超长按句子硬切）。"""
    text = re.sub(r"\r\n?", "\n", text).strip()
    if not text:
        return []
    paras = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paras:
        if len(buf) + len(p) + 1 <= CHUNK_SIZE:
            buf = f"{buf}\n{p}" if buf else p
            continue
        if buf:
            chunks.append(buf)
            buf = ""
        while len(p) > CHUNK_SIZE:
            # 超长段落按句号硬切，保留重叠
            cut = CHUNK_SIZE
            for sep in ("。", "；", ".", ";", "\n"):
                idx = p.rfind(sep, 0, CHUNK_SIZE)
                if idx > CHUNK_SIZE // 2:
                    cut = idx + 1
                    break
            chunks.append(p[:cut])
            p = p[max(0, cut - CHUNK_OVERLAP):]
        buf = p
    if buf:
        chunks.append(buf)
    return [c.strip() for c in chunks if c.strip()]


def add_document(name: str, text: str, source: str = "upload") -> dict:
    chunks = split_text(text)
    doc_id = db.execute(
        "INSERT INTO kb_documents(name, source, size, chunks, status) VALUES (?,?,?,?, 'indexed')",
        (name, source, len(text), len(chunks)),
    )
    for i, c in enumerate(chunks):
        with db.db() as conn:
            cur = conn.execute(
                "INSERT INTO kb_chunks(doc_id, chunk_index, text) VALUES (?,?,?)",
                (doc_id, i, c),
            )
            conn.execute(
                "INSERT INTO kb_chunks_fts(rowid, text) VALUES (?,?)",
                (cur.lastrowid, db.bigram_expand(c)),
            )
    return {"id": doc_id, "name": name, "chunks": len(chunks)}


def list_documents() -> list[dict]:
    return db.query_all("SELECT * FROM kb_documents ORDER BY id DESC")


def delete_document(doc_id: int) -> None:
    with db.db() as conn:
        rows = conn.execute("SELECT id FROM kb_chunks WHERE doc_id=?", (doc_id,)).fetchall()
        for r in rows:
            conn.execute("DELETE FROM kb_chunks_fts WHERE rowid=?", (r["id"],))
        conn.execute("DELETE FROM kb_documents WHERE id=?", (doc_id,))
        conn.execute("DELETE FROM kb_chunks WHERE doc_id=?", (doc_id,))


def search(query: str, top_k: int = 4) -> list[dict]:
    """FTS5 BM25 检索（中文 bigram 展开）；查询词做安全转义。"""
    expanded = db.bigram_expand(query)
    if not expanded.strip():
        return []
    match = " OR ".join(f'"{t}"' for t in expanded.split() if t)
    try:
        rows = db.query_all(
            """
            SELECT c.id, c.doc_id, c.text, d.name AS doc_name,
                   bm25(kb_chunks_fts) AS score
            FROM kb_chunks_fts f
            JOIN kb_chunks c ON c.id = f.rowid
            JOIN kb_documents d ON d.id = c.doc_id
            WHERE kb_chunks_fts MATCH ?
            ORDER BY score LIMIT ?
            """,
            (match, top_k),
        )
    except Exception:
        rows = []
    if not rows:  # 降级：LIKE
        like = f"%{query}%"
        rows = db.query_all(
            """
            SELECT c.id, c.doc_id, c.text, d.name AS doc_name, 0.0 AS score
            FROM kb_chunks c JOIN kb_documents d ON d.id = c.doc_id
            WHERE c.text LIKE ? LIMIT ?
            """,
            (like, top_k),
        )
    return rows


async def ask(question: str, top_k: int = 4) -> dict:
    t0 = time.time()
    refs = search(question, top_k)
    if not refs:
        return {
            "question": question,
            "answer": "知识库中还没有找到相关内容。请先在「文档导入」中上传资料，或换一个问法试试。",
            "refs": [],
            "mode": "empty",
            "elapsed_ms": int((time.time() - t0) * 1000),
        }
    context = "\n\n---\n\n".join(
        f"【资料：{r['doc_name']} · 片段{r['id']}】\n{r['text']}" for r in refs
    )
    ref_list = [{"doc": r["doc_name"], "text": r["text"][:120]} for r in refs]
    if llm.enabled():
        try:
            answer = await llm.chat(
                [
                    {"role": "system", "content": "你是企业知识库问答助手。严格依据下方资料回答，资料中没有的信息不要编造；回答末尾列出引用资料名。"},
                    {"role": "user", "content": f"资料：\n{context}\n\n问题：{question}"},
                ],
                temperature=0.2,
            )
            return {
                "question": question, "answer": answer, "refs": ref_list,
                "mode": "llm", "elapsed_ms": int((time.time() - t0) * 1000),
            }
        except Exception as e:  # noqa: BLE001
            answer = f"（LLM 调用失败，已降级为检索摘录：{e}）\n\n"
    else:
        answer = "（演示模式：未配置 LLM，以下为知识库检索摘录）\n\n"
    answer += "\n\n".join(f"◆ {r['text']}" for r in refs[:2])
    return {
        "question": question, "answer": answer, "refs": ref_list,
        "mode": "demo", "elapsed_ms": int((time.time() - t0) * 1000),
    }


def qa_history(limit: int = 20) -> list[dict]:
    return db.query_all("SELECT * FROM kb_qa_history ORDER BY id DESC LIMIT ?", (limit,))


def save_qa(question: str, answer: str, refs: list) -> None:
    import json

    db.execute(
        "INSERT INTO kb_qa_history(question, answer, refs) VALUES (?,?,?)",
        (question, answer[:2000], json.dumps(refs, ensure_ascii=False)),
    )
