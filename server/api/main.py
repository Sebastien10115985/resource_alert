# -*- coding: utf-8 -*-
"""FastAPI：供 Android App 拉取推荐/变更/统计。
启动：uvicorn api.main:app --host 0.0.0.0 --port 8000 （在 server 目录下）
"""
import os
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from common import load_config, ROOT, Listing
from api.admin import router as admin_router

app = FastAPI(title="闲置资源优选 API", version="0.1.0-M1")
app.include_router(admin_router)

# M1 本地调试：允许局域网任意来源；正式上线收紧为具体域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_cfg = load_config()
DB_PATH = os.path.join(ROOT, _cfg.get("storage", {}).get("db_path", "data/listings.db"))


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _row_to_dict(r) -> dict:
    d = dict(r)
    d["id"] = f"{d['source']}:{d['external_id']}"
    import json
    try:
        d["score_reasons"] = json.loads(d.get("score_reasons") or "[]")
    except Exception:
        d["score_reasons"] = []
    # bool 字段
    for k in ("second_listing", "has_defect_note"):
        d[k] = bool(d.get(k))
    return d


@app.get("/api/recommendations")
def recommendations(
    date: str = Query(default=""),
    category: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    c = _conn()
    where, args = ["1=1"], []
    if date:
        where.append("r.date=?"); args.append(date)
    else:
        row = c.execute("SELECT MAX(date) FROM recommendations").fetchone()
        where.append("r.date=?"); args.append(row[0] or "")
    if category:
        where.append("r.category=?"); args.append(category)
    total = c.execute(
        f"SELECT COUNT(*) FROM recommendations r JOIN listings l ON l.id=r.listing_id WHERE {' AND '.join(where)}",
        args,
    ).fetchone()[0]
    rows = c.execute(
        f"""SELECT l.* FROM recommendations r JOIN listings l ON l.id=r.listing_id
            WHERE {' AND '.join(where)} ORDER BY r.rank ASC LIMIT ? OFFSET ?""",
        args + [page_size, (page - 1) * page_size],
    ).fetchall()
    c.close()
    return {
        "date": date or _latest_date(),
        "items": [_row_to_dict(r) for r in rows],
        "total": total,
        "page": page,
    }


def _latest_date():
    c = _conn(); r = c.execute("SELECT MAX(date) FROM recommendations").fetchone(); c.close()
    return r[0] or ""


@app.get("/api/listings/{listing_id}")
def listing_detail(listing_id: str):
    c = _conn(); r = c.execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone(); c.close()
    if not r:
        return {"error": "not found"}
    return _row_to_dict(r)


@app.get("/api/changes")
def changes(days: int = Query(default=7, ge=1, le=90)):
    c = _conn()
    rows = c.execute(
        """SELECT c.*, l.title, l.url FROM listing_changes c
           LEFT JOIN listings l ON l.id=c.listing_id ORDER BY c.changed_at DESC LIMIT ?""",
        (days * 50,),
    ).fetchall()
    c.close()
    return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.get("/api/stats")
def stats():
    c = _conn()
    total = c.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    sources = []
    for r in c.execute("SELECT name, last_run, status, item_count FROM sources"):
        sources.append(dict(r))
    c.close()
    return {"today": total, "sources": sources}


@app.get("/health")
def health():
    return {"status": "ok"}
