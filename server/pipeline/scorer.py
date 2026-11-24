# -*- coding: utf-8 -*-
"""双权重评分：企业类 B / 个人类 C。规则来自实测的 rank_ejy.py，见文档 §5.3/5.4。"""
import re
from datetime import date
from common import Listing


def _seller_grade(seller: str) -> tuple[str, int]:
    if re.search(r"人民政府|管委会|管理委员会|国有资产|国资|财政局|街道办|镇政府", seller or ""):
        return "政府/国资", 3
    if re.search(r"产权交易|交易所|交易中心|拍卖|产权服务", seller or ""):
        return "产权机构", 2
    if re.search(r"银行|保险|资产管理|信托", seller or ""):
        return "金融机构", 2
    return "企业/其他", 1


def _days_left(deadline: str) -> int | None:
    m = re.search(r"(20\d{2})-(\d{2})-(\d{2})", deadline or "")
    if not m:
        return None
    try:
        return (date(int(m.group(1)), int(m.group(2)), int(m.group(3))) - date.today()).days
    except ValueError:
        return None


def score_business(l: Listing, cfg: dict) -> int:
    w = cfg.get("scoring", {}).get("business", {})
    s = 0
    # 权属/证照线索（标题或原始字段出现"出让/有证/权属清晰"）
    if re.search(r"出让|有证|权属|权证|不动产权", (l.title or "") + (l.raw or "")):
        s += w.get("clear_title", 20)
    # 用途匹配（有用_type 即视为有明确用途）
    if l.use_type:
        s += w.get("use_match", 15)
    # 规模合适（有面积即视为可评估）
    if l.area_sqm and l.area_sqm > 0:
        s += w.get("size_fit", 10)
    # 价格合理：低于评估价
    if l.discount_rate and l.discount_rate < 1:
        s += w.get("price_reasonable", 20)
    # 无他项权利线索（raw 里没出现抵押/查封/在租）
    blob = (l.raw or "") + (l.title or "")
    if not re.search(r"抵押|查封|在租|租赁", blob):
        s += w.get("no_encumbrance", 15)
    # 无生态/矿坑治理义务线索
    if not re.search(r"生态修复|治理义务|复垦|污染", blob):
        s += w.get("no_eco_burden", 10)
    # 挂牌方可靠
    grade, _ = _seller_grade(l.seller)
    s += w.get("reliable_seller", 10) if grade in ("政府/国资", "产权机构") else 0
    # 时效
    d = _days_left(l.deadline)
    if d is not None and d >= 7:
        s += w.get("time_left", 5)
    return s


def score_personal(l: Listing, cfg: dict) -> int:
    w = cfg.get("scoring", {}).get("personal", {})
    scfg = cfg.get("scoring", {})
    s = 0
    # 折扣率
    if l.discount_rate:
        d = l.discount_rate
        if d <= 0.85:
            s += w.get("discount_le_085", 30)
        elif d <= 0.95:
            s += w.get("discount_le_095", 18)
        elif d <= 1.0:
            s += w.get("discount_le_100", 8)
        elif d > 1.2:
            s += w.get("discount_gt_120", -15)
    # 住宅低单价（明确排除非住宅）
    nonres = scfg.get("non_residential_keywords", [])
    is_residential = (re.search(r"住宅|小区|花园|公寓|商品房|安置房|家园|苑|府|庭|村", l.title or "")
                      and not any(k in (l.title or "") for k in nonres))
    threshold = scfg.get("residential_unit_threshold", 5000)
    if l.unit_price and l.unit_price < threshold and is_residential:
        s += w.get("residential_low_unit", 20)
    # 二次挂牌
    if l.second_listing:
        s += w.get("second_listing", 12)
    # 挂牌方分级
    grade, gscore = _seller_grade(l.seller)
    if grade == "政府/国资":
        s += w.get("seller_gov", 9)
    elif grade == "产权机构":
        s += w.get("seller_exchange", 6)
    else:
        s += w.get("seller_enterprise", 3)
    # 时效
    d = _days_left(l.deadline)
    if d is not None:
        if d >= 3:
            s += w.get("deadline_ok", 5)
        elif d < 0:
            s += w.get("deadline_expired", -20)
    # 瑕疵
    if l.has_defect_note:
        s += w.get("defect_note", -3)
    return s


def score_listing(l: Listing, cfg: dict) -> int:
    """按品类选权重打分，并写回 l.score / l.score_reasons。"""
    reasons = []
    before = l.score
    if l.category in ("B", "BC"):
        l.score = score_business(l, cfg)
        if l.discount_rate and l.discount_rate < 1:
            reasons.append(f"低于评估价{int((1-l.discount_rate)*100)}%")
        if l.use_type:
            reasons.append(f"用途:{l.use_type}")
    else:
        l.score = score_personal(l, cfg)
        if l.discount_rate and l.discount_rate < 1:
            reasons.append(f"低于评估价{int((1-l.discount_rate)*100)}%")
        if l.unit_price and l.unit_price < cfg.get("scoring", {}).get("residential_unit_threshold", 5000):
            reasons.append(f"单价约{int(l.unit_price)}元/㎡")
        if l.second_listing:
            reasons.append("二次挂牌")
    grade, _ = _seller_grade(l.seller)
    reasons.append(f"挂牌方:{grade}")
    l.score_reasons = reasons
    return l.score - before
