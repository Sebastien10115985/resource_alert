# -*- coding: utf-8 -*-
"""每日优选：按类别取 Top-N，并合并变更标的。"""
from common import Listing
from .scorer import score_listing

def select(listings: list[Listing], config: dict) -> dict[str, list[Listing]]:
    scfg = config.get("scoring", {})
    top_n = int(config.get("selection", {}).get("top_n_per_category", 10))
    bc_threshold = float(config.get("filter", {}).get("bc_threshold_wan", 300))

    from .classifier import classify
    grouped = {"B": [], "C": []}
    for l in listings:
        l.category = classify(l, bc_threshold)
        score_listing(l, config)
        grouped[l.category].append(l)

    result = {}
    for cat in ("B", "C"):
        items = sorted(grouped[cat], key=lambda x: -x.score)[:top_n]
        result[cat] = items
    return result
