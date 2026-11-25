# -*- coding: utf-8 -*-
"""人民法院诉讼资产网采集器（rmfysszc.gov.cn）。

实测结论（2026-11）：
- 列表接口 www1 域 POST /News/Handler.aspx 返回 JSON，含公告标题/法院/发布日期/详情页链接；
  www 主域的同一接口返回错误页，必须用 www1。
- 详情页 www 域 /statichtml/rm_xmdetail/{id}.shtml 是静态页，可直连，
  含起拍价/评估价/保证金/面积/权证号等，但格式杂乱（数字夹空格、万元/元混用），需归一化。
- 无验证码/token，归入 open 组，保持礼貌间隔即可。

只抓近期公告（默认 7 天内），作为每日增量；已成交/结果类由 collectors.filter 兜底。
"""
import re
import json
import html
import urllib.parse
from datetime import date, timedelta

from common import Listing, to_yuan, clean_text
from .base import BaseCollector, UA
from .filter import is_concluded

LIST_URL = "https://www1.rmfysszc.gov.cn/News/Handler.aspx"
DETAIL_RE = re.compile(r"/rm_xmdetail/(\d+)\.shtml")

# 资产类型识别（按标题关键词，顺序优先）
TYPE_RULES = [
    ("土地", r"土地使用权|国有建设用地|土地租赁"),
    ("矿业权", r"探矿权|采矿权|矿业权"),
    ("股权", r"股权|股份|出资额|股票"),
    ("债权", r"债权|应收账款|不良资产"),
    ("二手车", r"机动车|汽车|车辆|轿车|客车|货车|电瓶车|摩托车"),
    ("二手设备", r"设备|机械|机器|工程机械|仪器|生产线|可移动物品"),
    # 房产：除显式词外，还覆盖法院公告常见的"X幢X室""X号楼X层X号"写法
    # 注意不加裸"X号"，否则"手机号157…""翡翠挂件1"会被误判
    ("房产", r"房产|房屋|住宅|商品房|不动产|商铺|写字楼|厂房|门店|商住|杂物间|车位|车库|"
             r"停车用房|房地产|\d+室|\d+幢|\d+栋|号楼|\d+单元|花园|雅筑|新村|小区|"
             r"路\d+号|街\d+号|层\d+号|\d+-\d+-\d+"),
]


def _clean_num_text(s: str) -> str:
    """去掉数字中间夹的空格，如 '5 00 0' → '5000'。"""
    return re.sub(r"(?<=\d)\s+(?=\d)", "", s or "")


def _parse_price(text: str, *labels) -> float | None:
    """从详情页纯文本里抽 '起拍价：1,330,000 元' 之类，统一换算成元。"""
    t = _clean_num_text(text)
    for lab in labels:
        m = re.search(lab + r"[:：]\s*([\d,]+(?:\.\d+)?)\s*(万元|万|元)?", t)
        if not m:
            continue
        val = float(m.group(1).replace(",", ""))
        unit = m.group(2) or ""
        if "万" in unit:
            val *= 10_000
        return val
    return None


