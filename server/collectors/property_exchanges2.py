# -*- coding: utf-8 -*-
"""第三批省级产权交易机构采集器（2026-11-26 实测接入）。

- fujian_cqjy   福建省产权交易中心     首页多栏目表格 → 静态详情页补价
- qingdao_cqjy  青岛产权交易所         /api/dpm/web/pro/{sys}/home → JSON
- tianjin_cqjy  天津产权交易中心       trade.tpre.cn .../project-info → JSON
- shenyang_cqjy 沈阳联合产权交易所     静态列表 xmgg.htm（编号/标题/日期）

接入前均低频探测过首页与列表接口；不登录、不绕验证码。
"""
import json
import re
import urllib.parse

from common import Listing, to_yuan, clean_text
from .base import BaseCollector, UA, CTX
from .filter import filter_concluded
from .property_exchanges import _ExchangeBase, guess_type, fmt_date, strip_tags, fetch_bytes


class _ProvBase(_ExchangeBase):
    """共用收尾：补来源机构、结果过滤。"""
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
            out.append(l)
        kept, removed = filter_concluded(out)
        if removed:
            print(f"  [{self.name}] 过滤已成交/结果公示 {removed} 条", flush=True)
        return kept


# ---------------- 福建省产权交易中心 ----------------

class FujianCollector(_ProvBase):
    name = "fujian_cqjy"
    org_name = "福建省产权交易中心"

    def __init__(self, config: dict):
        super().__init__(config)
        self.base = config.get("base", "https://www.fjcqjy.com").rstrip("/")
        self.max_detail = int(config.get("max_detail", 40))

    def _list(self) -> list[dict]:
        """首页多个栏目表格：项目编号 / 标题 / 发布时间 / 详情链接。"""
        try:
            html = fetch_bytes(self.base + "/").decode("utf-8", "ignore")
        except Exception:
            return []
        out, seen = [], set()
        # 每行：<td>编号</td><td><a href=... title=...>标题</a></td><td class=time>日期</td>
        for block in re.findall(r"<tr>(.*?)</tr>", html, re.S | re.I):
            m = re.search(
                r"<td[^>]*>\s*(?:<span[^>]*>)?\s*([A-Z0-9]{6,20})\s*(?:</span>)?\s*</td>"
                r".*?<a[^>]*href=\"([^\"]+)\"[^>]*title=\"([^\"]*)\""
                r".*?<td[^>]*class=\"time\"[^>]*>\s*(\d{4}-\d{2}-\d{2})",
                block, re.S | re.I)
            if not m:
                continue
            code, url, title, when = m.groups()
            if code in seen:
                continue
            seen.add(code)
            if url.startswith("/"):
                url = self.base + url
            out.append({"code": code, "title": clean_text(title),
                        "url": url, "date": when})
        return out

    def _detail(self, url: str) -> dict:
        """站内静态详情页：项目基本信息表（挂牌价/起止日期/发布机构）。"""
        if "fjcqjy.com" not in url:
            return {}  # 外链子站（泉州/厦门等）不深抓，避免触及其他站策略
        try:
            html = fetch_bytes(url).decode("utf-8", "ignore")
        except Exception:
            return {}
        text = strip_tags(html)
        d = {}
        m = re.search(r"挂牌价\s*([\d,]+(?:\.\d+)?)\s*(万元|元)?", text)
        if m and "详见公告" not in text[max(0, m.start()-6):m.start()]:
            v = float(m.group(1).replace(",", ""))
            d["price_yuan"] = v * 10000 if "万" in (m.group(2) or "") else v
        m = re.search(r"挂牌开始日期\s*(\d{4}-\d{2}-\d{2})", text)
        if m:
            d["published_at"] = m.group(1)
        m = re.search(r"挂牌结束日期\s*(\d{4}-\d{2}-\d{2})", text)
        if m:
            d["deadline"] = m.group(1)
        m = re.search(r"发布机构\s*([^\s]{2,30})", text)
        if m:
            d["seller"] = clean_text(m.group(1))
        m = re.search(r"建筑面积\s*([\d,]+(?:\.\d+)?)\s*(?:㎡|平方米)", text)
        if m:
            d["area_sqm"] = float(m.group(1).replace(",", ""))
        d["has_defect_note"] = "瑕疵" in text
        return d

    def collect(self) -> list[Listing]:
        rows = self._list()
        self.polite_sleep()
        print(f"  [{self.name}] 首页栏目去重 {len(rows)} 条", flush=True)
        out = []
        for r in rows[: self.max_detail]:
            d = self._detail(r["url"])
            self.polite_sleep()
            out.append(Listing(
                source=self.name, external_id=r["code"], title=r["title"],
                asset_type=guess_type(r["title"]),
                price_yuan=d.get("price_yuan"),
                area_sqm=d.get("area_sqm"),
                published_at=d.get("published_at") or r["date"],
                deadline=d.get("deadline", ""),
                seller=d.get("seller", ""), seller_grade="",
                has_defect_note=d.get("has_defect_note", False),
                url=r["url"], raw=r["code"],
            ))
        return self._finish(out)


