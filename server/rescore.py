# -*- coding: utf-8 -*-
"""用当前评分算法重算全库分数并回写（不重新采集）。

用法：
  python rescore.py            # 全量重算
  python rescore.py --limit 5  # 只算前 5 条并打印明细，用于抽查调参
"""
import argparse
import os
import sys
import json
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import load_config, ROOT, Listing
from pipeline.value_scorer import score_listing_v2, build_market_baseline
from pipeline.classifier import classify
from db.store import Store


def row_to_listing(r: dict) -> Listing:
    keys = r.keys()
    def g(k, default=None):
        return r[k] if k in keys else default
    reasons = []
    try:
        reasons = json.loads(g("score_reasons") or "[]")
    except Exception:
        pass
    return Listing(
        source=g("source", ""), external_id=g("external_id", ""), title=g("title") or "",
        category=g("category") or "C", asset_type=g("asset_type") or "",
        province=g("province") or "", city=g("city") or "", district=g("district") or "",
        area_sqm=g("area_sqm"), price_yuan=g("price_yuan"), price_text=g("price_text") or "",
        appraisal_yuan=g("appraisal_yuan"), unit_price=g("unit_price"), discount_rate=g("discount_rate"),
        deadline=g("deadline") or "", seller=g("seller") or "", seller_grade=g("seller_grade") or "",
        second_listing=bool(g("second_listing")), has_defect_note=bool(g("has_defect_note")),
        use_type=g("use_type") or "", url=g("url") or "", published_at=g("published_at") or "",
        collected_at=g("collected_at") or "", score=g("score") or 0,
        score_reasons=reasons, raw=g("raw") or "",
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 条并打印明细")
    args = ap.parse_args()

    cfg = load_config()
    db_path = os.path.join(ROOT, cfg.get("storage", {}).get("db_path", "data/listings.db"))
    Store(db_path)  # 确保新列存在（迁移）
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM listings")]
    listings = [row_to_listing(r) for r in rows]
    baseline = build_market_baseline(listings)
    bc = float(cfg.get("filter", {}).get("bc_threshold_wan", 300))

    scored = []
    for l in listings:
        l.category = classify(l, bc)
        score_listing_v2(l, cfg, baseline)
        l.scoring_version = "v2"
        scored.append(l)

    if args.limit:
        for l in scored[:args.limit]:
            print(f"\n[{l.score}] {l.asset_type} | {l.title[:40]}")
            print("  明细:", l.score_detail, "| 基准:", l.market_basis)
            print("  理由:", "；".join(l.score_reasons))
        conn.close()
        return

    # 回写全库
    conn.executemany(
        """UPDATE listings SET score=?, score_reasons=?, value_score=?, title_score=?,
           risk_score=?, seller_score=?, time_score=?, score_detail=?,
           market_basis=?, scoring_version=? WHERE id=?""",
        [
            (
                l.score, json.dumps(l.score_reasons, ensure_ascii=False),
                l.value_score, l.title_score, l.risk_score, l.seller_score, l.time_score,
                json.dumps(l.score_detail, ensure_ascii=False), l.market_basis, "v2",
                f"{l.source}:{l.external_id}",
            )
            for l in scored
        ],
    )
    # 先提交并断开上面的连接，避免与 Store 的新连接互相锁库
    conn.commit()
    conn.close()

    # 重算后刷新当日推荐的分数（排名按新分重排）
    from pipeline.selector import select
    from datetime import date
    today = date.today().isoformat()
    by_cat = select(scored, cfg)
    store = Store(db_path)
    store.save_recommendations(today, by_cat)

    # 统计摘要
    avg = sum(l.score for l in scored) / len(scored) if scored else 0
    high = sum(1 for l in scored if l.score >= 80)
    low = sum(1 for l in scored if l.score < 40)
    print(f"重算完成：{len(scored)} 条，均分 {avg:.1f}，≥80分 {high} 条，<40分 {low} 条")
    for cat in ("B", "C"):
        print(f"  [{cat}] Top3:")
        for i, l in enumerate(by_cat[cat][:3], 1):
            print(f"    {i}. {l.score}分 {l.asset_type} | {l.title[:36]}")


if __name__ == "__main__":
    main()
