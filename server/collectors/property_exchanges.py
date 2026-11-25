# -*- coding: utf-8 -*-
"""第二批国资委认定产权交易机构采集器。

已接入（公开接口/静态列表，实测 2026-11-25）：
- wuhan_ovupre  武汉光谷联合产权交易所  GET  /index/new_getxxmm.html  → JSON
- qinghai_cqjy  青海省产权交易市场      GET  /item.do?para=viewlist   → GBK HTML
- guizhou_cqjy  贵州阳光产权交易所      GET  /project/index.php       → HTML
- shenzhen_sotcbb 深圳联合产权交易所    POST /api/v1/sotcbb/local/project/list → JSON
- xiamen_cqjy   厦门产权交易中心        POST /cms/article/query        → JSON

未接入（站点策略限制，保持人工查看，不绕验证码/不伪造）：
- gansu_cqjy    www.gscq.com.cn        本机出口持续 403（WAF）
- dalian_cqjy   www.daee.cn            zbxsoft 接口要求 source 参数，公开页未暴露
- henan_zycqjy  www.zycqjy.com         同上
内蒙古/黑龙江/新疆等在 e交易 子站上，由现有 ejy 采集器覆盖，不重复接入。
"""
import re
import html as htmlmod
import json
import ssl
import urllib.parse
import urllib.request

from common import Listing, to_yuan, clean_text
from .base import BaseCollector, UA, CTX
from .filter import filter_concluded

# ---------------- 通用工具 ----------------

TYPE_RULES = [
    ("土地", r"土地使用权|国有建设用地|土地租赁|土地经营权"),
    ("矿业权", r"探矿权|采矿权|矿业权"),
    ("股权", r"股权|股份|出资额|增资|股票"),
    ("债权", r"债权|应收账款|不良资产|资产包"),
    ("二手车", r"机动车|汽车|车辆|轿车|客车|货车|电瓶车|摩托车|越野车"),
    ("二手设备", r"设备|机械|机器|仪器|生产线|机床|资产处置|报废"),
    ("招租", r"招租|租赁|出租|承租"),
    ("房产", r"房产|房屋|住宅|商品房|不动产|商铺|写字楼|厂房|门店|商住|车位|车库|"
             r"房地产|\d+室|\d+幢|\d+栋|号楼|新村|小区|大厦|楼宇"),
]


def guess_type(title: str) -> str:
    for asset, pat in TYPE_RULES:
        if re.search(pat, title or ""):
            return asset
    return "闲置资产"


def fmt_date(s) -> str:
    """20261125 / 2026-11-25 / '2026-11-24 00:00:00' → YYYY-MM-DD。"""
    s = str(s or "").strip()
    m = re.search(r"(\d{4})[-/年]?(\d{1,2})[-/月]?(\d{1,2})", s)
    if not m:
        return ""
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def strip_tags(s: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", s or "", flags=re.S | re.I)
    return re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def fetch_bytes(url: str, headers: dict | None = None, timeout: int = 30) -> bytes:
    h = {**UA, **(headers or {})}
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout, context=CTX) as r:
        return r.read(1500000)


class _ExchangeBase(BaseCollector):
    """共用：来源机构名、卖家等级、结果过滤。"""
    org_name = "产权交易机构"

    def _finish(self, items: list[Listing]) -> list[Listing]:
        out = []
        for l in items:
            l.seller = l.seller or self.org_name
            l.seller_grade = l.seller_grade or "产权机构"
            if l.area_sqm and l.price_yuan:
                l.unit_price = round(l.price_yuan / l.area_sqm, 2)
            if l.appraisal_yuan and l.price_yuan:
                l.discount_rate = round(l.price_yuan / l.appraisal_yuan, 3)
            if l.published_at and not l.deadline:
                pass
            out.append(l)
        kept, removed = filter_concluded(out)
        if removed:
            print(f"  [{self.name}] 过滤已成交/结果公示 {removed} 条", flush=True)
        return kept


# ---------------- 武汉光谷联合产权交易所 ----------------

