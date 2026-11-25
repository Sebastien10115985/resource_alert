# -*- coding: utf-8 -*-
"""全国公共资源交易平台 ggzy.gov.cn 采集器（反爬组，低频轮询）。

实测（2026-11-24/25）：
- 列表页 deal/dealList.html 静态框架，数据走 POST
  /information/pubTradingInfo/getTradList，带验证码机制（code 829）
  与限流（code 800/801）；直连多次返回错误页或要求 token，**不硬闯**。
- 详情页 /information/deal/html/... 是静态 HTML，可直连，含标题/正文。

策略：
1) 每次任务先探测列表接口：拿到结构化数据就用（正常路径）；
   遇到验证码/限流/错误页，立即放弃并记录原因，返回空，交给调度器冷却 2 分钟后再试。
2) 不缓存伪造数据。抓不到就是抓不到，绝不把筛选项数字当价格。
"""
import re
import json
import urllib.parse

from common import Listing, clean_text, to_yuan
from .base import BaseCollector

LIST_PAGE = "https://www.ggzy.gov.cn/deal/dealList.html"
LIST_API = "https://www.ggzy.gov.cn/information/pubTradingInfo/getTradList"

# 只看机会类：0301 土地出让公示 / 0501 国有产权挂牌披露
BUSINESS_TYPES = ["0301", "0501"]
BLOCK_CODES = {829, 800, 801, 804}   # 验证码 / 限流 / 参数错误


class GGzyCollector(BaseCollector):
    name = "ggzy"

    def __init__(self, config: dict):
        super().__init__(config)
        self.base = config.get("base", "https://www.ggzy.gov.cn")
        self.page_size = int(config.get("page_size", 20))
        self.max_pages = int(config.get("max_pages", 1))
        self.detail_limit = int(config.get("detail_limit", 10))
        self.last_block_reason = ""

    def _probe_list(self, btype: str, page: int) -> tuple[list[dict], str]:
        """探测列表接口。返回 (records, block_reason)。被限流返回 ([], 原因)。"""
        body = urllib.parse.urlencode({
            "PAGENUMBER": page,
            "PAGESIZE": self.page_size,
            "HEADER_DEAL_TYPE": btype,
            "TIMEBEGIN": "", "TIMEEND": "",
            "FINDTXT": "", "AREACODE": "", "PLATFORMCODE": "",
        })
        html = self.get(
            LIST_API,
            headers={"Referer": LIST_PAGE, "Content-Type": "application/x-www-form-urlencoded",
                     "X-Requested-With": "XMLHttpRequest"},
            retry=0, timeout=25,
        )
        if not html:
            return [], "列表接口不可达(HTTP错误/风控)"
        # 网关拦截返回 HTML 错误页而非 JSON
        if "<html" in html[:500].lower() or not html.lstrip().startswith(("{", "[")):
            return [], "列表接口被网关拦截(非JSON)"
        try:
            data = json.loads(html)
        except Exception:
            return [], "列表接口返回无法解析"
        code = data.get("code")
        if code in BLOCK_CODES or code not in (None, 0, 200):
            return [], f"列表接口风控/错误(code={code})"
        # 兼容多种返回结构
        rows = (data.get("data") or {}).get("records") or data.get("records") \
            or (data.get("data") or {}).get("list") or data.get("list") or []
        if not isinstance(rows, list):
            return [], "列表结构未知"
        return rows, ""

    def _detail(self, url: str) -> dict:
        """详情页直连，提取金额/面积/二次挂牌等。"""
        out = {}
        html = self.get(url, headers={"Referer": LIST_PAGE}, retry=0, timeout=25)
        if not html:
            return out
        txt = clean_text(html)
        for key, pat in [
            ("挂牌价", r"(?:挂牌价|转让底价|起始价|起拍价)[^\d]{0,12}([\d,]+(?:\.\d+)?)\s*万?元?"),
            ("评估价", r"评估价[^\d]{0,12}([\d,]+(?:\.\d+)?)\s*万?元?"),
            ("面积", r"([\d,]+(?:\.\d+)?)\s*(?:平方米|㎡)"),
        ]:
            m = re.search(pat, txt)
            if m:
                out[key] = m.group(1)
        out["second"] = bool(re.search(r"第二次|第2次|二次挂牌|再次挂牌|轮巡", txt))
        return out

    def collect(self) -> list[Listing]:
        all_rows = []          # (btype, row) 保留每行所属业务类型
        reasons = []
        for btype in BUSINESS_TYPES:
            for page in range(1, self.max_pages + 1):
                rows, reason = self._probe_list(btype, page)
                if reason:
                    reasons.append(f"{btype}/p{page}:{reason}")
                    self.polite_sleep()
                    break  # 该类型被限流，不再翻页换其他类型
                if not rows:
                    break
                all_rows.extend((btype, r) for r in rows)
                self.polite_sleep()

        self.last_block_reason = "；".join(reasons[:4])
        if not all_rows:
            # 优雅降级：不伪造数据，返回空让调度器冷却后重试
            return []

        out = []
        for btype, r in all_rows[:self.detail_limit]:
            title = clean_text(r.get("TITLE") or r.get("title") or r.get("INFOTITLE") or "")
            url = r.get("URL") or r.get("url") or r.get("LINKURL") or ""
            if url and url.startswith("/"):
                url = self.base + url
            if not title or not url:
                continue
            d = self._detail(url) if url else {}
            price_text = d.get("挂牌价", "")
            price = to_yuan(price_text + "万元") if price_text else None
            area = None
            if d.get("面积"):
                try:
                    area = float(d["面积"].replace(",", ""))
                except ValueError:
                    pass
            atype = "土地" if str(r.get("HEADER_DEAL_TYPE") or btype).startswith("03") else "房产"
            l = Listing(
                source=self.name, external_id=self._ext_id(url), title=title,
                asset_type=atype, url=url,
                province=clean_text(r.get("AREANAME") or r.get("PROVINCE") or ""),
                published_at=clean_text(r.get("SHOWTIME") or r.get("TIME") or ""),
                price_yuan=price, price_text=price_text, area_sqm=area,
                second_listing=d.get("second", False),
                raw=json.dumps(r, ensure_ascii=False)[:2000],
            )
            out.append(l)
            self.polite_sleep()
        return out

    @staticmethod
    def _ext_id(url: str) -> str:
        m = re.search(r"/([0-9a-f]{32})\.html?", url)
        return m.group(1) if m else re.sub(r"\W+", "_", url)[-60:]
