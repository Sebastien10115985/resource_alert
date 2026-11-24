# -*- coding: utf-8 -*-
"""矿业权市场 ky.mnr.gov.cn —— 静态 HTML + index_N.html 分页。"""
import re
import urllib.parse
from common import Listing, clean_text
from .base import BaseCollector
from .filter import filter_concluded

# 只保留"机会"栏目：出让公告 + 转让公示。
# jggs/jjgs、jggs/ckjjgs 是"出让结果公示"（已成交），对发现机会无价值，不采集。
COLS = {
    "kyqcrgg/tkq/": ("探矿权", "出让公告"),
    "kyqcrgg/ckq/": ("采矿权", "出让公告"),
    "zrgs/tkzrgs/": ("探矿权", "转让公示"),
    "zrgs/ckzrgs/": ("采矿权", "转让公示"),
}
LINK_RE = re.compile(r'href=["\']([^"\']*t20\d{6}_\d+\.htm)["\'][^>]*>([^<]{6,150})')


class MiningCollector(BaseCollector):
    name = "mining"

    def __init__(self, config: dict):
        super().__init__(config)
        self.base = config.get("base", "https://ky.mnr.gov.cn/")
        self.max_pages = int(config.get("max_pages_per_column", 3))

    def collect(self) -> list[Listing]:
        out = []
        seen_links = set()
        for col, (asset_sub, kind) in COLS.items():
            col_url = urllib.parse.urljoin(self.base, col)
            pages = [col_url]
            for p in range(1, self.max_pages + 1):
                pages.append(urllib.parse.urljoin(col_url, f"index_{p}.html"))

            for page_url in pages:
                html = self.get(page_url)
                if not html:
                    continue
                for m in LINK_RE.finditer(html):
                    rel, raw_title = m.group(1), m.group(2)
                    title = clean_text(raw_title)
                    if len(title) < 6:
                        continue
                    full = urllib.parse.urljoin(page_url, rel)
                    if full in seen_links:
                        continue
                    seen_links.add(full)
                    dm = re.search(r"(20\d{6})", rel)
                    date = f"{dm.group(1)[:4]}-{dm.group(1)[4:6]}-{dm.group(1)[6:]}" if dm else ""
                    # 资产类型：矿种从标题粗抽
                    mineral = ""
                    mm = re.search(r"(金矿|银矿|铜矿|铅锌矿|铁矿|煤矿|砂岩矿|石灰岩矿|磷矿|钼矿|镍矿|稀土)", title)
                    if mm:
                        mineral = mm.group(1)
                    out.append(Listing(
                        source=self.name,
                        external_id=re.sub(r"\W", "", full)[-40:],
                        title=f"[{kind}]{title}",
                        asset_type="矿业权",
                        province="",
                        city="",
                        use_type=f"{asset_sub}·{mineral}" if mineral else asset_sub,
                        url=full,
                        published_at=date,
                        raw=kind,
                    ))
                self.polite_sleep()
        kept, removed = filter_concluded(out)
        if removed:
            print(f"  [mining] 过滤已成交/结果公示 {removed} 条")
        return kept