class WuhanCollector(_ExchangeBase):
    name = "wuhan_ovupre"
    org_name = "武汉光谷联合产权交易所"

    def __init__(self, config: dict):
        super().__init__(config)
        self.base = config.get("base", "https://ovupre.com").rstrip("/")
        self.indexes = config.get("indexes", [2, 1, 3])  # 2=实物资产 1=产权转让 3=增资
        self.pages = int(config.get("pages", 2))
        self.page_size = int(config.get("page_size", 20))

    def _page(self, index: int, page: int) -> list[dict]:
        url = (f"{self.base}/index/new_getxxmm.html?pageSize={self.page_size}"
               f"&pageNo={page}&index={index}")
        try:
            raw = fetch_bytes(url, {"Referer": f"{self.base}/list/85.html?type=new"})
            return json.loads(raw.decode("utf-8", "ignore")).get("rows", [])
        except Exception:
            return []

    def collect(self) -> list[Listing]:
        rows, seen = [], set()
        for idx in self.indexes:
            for p in range(1, self.pages + 1):
                got = self._page(idx, p)
                if not got:
                    break
                for r in got:
                    code = clean_text(r.get("XMBH"))
                    if not code or code in seen:
                        continue
                    seen.add(code)
                    rows.append(r)
                self.polite_sleep()
        out = []
        for r in rows:
            title = clean_text(r.get("XMMC"))
            if not title:
                continue
            price_text = clean_text(r.get("ZRDJ"))
            url = clean_text(r.get("URL"))
            out.append(Listing(
                source=self.name, external_id=clean_text(r.get("XMBH")),
                title=title, asset_type=guess_type(title),
                price_yuan=to_yuan(None, price_text), price_text=price_text,
                published_at=fmt_date(r.get("KSRQ")), deadline=fmt_date(r.get("JSRQ")),
                url=url, raw=price_text,
            ))
        return self._finish(out)


# ---------------- 青海省产权交易市场 ----------------

class QinghaiCollector(_ExchangeBase):
    name = "qinghai_cqjy"
    org_name = "青海省产权交易市场"

    def __init__(self, config: dict):
        super().__init__(config)
        self.base = config.get("base", "http://www.qhcqjy.com").rstrip("/")
        self.ass_list = config.get("ass_list", ["01", "02", "03", "07", "16"])
        self.pages = int(config.get("pages", 2))
        self.max_detail = int(config.get("max_detail", 60))

    def _get(self, url: str) -> str:
        try:
            return fetch_bytes(url).decode("gbk", "ignore")
        except Exception:
            return ""

    def _list(self, ass: str, page: int) -> list[dict]:
        url = f"{self.base}/item.do?para=viewlist&classCode=3001&ass={ass}&page={page}"
        s = self._get(url)
        out = []
        for m in re.finditer(
            r'<A\s+title="([^"]+)"\s+href="(/item\.do\?para=viewcontent&id=(\d+)[^"]*)"', s, re.I
        ):
            out.append({"title": htmlmod.unescape(m.group(1)),
                        "url": self.base + htmlmod.unescape(m.group(2)), "id": m.group(3)})
        return out

    def _detail(self, url: str) -> dict:
        t = strip_tags(self._get(url))
        d = {}
        m = re.search(r"(?:挂牌价格|挂牌价|转让底价)[：:]\s*([\d,]+(?:\.\d+)?)\s*(万元|元)?", t)
        if m:
            val = float(m.group(1).replace(",", ""))
            d["price_yuan"] = val * 10000 if "万" in (m.group(2) or "") else val
        m = re.search(r"评估价(?:格)?[：:]\s*([\d,]+(?:\.\d+)?)\s*(万元|元)?", t)
        if m:
            val = float(m.group(1).replace(",", ""))
            d["appraisal_yuan"] = val * 10000 if "万" in (m.group(2) or "") else val
        m = re.search(r"建筑面积[：:]\s*([\d,]+(?:\.\d+)?)\s*平方米", t)
        if m:
            d["area_sqm"] = float(m.group(1).replace(",", ""))
        d["has_defect_note"] = "瑕疵" in t
        return d

    def collect(self) -> list[Listing]:
        rows, seen = [], set()
        for ass in self.ass_list:
            for p in range(1, self.pages + 1):
                got = self._list(ass, p)
                if not got:
                    break
                for r in got:
                    if r["id"] not in seen:
                        seen.add(r["id"])
                        rows.append(r)
                self.polite_sleep()
        out = []
        for r in rows[: self.max_detail]:
            d = self._detail(r["url"])
            self.polite_sleep()
            out.append(Listing(
                source=self.name, external_id=f"qh{r['id']}", title=r["title"],
                asset_type=guess_type(r["title"]),
                price_yuan=d.get("price_yuan"), appraisal_yuan=d.get("appraisal_yuan"),
                area_sqm=d.get("area_sqm"), has_defect_note=d.get("has_defect_note", False),
                url=r["url"], raw=d.get("price_note", ""),
            ))
        return self._finish(out)