# ---------------- 青岛产权交易所 ----------------

class QingdaoCollector(_ProvBase):
    name = "qingdao_cqjy"
    org_name = "青岛产权交易所"

    def __init__(self, config: dict):
        super().__init__(config)
        self.base = config.get("base", "https://www.qdcq.net").rstrip("/")
        # zbxsoft：source 走路径前缀 /api/dpm，缺了会报 Source must not be null
        self.api = config.get("api", self.base + "/api/dpm/web/pro/{sys}/home")
        self.systems = config.get("systems", ["utrg", "utrm", "utrz", "utrl", "utri"])
        self.pages = int(config.get("pages", 2))
        self.rows = int(config.get("rows", 20))

    def _page(self, sys: str, page: int) -> list[dict]:
        url = self.api.format(sys=sys) + "?" + urllib.parse.urlencode({
            "rows": self.rows, "page": page, "proStatus": "allNotException"})
        try:
            html = fetch_bytes(url, {"Referer": self.base + "/"}).decode("utf-8", "ignore")
            return (json.loads(html).get("rows") or [])
        except Exception:
            return []

    def collect(self) -> list[Listing]:
        rows, seen = [], set()
        for sys in self.systems:
            for p in range(1, self.pages + 1):
                got = self._page(sys, p)
                if not got:
                    break
                for r in got:
                    code = clean_text(r.get("jcNo")) or clean_text(r.get("proCode"))
                    if not code or code in seen:
                        continue
                    seen.add(code)
                    rows.append(r)
                self.polite_sleep()
        out = []
        for r in rows:
            title = clean_text(r.get("proName"))
            if not title:
                continue
            # 实测：proPrice="78229700.000000"（字符串）而 priceUnit 标"万元"，但 7822 万元
            # 股权才合理；前端 toWan(v)=v/10000 证明原始值就是元（单位标注有误），故直接取元。
            raw_price = r.get("proPrice")
            try:
                pv = float(raw_price) if raw_price not in (None, "") else None
            except (TypeError, ValueError):
                pv = None
            price_yuan = pv if pv and pv > 0 else None
            price_text = f"{price_yuan:.2f}元" if price_yuan else ""
            pid = clean_text(r.get("proId"))
            out.append(Listing(
                source=self.name,
                external_id=clean_text(r.get("jcNo")) or clean_text(r.get("proCode")),
                title=title, asset_type=guess_type(title),
                price_yuan=price_yuan, price_text=price_text,
                published_at=fmt_date(r.get("realPubStartTime")),
                deadline=fmt_date(r.get("realPubEndTime")),
                seller="", seller_grade="",
                second_listing=bool(re.search(r"第[二2三四3]次|再次挂牌|重新挂牌", title)),
                url=f"{self.base}/qd/detail/pro/{pid}" if pid else "",
                raw=" | ".join(x for x in [clean_text(r.get("sysName")),
                                           clean_text(r.get("proArea"))] if x),
            ))
        return self._finish(out)


# ---------------- 天津产权交易中心 ----------------

