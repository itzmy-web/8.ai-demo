"""SQLite 存储层：连接管理 + 建表 + 通用 CRUD。

全工作台统一持久化（替代原四项目的 MySQL / Mongo / Milvus / MinIO），
单文件 data/fusion.db，云端沙箱零外部依赖。
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any, Iterable

from config import DB_PATH

_lock = threading.Lock()

SCHEMA = """
-- 知识库文档与分块（RAG 智库）
CREATE TABLE IF NOT EXISTS kb_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    source TEXT DEFAULT 'upload',
    size INTEGER DEFAULT 0,
    chunks INTEGER DEFAULT 0,
    status TEXT DEFAULT 'indexed',
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);
CREATE TABLE IF NOT EXISTS kb_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL
);
-- 中文检索：bigram 展开后存入（unicode61 对连续中文不切词）
CREATE VIRTUAL TABLE IF NOT EXISTS kb_chunks_fts USING fts5(text, tokenize='unicode61');
CREATE TABLE IF NOT EXISTS kb_qa_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    refs TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 合同审查（合同审批）
CREATE TABLE IF NOT EXISTS contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    biz_type TEXT DEFAULT 'procurement',
    text TEXT NOT NULL,
    applicant TEXT DEFAULT '业务经办人',
    risk_level TEXT DEFAULT 'none',
    summary TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);
CREATE TABLE IF NOT EXISTS contract_risks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id INTEGER NOT NULL,
    risk_id TEXT,
    title TEXT,
    clause_type TEXT,
    level TEXT,
    reason TEXT,
    legal_basis TEXT,
    snippet TEXT,
    suggestion TEXT,
    by_llm INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    operator TEXT DEFAULT '',
    role TEXT DEFAULT '',
    comment TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT DEFAULT '',
    role TEXT DEFAULT '',
    action TEXT DEFAULT '',
    target TEXT DEFAULT '',
    detail TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 智能客服会话（电商小二）
CREATE TABLE IF NOT EXISTS cs_sessions (
    sender_id TEXT PRIMARY KEY,
    history TEXT DEFAULT '[]',
    active_task TEXT DEFAULT NULL,
    slots TEXT DEFAULT '{}',
    flow_id TEXT DEFAULT NULL,
    step_id TEXT DEFAULT NULL,
    last_active REAL DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);
CREATE TABLE IF NOT EXISTS cs_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id TEXT NOT NULL,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    track TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 运营助手（商品 / 店铺 / 看板 / Agent / 工作流）
CREATE TABLE IF NOT EXISTS ops_products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    platform TEXT DEFAULT 'taobao',
    price REAL DEFAULT 0,
    stock INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    category TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);
CREATE TABLE IF NOT EXISTS ops_stores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    platform TEXT DEFAULT 'taobao',
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);
CREATE TABLE IF NOT EXISTS ops_agent_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent TEXT NOT NULL,
    task TEXT NOT NULL,
    status TEXT DEFAULT 'running',
    result TEXT DEFAULT '',
    steps TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);
CREATE TABLE IF NOT EXISTS ops_workflows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    trigger TEXT DEFAULT 'manual',
    steps TEXT DEFAULT '[]',
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db():
    with _lock:
        conn = get_conn()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def init_db() -> None:
    with db() as conn:
        conn.executescript(SCHEMA)
        _seed(conn)


def bigram_expand(text: str) -> str:
    """中文按二元切分（重叠 bigram），英文/数字按词切分，空格连接供 FTS5 匹配。"""
    tokens: list[str] = []
    for seg in re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+", text or ""):
        if seg[0].isascii() and seg[0].isalnum():
            if len(seg) > 1:
                tokens.append(seg)
            continue
        if len(seg) == 1:
            tokens.append(seg)
        else:
            tokens.extend(seg[i : i + 2] for i in range(len(seg) - 1))
    return " ".join(tokens)


def _seed(conn: sqlite3.Connection) -> None:
    """首次启动灌入演示数据（四模块均可空手演示）。"""
    if conn.execute("SELECT COUNT(*) c FROM ops_products").fetchone()["c"] == 0:
        products = [
            ("无线降噪耳机 Pro", "taobao", 899.0, 320, "active", "数码"),
            ("智能扫地机器人 X2", "jd", 2599.0, 56, "active", "家电"),
            ("便携蓝牙音箱 Mini", "taobao", 299.0, 890, "active", "数码"),
            ("4K 高清投影仪 H1", "jd", 3299.0, 12, "active", "家电"),
            ("运动智能手表 S7", "pdd", 699.0, 430, "active", "穿戴"),
        ]
        conn.executemany(
            "INSERT INTO ops_products(name, platform, price, stock, status, category) VALUES (?,?,?,?,?,?)",
            products,
        )
    if conn.execute("SELECT COUNT(*) c FROM ops_stores").fetchone()["c"] == 0:
        stores = [
            ("品牌官方旗舰店", "taobao", "active"),
            ("京东自营专区", "jd", "active"),
            ("拼多多品牌馆", "pdd", "active"),
            ("抖音商城直播间", "douyin", "active"),
        ]
        conn.executemany(
            "INSERT INTO ops_stores(name, platform, status) VALUES (?,?,?)",
            stores,
        )
    if conn.execute("SELECT COUNT(*) c FROM ops_workflows").fetchone()["c"] == 0:
        conn.execute(
            "INSERT INTO ops_workflows(name, trigger, steps, enabled) VALUES (?,?,?,?)",
            ("每日库存巡检", "daily", json.dumps(["拉取商品库存", "低于阈值标记", "生成补货建议"], ensure_ascii=False), 1),
        )
        conn.execute(
            "INSERT INTO ops_workflows(name, trigger, steps, enabled) VALUES (?,?,?,?)",
            ("竞品价格追踪", "hourly", json.dumps(["抓取竞品链接", "比价分析", "推送调价建议"], ensure_ascii=False), 1),
        )


def query_all(sql: str, params: Iterable[Any] = ()) -> list[dict]:
    with db() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
        return [dict(r) for r in rows]


def query_one(sql: str, params: Iterable[Any] = ()) -> dict | None:
    with db() as conn:
        row = conn.execute(sql, tuple(params)).fetchone()
        return dict(row) if row else None


def execute(sql: str, params: Iterable[Any] = ()) -> int:
    with db() as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.lastrowid or 0


def audit(actor: str, role: str, action: str, target: str = "", detail: str = "") -> None:
    execute(
        "INSERT INTO audit_logs(actor, role, action, target, detail) VALUES (?,?,?,?,?)",
        (actor, role, action, target, detail),
    )
