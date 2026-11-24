# -*- coding: utf-8 -*-
"""SQLite 存储层：建表、upsert、变更检测、查询。M1 用本地 SQLite，上量后换云数据库只改这一层。"""
import os
import sys
import sqlite3
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import Listing, now_iso, ROOT

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    category TEXT,
    asset_type TEXT,
    title TEXT,
    province TEXT, city TEXT, district TEXT,
    area_sqm REAL, price_yuan REAL, price_text TEXT,
    appraisal_yuan REAL, unit_price REAL, discount_rate REAL,
    deadline TEXT, seller TEXT, seller_grade TEXT,
    second_listing INTEGER DEFAULT 0, has_defect_note INTEGER DEFAULT 0,
    use_type TEXT, url TEXT, published_at TEXT, collected_at TEXT,
    score INTEGER DEFAULT 0, score_reasons TEXT, raw TEXT,
    value_score REAL DEFAULT 0, title_score REAL DEFAULT 0,
    risk_score REAL DEFAULT 0, seller_score REAL DEFAULT 0, time_score REAL DEFAULT 0,
    score_detail TEXT, market_basis TEXT DEFAULT '', scoring_version TEXT DEFAULT 'v1',
    UNIQUE(source, external_id)
);
CREATE INDEX IF NOT EXISTS idx_listings_cat ON listings(category);
CREATE INDEX IF NOT EXISTS idx_listings_score ON listings(score);

CREATE TABLE IF NOT EXISTS listing_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id TEXT, field TEXT, old TEXT, new TEXT, changed_at TEXT
);

CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT, category TEXT, listing_id TEXT, rank INTEGER, score INTEGER
);

CREATE TABLE IF NOT EXISTS push_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT, channel TEXT, status TEXT, detail TEXT
);

