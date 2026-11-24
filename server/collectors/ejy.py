# -*- coding: utf-8 -*-
"""e交易 ejy365.com —— 列表静态可抓，详情静态；robots 允许 /info/。"""
import re
import html as htmlmod
from concurrent.futures import ThreadPoolExecutor, as_completed
from common import Listing, to_yuan, clean_text
from .base import BaseCollector

CATEGORY_MAP = {
    "FC": "房产", "CL": "二手车", "ESSB": "二手设备", "WZ": "闲置资产",
    "FCZZ": "招租", "GQ": "股权", "ZQ": "债权", "TD": "土地",
}


class EJyCollector(BaseCollector):
    name = "ejy"

    def __init__(self, config: dict):
        super().__init__(config)
        self.base = config.get("base", "https://www.ejy365.com").rstrip("/")
        self.categories = config.get("categories", list(CATEGORY_MAP))
        self.workers = int(config.get("max_detail_workers", 8))

    def _list_page(self, category: str, page: int, low_price: bool = True) -> list[dict]:
        order = "orderType2_up" if low_price else "orderType1"
        url = f"{self.base}/jygg_more?project_type={category}&status=START_BM&orderType={order}&page={page}"
        s = self.get(url)
        if not s:
            return []
        i = s.find('id="cqjyUl"')
        if i < 0:
            return []
        block = s[i:s.find("</ul>", i)]
        rows = []
        for li in re.findall(r"<li>(.*?)</li>", block, re.S):
            m = re.search(r"/info/(\w+)", li)
            if not m:
                continue
            code = m.group(1)
            city_m = re.search(r"<b>\[([^\]]+)\]</b>", li)
            title_m = re.search(r"<div class=\"title\">.*?<b>\[[^\]]+\]</b>(.*?)</a>", li, re.S)
            price_m = re.search(r"挂牌价[^>]*title=\"([^\"]*)\"", li)
            deadline_m = re.search(r"报名截止时间：([^<]+)", li)
            owner_m = re.search(r"挂牌方：(.*?)</div>", li, re.S)
            rows.append({
                "code": code,
                "city": clean_text(city_m.group(1)) if city_m else "",
                "title": clean_text(title_m.group(1)) if title_m else "",
                "price_text": htmlmod.unescape(price_m.group(1)) if price_m else "",
                "deadline": clean_text(deadline_m.group(1)) if deadline_m else "",
                "seller": clean_text(owner_m.group(1)) if owner_m else "",
                "asset_type": CATEGORY_MAP.get(category, category),
            })
        return rows

    def _detail(self, code: str) -> dict:
        s = self.get(f"{self.base}/info/{code}")
        d = {}
        if not s:
            return d
        # 评估价（元）
        m = re.search(r"评估价（元）\s*</td>\s*<td[^>]*>(.*?)</td>", s, re.S)
        if m:
            d["appraisal_yuan"] = to_yuan(None, clean_text(m.group(1)))
        # 建筑面积
        m = re.search(r'房屋建筑面积.*?class="money small"[^>]*title="([\d,.]+)"', s, re.S)
        if m:
            d["area_sqm"] = to_yuan(None, m.group(1))  # 纯数字
        # 二次挂牌（仅在 title 里判定，避免命中通用提示）
        tm = re.search(r"<title>(.*?)</title>", s, re.S | re.I)
        title_tag = tm.group(1) if tm else ""
        d["second_listing"] = bool(re.search(r"第[二2三四3]次|二次挂牌|再次挂牌", title_tag))
        d["has_defect_note"] = ("瑕疵" in s or "重大事项" in s)
        return d

    def collect(self) -> list[Listing]:
        # 1) 列表采集（每类默认 + 低价两种排序各若干页）
        raw = {}
        for cat in self.categories:
            for low in (True, False):
                for page in range(1, 5):
                    rows = self._list_page(cat, page, low_price=low)
                    if not rows:
                        break
                    for r in rows:
                        raw.setdefault(r["code"], r)
                    self.polite_sleep()
        # 2) 并发详情（只对有价格或房产类抓详情，控制量）
        codes = [c for c, r in raw.items() if r["price_text"] or r["asset_type"] == "房产"][:400]
        details = {}
        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            futs = {ex.submit(self._detail, c): c for c in codes}
            for fut in as_completed(futs):
                details[futs[fut]] = fut.result()

        out = []
        for code, r in raw.items():
            d = details.get(code, {})
            price = to_yuan(None, r["price_text"])
            area = d.get("area_sqm")
            appraisal = d.get("appraisal_yuan")
            unit = price / area if (price and area and area > 0) else None
            disc = price / appraisal if (price and appraisal and appraisal > 0) else None
            out.append(Listing(
                source=self.name,
                external_id=code,
                title=r["title"],
                asset_type=r["asset_type"],
                city=r["city"],
                price_yuan=price,
                price_text=r["price_text"],
                area_sqm=area,
                appraisal_yuan=appraisal,
                unit_price=unit,
                discount_rate=disc,
                deadline=r["deadline"],
                seller=r["seller"],
                second_listing=d.get("second_listing", False),
                has_defect_note=d.get("has_defect_note", False),
                url=f"{self.base}/info/{code}",
                raw="",
            ))
        return out