class TianjinCollector(_ProvBase):
    name = "tianjin_cqjy"
    org_name = "天津产权交易中心"

    def __init__(self, config: dict):
        super().__init__(config)
        self.api = config.get(
            "api", "https://trade.tpre.cn/up/biz/up-data-view/anmuas/project-info")
        # 与官网首页 JS 一致的 8 个业务系统
        self.systems = config.get("systems", [
            "ENTERPRISE_ASSETS", "PROPERTY_RIGHT_TRANSFER",
            "ENTERPRISE_CAPITAL_INCREASE", "ENTERPRISE_INVESTMENT_ATTRACTION",
            "JS", "FINANCE", "LEASE", "SMALL_COMMODITY"])
        self.pages = int(config.get("pages", 2))
        self.size = int(config.get("size", 20))

    def _page(self, sys: str, page: int) -> list[dict]:
        url = self.api + "?" + urllib.parse.urlencode({
            "current": page, "size": self.size, "systemCode": sys})
        try:
            html = fetch_bytes(url, {"Referer": "https://www.tpre.cn/"}).decode("utf-8", "ignore")
            return ((json.loads(html).get("data") or {}).get("records") or [])
        except Exception:
            return []

    def collect(self) -> list[Listing]:
        rows, seen = [], set()
        for sys in self.systems:
            for p in range(1, self.pages + 1):
                got = self._page(sys, p)
                if not got:
                    break
                for r in got:
                    # 已成交/结果类由 filter_concluded 兜底，这里先按状态过滤
                    status = clean_text(r.get("projectStatus"))
                    if status and "DISCLOSED" not in status.upper() and "披露" not in status:
                        continue
                    code = clean_text(r.get("uniqueIdentification")) or clean_text(r.get("projectCode"))
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
            price_text = clean_text(r.get("price"))
            unit = clean_text(r.get("priceUnit"))
            price_yuan = to_yuan(price_text, unit) if price_text else None
            city = " ".join(x for x in [clean_text(r.get("addressProvince")),
                                        clean_text(r.get("addressCity")),
                                        clean_text(r.get("addressCounty"))] if x)
            out.append(Listing(
                source=self.name,
                external_id=clean_text(r.get("uniqueIdentification")) or clean_text(r.get("projectCode")),
                title=title, asset_type=guess_type(title),
                price_yuan=price_yuan, price_text=f"{price_text}{unit}" if price_text else "",
                published_at=fmt_date(r.get("startTime")),
                deadline=fmt_date(r.get("endTime")),
                city=city,
                seller=clean_text(r.get("transferorName")), seller_grade="",
                url=clean_text(r.get("projectLink")),
                raw=" | ".join(x for x in [clean_text(r.get("systemName")),
                                           clean_text(r.get("bizTypeName"))] if x),
            ))
        return self._finish(out)


# ---------------- 沈阳联合产权交易所 ----------------

class ShenyangCollector(_ProvBase):
    name = "shenyang_cqjy"
    org_name = "沈阳联合产权交易所"

    def __init__(self, config: dict):
        super().__init__(config)
        self.base = config.get("base", "https://www.sprtc.com").rstrip("/")
        self.list_path = config.get("list_path", "/gghz1/xmgg.htm")
        self.pages = int(config.get("pages", 3))

    def _page(self, page: int) -> list[dict]:
        # 第 1 页 /gghz1/xmgg.htm，后续 /gghz1/xmgg/{N}.htm
        path = self.list_path if page == 1 else self.list_path.replace(".htm", f"/{page}.htm")
        try:
            html = fetch_bytes(self.base + path).decode("utf-8", "ignore")
        except Exception:
            return []
        out = []
        # <a href="...qrtwo.htm?id=..."><p>标题</p><span class="date">2026-11-25
        for m in re.finditer(
            r'<a[^>]*href="([^"]*qrtwo\.htm\?id=[^"]+)"[^>]*>\s*<p>(.*?)</p>\s*'
            r'<span[^>]*class="date"[^>]*>\s*(\d{4}-\d{2}-\d{2})',
            html, re.S | re.I):
            url, title, when = m.groups()
            if url.startswith("/"):
                url = self.base + url
            elif not url.startswith("http"):
                url = self.base + "/index/" + url.lstrip("./")
            out.append({"id": clean_text(re.search(r"id=([^&]+)", url).group(1)) if "id=" in url else title,
                        "title": clean_text(title), "date": when, "url": url})
        return out

    def collect(self) -> list[Listing]:
        rows, seen = [], set()
        for p in range(1, self.pages + 1):
            got = self._page(p)
            if not got:
                break
            for r in got:
                if r["id"] in seen:
                    continue
                seen.add(r["id"])
                rows.append(r)
            self.polite_sleep()
        out = []
        for r in rows:
            title = r["title"]
            if not title:
                continue
            out.append(Listing(
                source=self.name, external_id=r["id"], title=title,
                asset_type=guess_type(title),
                published_at=r["date"], url=r["url"], raw=r["id"],
            ))
        return self._finish(out)
