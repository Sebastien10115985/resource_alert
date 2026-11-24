# -*- coding: utf-8 -*-
"""过滤已成交/结果公示类标的：这类信息对"发现机会"无价值，不入库。

判定分两层（任一命中即排除）：
1) URL 栏目本身是结果公示（如 mining 的 /jggs/ 栏目）
2) 标题/raw 含成交结果类关键词（出让结果、成交公示、中标结果…）
"""
import re
from common import Listing

# 已成交/结果类：出现这些词组说明交易已经完成，不再是机会
RESULT_PATTERNS = [
    r"出让结果", r"成交公示", r"成交结果", r"成交公告", r"成交确认",
    r"中标结果", r"中标公示", r"中标公告", r"竞得结果", r"竞得公示",
    r"挂牌结果", r"拍卖结果", r"交易结果", r"结果公示", r"结果公告",
    r"已成交", r"已出让", r"已中标", r"成交价", r"竞得人",
    r"公示结果", r"成交情况", r"出让成交", r"转让结果",
]

_RESULT_RE = re.compile("|".join(RESULT_PATTERNS))

# 采集器来源栏目本身就是结果公示的（ mining 的 jggs 栏目）
RESULT_URL_PATTERNS = [r"/jggs/", r"/cjgs/", r"/result", r"transNoticeOrResultList"]


def is_concluded(l: Listing) -> bool:
    """是否已成交/结果公示。True 表示应排除。"""
    # URL 直接判定（栏目级）
    url = l.url or ""
    if any(re.search(p, url, re.I) for p in RESULT_URL_PATTERNS):
        return True
    title = (l.title or "") + " " + (l.raw or "")
    # 结果类优先：命中成交/结果词组即排除，避免"挂牌出让结果公示"被机会词误留
    if _RESULT_RE.search(title):
        return True
    return False


def filter_concluded(items: list[Listing]) -> tuple[list[Listing], int]:
    """过滤列表，返回 (保留列表, 剔除数量)。"""
    kept = [it for it in items if not is_concluded(it)]
    return kept, len(items) - len(kept)
