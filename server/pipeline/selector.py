# -*- coding: utf-8 -*-
"""每日优选：按类别取 Top-N，并合并变更标的。

评分支持两版：
- v2（默认）：性价比/权属/风险/挂牌方/时效五维度，按 asset_type 走不同权重 —— value_scorer.py
- v1（回退）：旧的 B/C 双权重 —— scorer.py
由 config.yaml 的 value_scoring.enabled 控制。
"""
from common import Listing
from .value_scorer import score_listing_v2, build_market_baseline


def select(listings: list[Listing], config: dict) -> dict[str, list[Listing]]:
    top_n = int(config.get("selection", {}).get("top_n_per_category", 10))
    bc_threshold = float(config.get("filter", {}).get("bc_threshold_wan", 300))
    use_v2 = bool(config.get("value_scoring", {}).get("enabled", False))

    from .classifier import classify
    if use_v2:
        baseline = build_market_baseline(listings)
    else:
        baseline = None

    grouped = {"B": [], "C": []}
    for l in listings:
        l.category = classify(l, bc_threshold)
        if use_v2:
            score_listing_v2(l, config, baseline)
            l.scoring_version = "v2"
        else:
            from .scorer import score_listing
            score_listing(l, config)
            l.scoring_version = "v1"
        # BC 双推：同一标的同时进入企业 B 和个人 C 两个分组
        if l.category == "BC":
            grouped["B"].append(l)
            grouped["C"].append(l)
        elif l.category in grouped:
            grouped[l.category].append(l)

    result = {}
    for cat in ("B", "C"):
        items = sorted(grouped[cat], key=lambda x: -x.score)[:top_n]
        result[cat] = items
    return result