# ---------------- 贵州阳光产权交易所 ----------------

class GuizhouCollector(_ExchangeBase):
    name = "guizhou_cqjy"
    org_name = "贵州阳光产权交易所"

    def __init__(self, config: dict):
        super().__init__(config)
        self.base = config.get("base", "https://www.prechina.net").rstrip("/")
        self.pages = int(config.get("pages", 3))

    def _list(self, page: int) -> list[dict]:
        url = f"{self.base}/project/index.php?class1=2&page={page}" if page > 1 else f"{self.base}/project/"
        try:
            s = fetch_bytes(url).decode("utf-8", "ignore")
        except Exception:
            return []
        out = []
        for block in re.findall(r'<li class="media[^"]*">(.*?)</li>', s, re.S):
            m = re.search(r'href="(?:\.\./)?project/project(\d+)\.html"[^>]*title="([^"]*)"', block, re.I)
            if not m:
                m = re.search(r'href="(?:\.\./)?project/project(\d+)\.html"', block, re.I)
                title_m = re.search(r"<h4>.*?<a[^>]*>(.*?)</a>", block, re.S | re.I)
                title = clean_text(title_m.group(1)) if title_m else ""
            else:
                title = clean_text(htmlmod.unescape(m.group(2)))
            if not m:
                continue
            pid = m.group(1)
            num = re.search(r"项目编号[：:]\s*([^<\s]+)", block)
            price = re.search(r"挂牌价[：:]\s*([\d,]+(?:\.\d+)?)", block)
            when = re.search(r"(?:挂牌时间|公告时间)[：:]\s*(\d{4}-\d{2}-\d{2})", block)
            out.append({
                "id": pid, "title": title,
                "code": clean_text(num.group(1)) if num else "",
                "price_yuan": to_yuan(price.group(1)) if price else None,
                "published_at": when.group(1) if when else "",
                "url": f"{self.base}/project/project{pid}.html",
            })
        return out

    def collect(self) -> list[Listing]:
        rows, seen = [], set()
        for p in range(1, self.pages + 1):
            got = self._list(p)
            if not got:
                break
            for r in got:
                if r["id"] not in seen:
                    seen.add(r["id"])
                    rows.append(r)
            self.polite_sleep()
        out = []
        for r in rows:
            title = r["title"]
            if not title or re.search(r"成交|结果", title):
                continue
            out.append(Listing(
                source=self.name, external_id=r["code"] or f"gz{r['id']}", title=title,
                asset_type=guess_type(title), price_yuan=r["price_yuan"],
                published_at=r["published_at"], url=r["url"], raw=r["code"],
            ))
        return self._finish(out)


# ---------------- 深圳联合产权交易所 ----------------

