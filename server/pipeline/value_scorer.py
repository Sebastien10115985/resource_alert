# -*- coding: utf-8 -*-
"""性价比/风险综合评分（v2）。

设计目标（需求）：
- 明显超出市场价值、产权不清晰、风险高 → 低分；反之高分
- 不同类型资产用不同的评分标准和算法（权重 + 关键词均可按 asset_type 配置）
- 市场价基准：评估价优先，同类城市单价中位数兜底；缺基准给中性分并标注，不虚高

五个维度（均归一化到 0-100，越高越好）：
  value  性价比 —— 挂牌价相对市场基准的折扣
  title  权属清晰度 —— 证照/权属线索
  risk   安全度 —— 抵押查封/债务/治理义务等风险线索（越高越安全）
  seller 挂牌方可靠度
  time   时效 —— 剩余挂牌时间

最终 score = Σ(维度分 × 权重)，权重按 asset_type 取配置，缺失时用 default。
"""
import re
import statistics
from collections import defaultdict
from datetime import date
from typing import Optional

from common import Listing

DIMENSIONS = ("value", "title", "risk", "seller", "time")

# 市场基准缺失时的中性分
NEUTRAL = 50.0


# ---------------------------------------------------------------- 市场基准
def build_market_baseline(listings: list[Listing]) -> dict:
    """从全库计算同类城市单价中位数，作为评估价缺失时的兜底基准。"""
    by_city: dict[str, list[float]] = defaultdict(list)
    by_type: dict[str, list[float]] = defaultdict(list)
    for l in listings:
        p = l.unit_price
        if not p or p <= 0:
            continue
        key_city = (l.asset_type or "", l.city or "")
        by_city[key_city].append(p)
        by_type[l.asset_type or ""].append(p)
    city_med = {k: statistics.median(v) for k, v in by_city.items() if v}
    type_med = {k: statistics.median(v) for k, v in by_type.items() if v}
    return {"city_median": city_med, "type_median": type_med}


def _market_price(l: Listing, baseline: dict) -> tuple[Optional[float], str]:
    """返回 (每单位市场价, 基准来源)。优先评估价折算单价，其次同类城市单价中位数。"""
    # 1) 评估价优先：有评估价 + 面积 → 折成单价；无面积但有评估价 → 退回总价对比在 score_value 内处理
    if l.appraisal_yuan and l.appraisal_yuan > 0:
        if l.area_sqm and l.area_sqm > 0:
            return l.appraisal_yuan / l.area_sqm, "评估价"
        return l.appraisal_yuan, "评估价(总价)"
    # 2) 同类中位数兜底
    med = baseline.get("city_median", {}).get((l.asset_type or "", l.city or ""))
    if med:
        return med, "同类城市单价中位数"
    med = baseline.get("type_median", {}).get(l.asset_type or "")
    if med:
        return med, "同类单价中位数"
    return None, "无基准"


# ---------------------------------------------------------------- 折扣映射
def _discount_score(ratio: Optional[float], cfg: dict) -> tuple[float, str]:
    """ratio = 挂牌价 / 市场价。<1 为折价。返回 (0-100 分, 说明)。"""
    if ratio is None:
        return NEUTRAL, "价格信息不足"
    bands = cfg.get("value_scoring", {}).get("discount_bands", [])
    for b in bands:
        # bands: [{max: 0.5, score: 95, label: "五折以下"}, ...]，末条 max=null 表示兜底
        hi = b.get("max")
        if hi is None or ratio <= float(hi):
            return float(b.get("score", NEUTRAL)), b.get("label", f"价格比{int(ratio*100)}%")
    return NEUTRAL, "价格信息不足"


# ---------------------------------------------------------------- 关键词命中
def _hit(text: str, words: list[str]) -> list[str]:
    return [w for w in words if w and w in text]


def _blob(l: Listing) -> str:
    return f"{l.title or ''} {l.raw or ''} {l.use_type or ''}"


def _days_left(deadline: str) -> Optional[int]:
    if not deadline:
        return None
    m = re.search(r"(20\d{2})-(\d{2})-(\d{2})", deadline)
    if not m:
        return None
    try:
        return (date(int(m.group(1)), int(m.group(2)), int(m.group(3))) - date.today()).days
    except ValueError:
        return None


# ---------------------------------------------------------------- 五维度
def score_value(l: Listing, baseline: dict, cfg: dict, tcfg: dict) -> tuple[float, list[str]]:
    """性价比：挂牌价 vs 市场基准。"""
    reasons = []
    market, source = _market_price(l, baseline)
    ratio = None
    if market and market > 0:
        price = None
        if source == "评估价(总价)" and l.price_yuan:
            price = l.price_yuan
        elif l.unit_price and l.unit_price > 0:
            price = l.unit_price
        elif l.price_yuan and l.area_sqm and l.area_sqm > 0:
            price = l.price_yuan / l.area_sqm
        if price and price > 0:
            ratio = price / market
    s, label = _discount_score(ratio, cfg)
    if ratio is not None:
        pct = int(ratio * 100)
        reasons.append(f"{label}(价/基准{pct}%,基准:{source})")
        if pct > 120:
            reasons.append("价格明显偏高")
    elif source == "无基准":
        reasons.append("无同类市场基准，性价比按中性计")
    else:
        # 有基准但该标的自身缺价格/面积数据，无法比较
        reasons.append(f"本标的价格数据不足，无法与{source}比较，按中性计")
    return _clamp(s), reasons