class RmfyCollector(BaseCollector):
    name = "rmfysszc"

    def __init__(self, config: dict):
        super().__init__(config)
        self.max_pages = int(config.get("max_pages", 3))
        self.max_detail = int(config.get("max_detail", 60))
        self.fresh_days = int(config.get("fresh_days", 7))
        self.last_block_reason = ""

    def _fetch_list(self, page: int) -> list[dict]:
        """取一页公告列表，返回 [{id,title,court,date,url}]。"""
        body = urllib.parse.urlencode({
            "search": "", "fid1": "", "fid2": "", "fid3": "",
            "page": str(page), "include": "0",
        }).encode("ascii")
        req = urllib.request.Request(
            LIST_URL, data=body,
            headers={**UA, "Referer": "https://www1.rmfysszc.gov.cn/News/Pmgg.shtml",
                     "X-Requested-With": "XMLHttpRequest"},
        )
        import ssl
        try:
            raw = urllib.request.urlopen(req, timeout=40, context=ssl._create_unverified_context()).read().decode("utf-8", "ignore")
            d = json.loads(raw)
        except Exception as e:
            self.last_block_reason = f"list p{page} error: {str(e)[:60]}"
            return []
        h = d.get("html", "")
        out = []
        for tr in re.findall(r"<tr class='listtr'>(.*?)</tr>", h, re.S):
            m = DETAIL_RE.search(tr)
            if not m:
                continue
            a = re.search(r"title='([^']*)'", tr)
            title = html.unescape(a.group(1)) if a else ""
            # 法院：带 title 属性的 span
            court = ""
            cm = re.search(r"class='n_c_l'[^>]*title='([^']*)'", tr)
            if cm:
                court = html.unescape(cm.group(1))
            dm = re.search(r"class='n_c_r'[^>]*>([\d.]+)<", tr)
            pub = dm.group(1).replace(".", "-") if dm else ""
            out.append({
                "id": m.group(1),
                "title": clean_text(title),
                "court": court,
                "date": pub,
                "url": f"https://www.rmfysszc.gov.cn/statichtml/rm_xmdetail/{m.group(1)}.shtml",
            })
        return out

    def _fetch_detail(self, url: str) -> str:
        h = self.get(url, timeout=40)
        if not h:
            return ""
        t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", h, flags=re.S)
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t))).strip()

    def collect(self) -> list[Listing]:
        self.last_block_reason = ""
        cutoff = (date.today() - timedelta(days=self.fresh_days)).isoformat()
        rows, seen = [], set()
        for page in range(1, self.max_pages + 1):
            got = self._fetch_list(page)
            if not got:
                break
            # 已到 cutoff 之前则停止翻页（列表按日期倒序）
            older = [r for r in got if r["date"] and r["date"] < cutoff]
            fresh = [r for r in got if not r["date"] or r["date"] >= cutoff]
            for r in fresh:
                if r["id"] not in seen:
                    seen.add(r["id"])
                    rows.append(r)
            self.polite_sleep()
            if len(older) >= len(got) / 2:
                break
        if not rows:
            return []

        out = []
        for r in rows[: self.max_detail]:
            text = self._fetch_detail(r["url"])
            self.polite_sleep()
            title = r["title"]
            price = _parse_price(text, "起拍价")
            appraisal = _parse_price(text, "评估价", "市场价")
            deposit = _parse_price(text, "保证金")
            area_m = re.search(r"面积[:：]\s*([\d,]+(?:\.\d+)?)\s*平方米", _clean_num_text(text))
            area = float(area_m.group(1).replace(",", "")) if area_m else None
            use_m = re.search(r"(?:房屋)?(?:批准)?用途[:：]\s*([^,，。；;]{2,12})", text)
            cert_m = re.search(r"(?:产权证号|权证号)[:：]\s*([^,，。；;]{4,40})", text)
            asset = "其他"
            for t, pat in TYPE_RULES:
                if re.search(pat, title):
                    asset = t
                    break
            second = "第二次拍卖" in title or "二次拍卖" in title
            idx = r["id"]
            l = Listing(
                source=self.name, external_id=f"rmfy{idx}", title=title,
                asset_type=asset, price_yuan=price, appraisal_yuan=appraisal,
                area_sqm=area, use_type=clean_text(use_m.group(1)) if use_m else "",
                seller=r["court"], seller_grade="法院", second_listing=second,
                has_defect_note=("瑕疵" in text),
                published_at=r["date"], url=r["url"],
                price_text=(f"起拍{int(price)}元" if price else (f"保证金{int(deposit)}元" if deposit else "")),
                raw=(cert_m.group(0)[:80] if cert_m else ""),
            )
            if l.area_sqm and l.price_yuan:
                l.unit_price = round(l.price_yuan / l.area_sqm, 2)
            if l.appraisal_yuan and l.price_yuan:
                l.discount_rate = round(l.price_yuan / l.appraisal_yuan, 3)
            if not is_concluded(l):
                out.append(l)
        return out
