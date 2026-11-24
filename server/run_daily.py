# -*- coding: utf-8 -*-
"""每日主流程：采集 → 分类评分 → 入库/变更检测 → 优选 → 推送。
用法：
  python run_daily.py            # 跑完整流程（采集+推送）
  python run_daily.py --no-push  # 只采集评分入库，不推送
  python run_daily.py --dry      # 用已有数据只重算优选，不采集
"""
import argparse
import sys
import os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import load_config, ROOT
from db.store import Store
from collectors import build_collectors
from pipeline.selector import select
from pipeline.notifier import push_daily


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--dry", action="store_true", help="不采集，只用库里已有数据重算优选")
    args = ap.parse_args()

    cfg = load_config()
    db_path = os.path.join(ROOT, cfg.get("storage", {}).get("db_path", "data/listings.db"))
    store = Store(db_path)
    today = date.today().isoformat()

    if not args.dry:
        collectors = build_collectors(cfg)
        if not collectors:
            print("警告：没有启用的数据源，请检查 config.yaml sources.*.enabled")
        all_listings = []
        for c in collectors:
            print(f"\n[采集] {c.name} ...", flush=True)
            try:
                items = c.collect()
                print(f"  {c.name} 采集 {len(items)} 条", flush=True)
            except Exception as e:
                print(f"  {c.name} 失败: {str(e)[:120]}", flush=True)
                store.mark_source(c.name, f"error: {str(e)[:60]}", 0)
                items = []
            changed = 0
            for it in items:
                if store.upsert_listing(it):
                    changed += 1
            store.mark_source(c.name, "ok", len(items))
            print(f"  {c.name} 新增/变更 {changed} 条", flush=True)
            all_listings += items
    else:
        rows = store.recommendations(date="")  # 触发读取；实际全量需从 listings 查
        print("[dry] 跳过采集，使用库中数据", flush=True)

    # 全量重算优选（从库里读所有标的）
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    from common import Listing
    all_rows = [dict(r) for r in conn.execute("SELECT * FROM listings")]
    conn.close()
    listings = []
    for r in all_rows:
        l = Listing(
            source=r["source"], external_id=r["external_id"], title=r["title"] or "",
            category=r["category"] or "C", asset_type=r["asset_type"] or "",
            province=r["province"] or "", city=r["city"] or "", district=r["district"] or "",
            area_sqm=r["area_sqm"], price_yuan=r["price_yuan"], price_text=r["price_text"] or "",
            appraisal_yuan=r["appraisal_yuan"], unit_price=r["unit_price"], discount_rate=r["discount_rate"],
            deadline=r["deadline"] or "", seller=r["seller"] or "", seller_grade=r["seller_grade"] or "",
            second_listing=bool(r["second_listing"]), has_defect_note=bool(r["has_defect_note"]),
            use_type=r["use_type"] or "", url=r["url"] or "", published_at=r["published_at"] or "",
            collected_at=r["collected_at"] or "", score=r["score"] or 0,
            score_reasons=[], raw=r["raw"] or "",
            value_score=r["value_score"] if "value_score" in r.keys() else 0,
            title_score=r["title_score"] if "title_score" in r.keys() else 0,
            risk_score=r["risk_score"] if "risk_score" in r.keys() else 0,
            seller_score=r["seller_score"] if "seller_score" in r.keys() else 0,
            time_score=r["time_score"] if "time_score" in r.keys() else 0,
            market_basis=r["market_basis"] if "market_basis" in r.keys() else "",
            scoring_version=r["scoring_version"] if "scoring_version" in r.keys() else "v1",
        )
        listings.append(l)

    by_cat = select(listings, cfg)
    store.save_recommendations(today, by_cat)
    print(f"\n[优选] {today}  企业类 {len(by_cat['B'])} 条 / 个人类 {len(by_cat['C'])} 条")
    for cat in ("B", "C"):
        for i, l in enumerate(by_cat[cat][:3], 1):
            print(f"  [{cat}] {i}. {l.score}分 {l.title[:36]}")

    if args.no_push:
        print("\n[推送] 已跳过（--no-push）")
        return

    results = push_daily(cfg, today, by_cat, already_pushed_fn=store.already_pushed)
    for ch, ok in results.items():
        store.log_push(today, ch, "ok" if ok else "fail")
    print("\n[推送]", results if results else "未配置推送通道（config.yaml push.enabled=false 或缺少密钥）")


if __name__ == "__main__":
    main()