CREATE TABLE IF NOT EXISTS sources (
    name TEXT PRIMARY KEY, last_run TEXT, status TEXT, item_count INTEGER
);
"""

# 参与变更检测的字段
WATCH_FIELDS = ["price_yuan", "deadline", "title"]


class Store:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self):
        """旧库补列：Schema 新增字段时平滑升级，不丢历史数据。"""
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(listings)")}
        additions = {
            "value_score": "REAL DEFAULT 0",
            "title_score": "REAL DEFAULT 0",
            "risk_score": "REAL DEFAULT 0",
            "seller_score": "REAL DEFAULT 0",
            "time_score": "REAL DEFAULT 0",
            "score_detail": "TEXT",
            "market_basis": "TEXT DEFAULT ''",
            "scoring_version": "TEXT DEFAULT 'v1'",
        }
        for name, decl in additions.items():
            if name not in cols:
                self.conn.execute(f"ALTER TABLE listings ADD COLUMN {name} {decl}")

    def upsert_listing(self, listing: Listing) -> bool:
        """写入或更新标的。返回 True 表示有新变更（新增或 WATCH_FIELDS 变化）。"""
        d = listing.to_dict()
        lid = d["id"]
        old = self.conn.execute("SELECT * FROM listings WHERE id=?", (lid,)).fetchone()
        changed = False

        if old is None:
            self._insert(d)
            self._log_change(lid, "status", "", "新增", listing.collected_at)
            changed = True
        else:
            for f in WATCH_FIELDS:
                newv = d.get(f)
                oldv = old[f]
                # 数值型按数值比较（容忍浮点/单位差异）
                if f == "price_yuan":
                    if newv is not None and oldv is not None and abs(float(newv) - float(oldv)) > 0.01:
                        self._log_change(lid, f, str(oldv), str(newv), listing.collected_at)
                        changed = True
                elif newv and str(newv) != str(oldv):
                    self._log_change(lid, f, str(oldv), str(newv), listing.collected_at)
                    changed = True
            self._update(d)

        self.conn.commit()
        return changed

    def _insert(self, d: dict):
        d = dict(d)
        # SQLite 不支持 list/dict，JSON 序列化
        for k in ("score_reasons", "score_detail"):
            if isinstance(d.get(k), (list, dict)):
                d[k] = json.dumps(d[k], ensure_ascii=False)
        if isinstance(d.get("raw"), (list, dict)):
            d["raw"] = json.dumps(d["raw"], ensure_ascii=False)
        cols = [k for k in d.keys() if k != "id"]
        cols = ["id"] + cols
        ph = ",".join("?" for _ in cols)
        self.conn.execute(
            f"INSERT OR REPLACE INTO listings ({','.join(cols)}) VALUES ({ph})",
            [d.get(c) for c in cols],
        )

    def _update(self, d: dict):
        self._insert(d)  # INSERT OR REPLACE 即更新

    def _log_change(self, lid, field, old, new, at):
        self.conn.execute(
            "INSERT INTO listing_changes (listing_id,field,old,new,changed_at) VALUES (?,?,?,?,?)",
            (lid, field, old, new, at),
        )

    def save_recommendations(self, date: str, items_by_cat: dict):
        self.conn.execute("DELETE FROM recommendations WHERE date=?", (date,))
        for cat, items in items_by_cat.items():
            for rank, it in enumerate(items, 1):
                lid = it.to_dict()["id"]
                self.conn.execute(
                    "INSERT INTO recommendations (date,category,listing_id,rank,score) VALUES (?,?,?,?,?)",
                    (date, cat, lid, rank, it.score),
                )
                # 回写评分与理由到 listings，供 API/App 展示
                self.conn.execute(
                    """UPDATE listings SET score=?, score_reasons=?, category=?,
                       value_score=?, title_score=?, risk_score=?, seller_score=?, time_score=?,
                       score_detail=?, market_basis=?, scoring_version=? WHERE id=?""",
                    (
                        it.score, json.dumps(it.score_reasons, ensure_ascii=False), cat,
                        getattr(it, "value_score", 0), getattr(it, "title_score", 0),
                        getattr(it, "risk_score", 0), getattr(it, "seller_score", 0),
                        getattr(it, "time_score", 0),
                        json.dumps(getattr(it, "score_detail", {}), ensure_ascii=False),
                        getattr(it, "market_basis", ""), getattr(it, "scoring_version", "v1"),
                        lid,
                    ),
                )
        self.conn.commit()

    def recommendations(self, date: str = "", category: str = "") -> list:
        sql = """SELECT l.* FROM recommendations r JOIN listings l ON l.id=r.listing_id WHERE 1=1"""
        args = []
        if date:
            sql += " AND r.date=?"; args.append(date)
        if category:
            sql += " AND r.category=?"; args.append(category)
        sql += " ORDER BY r.rank ASC"
        return [dict(x) for x in self.conn.execute(sql, args).fetchall()]

    def latest_date(self) -> str:
        r = self.conn.execute("SELECT MAX(date) FROM recommendations").fetchone()
        return r[0] or ""

    def changes(self, days: int = 7) -> list:
        sql = """SELECT c.*, l.title, l.url FROM listing_changes c
                 LEFT JOIN listings l ON l.id=c.listing_id
                 ORDER BY c.changed_at DESC LIMIT ?"""
        return [dict(x) for x in self.conn.execute(sql, (days * 50,)).fetchall()]

    def stats(self) -> dict:
        total = self.conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        by_src = {}
        for r in self.conn.execute("SELECT source, COUNT(*) n, MAX(collected_at) t FROM listings GROUP BY source"):
            by_src[r["source"]] = {"item_count": r["n"], "last_run": r["t"]}
        return {"total": total, "sources": by_src}

    def mark_source(self, name: str, status: str, count: int):
        self.conn.execute(
            "INSERT INTO sources (name,last_run,status,item_count) VALUES (?,?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET last_run=excluded.last_run,status=excluded.status,item_count=excluded.item_count",
            (name, now_iso(), status, count),
        )
        self.conn.commit()

    def already_pushed(self, date: str, channel: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM push_log WHERE date=? AND channel=? AND status='ok' LIMIT 1",
            (date, channel),
        ).fetchone() is not None

    def log_push(self, date: str, channel: str, status: str, detail: str = ""):
        self.conn.execute(
            "INSERT INTO push_log (date,channel,status,detail) VALUES (?,?,?,?)",
            (date, channel, status, detail[:500]),
        )
        self.conn.commit()
