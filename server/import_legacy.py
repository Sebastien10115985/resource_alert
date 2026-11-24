# -*- coding: utf-8 -*-
"""把前两天已采的真实 CSV 导入新库（M1 冷启动数据），验证整条链路。
数据源：旧工作目录 output/ 下的 ejy / market_mnr / ky CSV。
用法：python import_legacy.py [旧目录路径]
"""
import os
import sys
import csv
import json
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Listing, load_config, to_yuan, num, ROOT
from db.store import Store

DEFAULT_LEGACY = r"C:\Users\lvhe\WorkBuddy\2026-11-23-10-29-43\output"


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def import_ejy(legacy_dir, store):
    lst = read_csv(os.path.join(legacy_dir, "ejy_list.csv"))
    detail = {r["标的编号"]: r for r in read_csv(os.path.join(legacy_dir, "ejy_detail.csv"))}
    house = {r["标的编号"]: r for r in read_csv(os.path.join(legacy_dir, "ejy_house.csv"))}
    cat_map = {"房地产": "房产", "二手车": "二手车", "二手设备": "二手设备", "闲置资产": "闲置资产",
               "资产招租": "招租", "股权": "股权", "债权": "债权", "土地使用权": "土地"}
    n = 0
    for r in lst:
        code = r.get("标的编号", "")
        if not code:
            continue
        d = {**detail.get(code, {}), **house.get(code, {})}
        price_text = r.get("挂牌价", "")
        price = to_yuan(None, price_text)
        appraisal = None
        raw_ep = d.get("评估价", "")
        v = num(raw_ep)
        if v and v > 0:
            appraisal = v
        area_v = num(d.get("建筑面积", ""))
        area = area_v if area_v and area_v > 0 else None
        unit = price / area if (price and area) else None
        disc = price / appraisal if (price and appraisal) else None
        deadline = r.get("报名截止", "")
        dm = re.search(r"(20\d{2}-\d{2}-\d{2})", deadline)
        title = r.get("标题", "")
        l = Listing(
            source="ejy", external_id=code, title=title,
            asset_type=cat_map.get(r.get("标的类型", ""), r.get("标的类型", "") or "其他"),
            city=r.get("城市", ""), price_yuan=price, price_text=price_text,
            area_sqm=area, appraisal_yuan=appraisal, unit_price=unit, discount_rate=disc,
            deadline=dm.group(1) if dm else "", seller=r.get("挂牌方", ""),
            second_listing=bool(re.search(r"第[二2三四3]次|二次挂牌|再次", title)),
            has_defect_note=str(d.get("有瑕疵提示", "")) == "1",
            url=r.get("链接", ""), raw=json.dumps(d, ensure_ascii=False)[:1000],
        )
        store.upsert_listing(l); n += 1
    return n


def import_land(legacy_dir, store):
    rows = read_csv(os.path.join(legacy_dir, "market_mnr_listings.csv"))
    n = 0
    for r in rows:
        title = r.get("标题", "")
        if not title:
            continue
        rid = r.get("ID", "") or title[:20]
        price_text = r.get("价格", "")
        area_v = num(r.get("面积(㎡)", ""))
        l = Listing(
            source="land_market", external_id=str(rid), title=title, asset_type="土地",
            province=r.get("省份", ""), city=r.get("城市", ""), district=r.get("区县", ""),
            area_sqm=area_v, price_yuan=to_yuan(None, price_text), price_text=price_text,
            use_type=r.get("用途", ""), published_at=(r.get("发布日期", "") or "")[:10],
            url="https://market.mnr.gov.cn/", raw=r.get("原始字段", "")[:1000],
        )
        store.upsert_listing(l); n += 1
    return n


def import_mining(legacy_dir, store):
    rows = read_csv(os.path.join(legacy_dir, "ky_notices.csv"))
    n = 0
    for r in rows:
        url = r.get("链接", "")
        if not url:
            continue
        title = r.get("标题", "")
        l = Listing(
            source="mining", external_id=re.sub(r"\W", "", url)[-40:],
            title=title, asset_type="矿业权",
            use_type=r.get("类型", ""), published_at=r.get("日期", ""), url=url,
        )
        store.upsert_listing(l); n += 1
    return n


def main():
    legacy = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_LEGACY
    cfg = load_config()
    db_path = os.path.join(ROOT, cfg.get("storage", {}).get("db_path", "data/listings.db"))
    store = Store(db_path)
    counts = {
        "ejy": import_ejy(legacy, store),
        "land_market": import_land(legacy, store),
        "mining": import_mining(legacy, store),
    }
    for name, c in counts.items():
        store.mark_source(name, "imported_legacy", c)
    print("导入完成：", counts, "合计", sum(counts.values()))


if __name__ == "__main__":
    main()