class ShenzhenCollector(_ExchangeBase):
    name = "shenzhen_sotcbb"
    org_name = "深圳联合产权交易所"

    def __init__(self, config: dict):
        super().__init__(config)
        self.api = config.get("api", "https://www.sotcbb.com/api/v1/sotcbb/local/project/list")
        self.pages = int(config.get("pages", 3))
        self.page_size = int(config.get("page_size", 20))

    def _page(self, page: int) -> list[dict]:
        body = {
            "channelIds": [], "targetColumnIds": ["3226"],
            "projectMoneyRanges": [], "projectSubjections": [], "projectSources": [],
            "projectStatus": None, "releaseTimeBegin": None, "releaseTimeEnd": None,
            "title": None, "pageNum": page, "pageSize": self.page_size, "dataType": 1,
        }
        try:
            req = urllib.request.Request(
                self.api, data=json.dumps(body).encode("utf-8"),
                headers={**UA, "Content-Type": "application/json",
                         "Referer": "https://www.sotcbb.com/xmgg"},
            )
            raw = urllib.request.urlopen(req, timeout=30, context=CTX).read().decode("utf-8", "ignore")
            return (json.loads(raw).get("data") or {}).get("content") or []
        except Exception:
            return []

    def collect(self) -> list[Listing]:
        rows, seen = [], set()
        for p in range(1, self.pages + 1):
            got = self._page(p)
            if not got:
                break
            for r in got:
                code = clean_text(r.get("projectNo")) or str(r.get("contentId") or "")
                if not code or code in seen:
                    continue
                seen.add(code)
                rows.append(r)
            self.polite_sleep()
        out = []
        for r in rows:
            title = clean_text(r.get("title"))
            if not title:
                continue
            price_text = clean_text(r.get("listingPriceUnits") or r.get("listingPrice"))
            cid = r.get("contentId")
            out.append(Listing(
                source=self.name, external_id=clean_text(r.get("projectNo")) or f"sz{cid}",
                title=title, asset_type=guess_type(title),
                price_yuan=to_yuan(price_text), price_text=price_text,
                published_at=fmt_date(r.get("registerFrom")), deadline=fmt_date(r.get("registerTo")),
                city=clean_text(r.get("targetRegion")),
                seller=self.org_name, seller_grade="产权机构",
                second_listing=bool(re.search(r"第[二2三四3]次|再次挂牌|重新挂牌", title)),
                url=f"https://www.sotcbb.com/projectDetails.htm?contentId={cid}",
                raw=clean_text(r.get("projectBusiness")),
            ))
        return self._finish(out)


# ---------------- 厦门产权交易中心 ----------------

class XiamenCollector(_ExchangeBase):
    name = "xiamen_cqjy"
    org_name = "厦门产权交易中心"

    def __init__(self, config: dict):
        super().__init__(config)
        self.api = config.get("api", "https://www.xemas.com.cn/cms/article/query")
        self.root_uid = config.get("root_uid", "a22482fe-5ddb-44a2-af49-ebbc22c1d29b")
        self.pages = int(config.get("pages", 3))
        self.page_size = int(config.get("page_size", 20))

    def _page(self, page: int) -> list[dict]:
        body = {
            "categorys": [self.root_uid + "getProgeniture"],
            "dataQuerys": {}, "orderBy": "userdefine1", "orderType": "desc",
        }
        url = (f"{self.api}?size={self.page_size}&page={page}"
               f"&getData=true&getResource=true")
        try:
            req = urllib.request.Request(
                url, data=json.dumps(body).encode("utf-8"),
                headers={**UA, "Content-Type": "application/json",
                         "Referer": "https://www.xemas.com.cn/project-announcement.html"},
            )
            raw = urllib.request.urlopen(req, timeout=30, context=CTX).read().decode("utf-8", "ignore")
            return (json.loads(raw).get("body") or {}).get("content") or []
        except Exception:
            return []

    def collect(self) -> list[Listing]:
        rows, seen = [], set()
        for p in range(0, self.pages):
            got = self._page(p)
            if not got:
                break
            for r in got:
                uid = r.get("uid")
                if not uid or uid in seen:
                    continue
                seen.add(uid)
                rows.append(r)
            self.polite_sleep()
        out = []
        for r in rows:
            title = clean_text(r.get("title"))
            if not title:
                continue
            data = r.get("data") or {}
            price_text = clean_text(data.get("listingPrice"))
            seller = clean_text(data.get("sellerName"))
            out.append(Listing(
                source=self.name, external_id=r["uid"], title=title,
                asset_type=guess_type(clean_text(r.get("categoryName")) + title),
                price_yuan=to_yuan(price_text), price_text=price_text,
                published_at=fmt_date(r.get("userdefine3")), deadline=fmt_date(r.get("userdefine5")),
                seller=seller or self.org_name, seller_grade="产权机构" if not seller else "",
                has_defect_note=("瑕疵" in strip_tags(str(r.get("userdefine7") or ""))),
                url=f"https://www.xemas.com.cn/project-announcement-details-new.html?uid={r['uid']}",
                raw=clean_text(data.get("no")),
            ))
        return self._finish(out)