def score_title(l: Listing, cfg: dict, tcfg: dict) -> tuple[float, list[str]]:
    """权属清晰度。"""
    s = float(tcfg.get("base", 60))
    text = _blob(l)
    pos = _hit(text, tcfg.get("positive", ["出让", "权属清晰", "不动产权证", "有证", "国有建设用地", "挂牌出让"]))
    neg = _hit(text, tcfg.get("negative", ["无证", "划拨", "临时", "代持", "共有", "未取得权证", "权属不清"]))
    s += len(pos) * float(tcfg.get("positive_step", 10))
    s -= len(neg) * float(tcfg.get("negative_step", 15))
    reasons = []
    if pos:
        reasons.append("权属线索:" + "/".join(pos[:3]))
    if neg:
        reasons.append("权属存疑:" + "/".join(neg[:3]))
    return _clamp(s), reasons


def score_risk(l: Listing, cfg: dict, tcfg: dict) -> tuple[float, list[str]]:
    """安全度：越高越安全。"""
    s = float(tcfg.get("base", 75))
    text = _blob(l)
    hits = _hit(text, tcfg.get("keywords", [
        "抵押", "查封", "冻结", "诉讼", "纠纷", "债务", "担保", "被执行",
        "生态修复", "治理义务", "复垦", "污染", "矿坑", "瑕疵", "报废",
    ]))
    # 同词多次出现也只按类别扣一次，避免标题冗长被过度惩罚
    s -= len(hits) * float(tcfg.get("step", 12))
    if l.second_listing:
        s -= float(tcfg.get("second_listing_penalty", 8))
        hits.append("二次挂牌")
    if l.has_defect_note and "瑕疵说明" not in hits and "瑕疵" not in hits:
        s -= float(tcfg.get("defect_penalty", 10))
        hits.append("瑕疵说明")
    reasons = []
    if hits:
        reasons.append("风险线索:" + "/".join(hits[:4]))
    else:
        reasons.append("未见明显风险线索")
    return _clamp(s), reasons


def score_seller(l: Listing, cfg: dict, tcfg: dict) -> tuple[float, list[str]]:
    """挂牌方可靠度。"""
    seller = l.seller or ""
    grades = tcfg.get("grades", {})
    label, s = "其他", float(tcfg.get("base", 55))
    for pat, (lbl, val) in grades.items():
        if re.search(pat, seller):
            label, s = lbl, float(val)
            break
    return _clamp(s), [f"挂牌方:{label}"]


def score_time(l: Listing, cfg: dict, tcfg: dict) -> tuple[float, list[str]]:
    """时效。"""
    d = _days_left(l.deadline)
    if d is None:
        return float(tcfg.get("no_deadline", 60)), ["截止时间未知"]
    bands = tcfg.get("bands", [])
    s = float(tcfg.get("base", 60))
    label = f"剩余{d}天"
    for b in bands:
        mn, mx = b.get("min"), b.get("max")
        if (mn is None or d >= float(mn)) and (mx is None or d < float(mx)):
            s = float(b.get("score", s))
            label = b.get("label", label)
            break
    return _clamp(s), [label]


_SCORERS = {
    "value": score_value,
    "title": score_title,
    "risk": score_risk,
    "seller": score_seller,
    "time": score_time,
}


def _clamp(x: float) -> float:
    return max(0.0, min(100.0, x))


# ---------------------------------------------------------------- 主入口
def score_listing_v2(l: Listing, cfg: dict, baseline: Optional[dict] = None) -> int:
    """统一评分入口：按 asset_type 取权重，五维度加权融合为单一 score。

    写回 l.score / l.score_reasons / l.score_detail / l.asset_score_* 等字段。
    """
    baseline = baseline or {"city_median": {}, "type_median": {}}
    vcfg = cfg.get("value_scoring", {})
    profiles = vcfg.get("profiles", {})
    atype = l.asset_type or "其他"
    default_profile = profiles.get("default") or {}
    own = profiles.get(atype) or {}
    # 各维度配置：优先用本类型，缺则回退 default（这样 seller/time 等公共配置不必每类重写）
    profile: dict = {"weights": own.get("weights") or default_profile.get("weights", {})}
    for dim in DIMENSIONS:
        profile[dim] = own.get(dim) or default_profile.get(dim) or {}
    weights = profile["weights"]

    detail: dict[str, float] = {}
    all_reasons: list[str] = []
    total = 0.0
    wsum = 0.0
    for dim in DIMENSIONS:
        fn = _SCORERS[dim]
        tcfg = profile.get(dim, {})
        if dim == "value":
            s, rs = fn(l, baseline, cfg, tcfg)
        else:
            s, rs = fn(l, cfg, tcfg)
        detail[dim] = round(s, 1)
        all_reasons.extend(rs)
        w = float(weights.get(dim, 0))
        total += s * w
        wsum += w

    score = int(round(total / wsum)) if wsum else 0
    l.score = max(0, min(100, score))
    l.score_reasons = all_reasons
    # 明细字段（ Listing 中动态挂载，store 会按列名写入）
    l.score_detail = detail
    l.value_score = detail.get("value", 0)
    l.title_score = detail.get("title", 0)
    l.risk_score = detail.get("risk", 0)
    l.seller_score = detail.get("seller", 0)
    l.time_score = detail.get("time", 0)
    l.market_basis = _market_price(l, baseline)[1]
    return l.score
