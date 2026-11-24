# -*- coding: utf-8 -*-
"""全国土地二级市场 market.mnr.gov.cn —— 公开 API，无需登录/验证码。"""
import json
import urllib.parse
from common import Listing, to_yuan, clean_text
from .base import BaseCollector

ENDPOINTS = [
    ("转让信息", "/epf-landweb/tsell/getTransfer"),
    ("求购需求", "/epf-landweb/tpurchase/getIndexTPurchaseList"),
    ("交易结果公示", "/epf-landweb/landweb/transtarget/transNoticeOrResultList"),
    # 热门供需 pageSize 被锁 2 且翻页重复，M1 暂不采
]


class LandMarketCollector(BaseCollector):
    name = "land_market"

    def __init__(self, config: dict):
        super().__init__(config)
        self.base = config.get("base", "https://market.mnr.gov.cn/api").rstrip("/")

    def _api(self, path: str, page: int, size: int = 50) -> dict:
        url = f"{self.base}{path}?{urllib.parse.urlencode({'pageNo': page, 'pageSize': size})}"
        s = self.get(url, headers={"Referer": "https://market.mnr.gov.cn/"})
        try:
            return json.loads(s) if s else {}
        except Exception:
            return {}

    def collect(self) -> list[Listing]:
        import hashlib
        out = []
        for label, path in ENDPOINTS:
            for page in range(1, 6):
                data = self._api(path, page)
                if data.get("code") != 0:
                    break
                pager = data.get("pager", {})
                rows = pager.get("results", [])
                if not rows:
                    break
                for rec in rows:
                    def g(*keys):
                        for k in keys:
                            if rec.get(k) not in (None, "", []):
                                return rec[k]
                        return ""

                    title = clean_text(g("title", "publictTitle", "name", "tsellName", "demandTitle"))
                    price_text = str(g("price", "transPrice", "transferPrice", "listingPrice", "amount"))
                    province = clean_text(g("cantonProvinceName", "provinceName", "province"))
                    city = clean_text(g("cantonCityName", "cityName", "city"))
                    rid = str(g("id", "targetNo", "targetId", "tsellId", "tpurchaseId", "relevanceId"))
                    ext = rid or hashlib.md5((label + title).encode()).hexdigest()[:16]
                    rec_json = json.dumps(rec, ensure_ascii=False)[:1200]
                    out.append(Listing(
                        source=self.name,
                        external_id=ext,
                        title=title,
                        asset_type="土地",
                        province=province,
                        city=city,
                        district=clean_text(g("cantonAreaName", "areaName", "districtName")),
                        area_sqm=float(g("area", "square", "landArea", "useArea")) if str(g("area", "square", "landArea", "useArea") or "").replace(".", "", 1).isdigit() else None,
                        price_yuan=to_yuan(None, price_text),
                        price_text=price_text,
                        use_type=clean_text(g("firstClassUseName", "useTypeName", "landUse")),
                        published_at=str(g("releaseDate", "createTime", "insertTime", "pubDate"))[:10],
                        url="https://market.mnr.gov.cn/",
                        raw=rec_json,
                    ))
                if page >= pager.get("totalPage", 1):
                    break
                self.polite_sleep()
            self.polite_sleep()
        # 接口内去重
        seen = set(); uniq = []
        for it in out:
            if it.key in seen:
                continue
            seen.add(it.key); uniq.append(it)
        return uniq
