# -*- coding: utf-8 -*-
"""分类路由：企业类 B / 个人类 C。规则见开发文档 §5.2。"""
import re
from common import Listing

BUSINESS_TYPES = {"土地", "矿业权", "股权", "债权"}
PERSONAL_TYPES = {"二手车", "二手设备", "闲置资产"}


def classify(listing: Listing, threshold_wan: float = 300) -> str:
    at = listing.asset_type
    price_wan = (listing.price_yuan or 0) / 10_000
    if at in BUSINESS_TYPES:
        return "B"
    if at == "房产":
        # 大额或商业/整栋归企业；否则个人
        commercial = re.search(r"厂房|商铺|商业|经营性|整栋|办公楼|写字楼|土地使用权", listing.title)
        if price_wan >= threshold_wan or commercial:
            return "B"
        return "C"
    if at in PERSONAL_TYPES:
        return "C"
    if at == "招租":
        return "B" if price_wan >= threshold_wan else "C"
    return "C"
