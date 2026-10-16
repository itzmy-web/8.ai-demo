"""运营助手数据层：商品 / 店铺 / 看板（SQLite，替代原 Next.js + FastAPI api + Docker 栈）。"""
from __future__ import annotations

from core import db


def list_products(keyword: str = "", platform: str = "") -> list[dict]:
    sql = "SELECT * FROM ops_products WHERE 1=1"
    params: list = []
    if keyword:
        sql += " AND name LIKE ?"
        params.append(f"%{keyword}%")
    if platform:
        sql += " AND platform=?"
        params.append(platform)
    sql += " ORDER BY id DESC"
    return db.query_all(sql, params)


def create_product(name: str, platform: str, price: float, stock: int, category: str = "") -> dict:
    pid = db.execute(
        "INSERT INTO ops_products(name, platform, price, stock, category) VALUES (?,?,?,?,?)",
        (name, platform, price, stock, category),
    )
    return db.query_one("SELECT * FROM ops_products WHERE id=?", (pid,))


def update_product(pid: int, **fields) -> dict | None:
    allowed = {"name", "platform", "price", "stock", "status", "category"}
    sets, params = [], []
    for k, v in fields.items():
        if k in allowed and v is not None:
            sets.append(f"{k}=?")
            params.append(v)
    if not sets:
        return db.query_one("SELECT * FROM ops_products WHERE id=?", (pid,))
    params.append(pid)
    db.execute(f"UPDATE ops_products SET {', '.join(sets)} WHERE id=?", params)
    return db.query_one("SELECT * FROM ops_products WHERE id=?", (pid,))


def delete_product(pid: int) -> None:
    db.execute("DELETE FROM ops_products WHERE id=?", (pid,))


def list_stores() -> list[dict]:
    return db.query_all("SELECT * FROM ops_stores ORDER BY id DESC")


def create_store(name: str, platform: str) -> dict:
    sid = db.execute(
        "INSERT INTO ops_stores(name, platform) VALUES (?,?)", (name, platform)
    )
    return db.query_one("SELECT * FROM ops_stores WHERE id=?", (sid,))


def update_store(sid: int, **fields) -> dict | None:
    allowed = {"name", "platform", "status"}
    sets, params = [], []
    for k, v in fields.items():
        if k in allowed and v is not None:
            sets.append(f"{k}=?")
            params.append(v)
    if not sets:
        return db.query_one("SELECT * FROM ops_stores WHERE id=?", (sid,))
    params.append(sid)
    db.execute(f"UPDATE ops_stores SET {', '.join(sets)} WHERE id=?", params)
    return db.query_one("SELECT * FROM ops_stores WHERE id=?", (sid,))


def delete_store(sid: int) -> None:
    db.execute("DELETE FROM ops_stores WHERE id=?", (sid,))


def dashboard() -> dict:
    products = db.query_all("SELECT * FROM ops_products")
    stores = db.query_all("SELECT * FROM ops_stores")
    total_stock_value = sum(p["price"] * p["stock"] for p in products)
    low_stock = [p for p in products if p["stock"] < 100]
    platforms: dict[str, int] = {}
    for p in products:
        platforms[p["platform"]] = platforms.get(p["platform"], 0) + 1
    for s in stores:
        platforms.setdefault(s["platform"], platforms.get(s["platform"], 0))
    return {
        "metrics": {
            "product_count": len(products),
            "store_count": len(stores),
            "active_store_count": sum(1 for s in stores if s["status"] == "active"),
            "platform_count": len(platforms),
            "total_stock_value": round(total_stock_value, 2),
            "low_stock_count": len(low_stock),
        },
        "low_stock_products": low_stock,
        "platform_distribution": [{"platform": k, "count": v} for k, v in platforms.items()],
        "price_ranking": sorted(products, key=lambda p: p["price"], reverse=True)[:5],
    }
