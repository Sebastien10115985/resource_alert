# -*- coding: utf-8 -*-
"""分类路由：企业类 B / 个人类 C / 双推类 BC。规则见开发文档 §5.2。

BC：原本归企业的大宗资产（土地/房产/矿业权等），若挂牌价有效且不超过
阈值（默认 300 万），则同时向企业和个人两个 Tab 推送。
无价格的不降级为双推——避免矿业权等无量价标的被误推给个人。
"""
import re
from common import Listing

BUSINESS_TYPES = {"土地", "矿业权", "股权", "债权"}
PERSONAL_TYPES = {"二手车", "二手设备", "闲置资产"}


def classify(listing: Listing, threshold_wan: float = 300) -> str:
    at = listing.asset_type
    price_wan = (listing.price_yuan or 0) / 10_000
    has_price = listing.price_yuan is not None and listing.price_yuan > 0

    # 先按原规则判基础类别
    base = "C"
    if at in BUSINESS_TYPES:
        base = "B"
    elif at == "房产":
        # 大额或商业/整栋归企业；否则个人
        commercial = re.search(r"厂房|商铺|商业|经营性|整栋|办公楼|写字楼|土地使用权", listing.title or "")
        if price_wan >= threshold_wan or commercial:
            base = "B"
    elif at in PERSONAL_TYPES:
        base = "C"
    elif at == "招租":
        base = "B" if price_wan >= threshold_wan else "C"

    # 原本归企业的大宗资产，价格有效且 ≤ 阈值 → 企业+个人双推
    if base == "B" and has_price and price_wan <= threshold_wan:
        return "BC"
    return base
