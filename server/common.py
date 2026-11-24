# -*- coding: utf-8 -*-
"""公共工具：配置加载、数值解析、统一 Schema、时间。"""
import os
import re
import json
import yaml
from dataclasses import dataclass, asdict, field
from typing import Any, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))


def load_config(path: Optional[str] = None) -> dict:
    path = path or os.path.join(ROOT, "config.yaml")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def num(s: Any) -> Optional[float]:
    """从 '580万元' / '1,234.5' / '面议' 中抽数值；无则返回 None。"""
    if s is None:
        return None
    m = re.search(r"([\d,]+(?:\.\d+)?)", str(s))
    return float(m.group(1).replace(",", "")) if m else None


def to_yuan(value: Any, text: str = "") -> Optional[float]:
    """把价格统一换算成元。'580万元'→5,800,000；'1.33亿'→133,000,000。"""
    v = num(value if value not in (None, "") else text)
    if v is None:
        return None
    s = f"{value} {text}"
    if "亿" in s:
        return v * 100_000_000
    if "万" in s:
        return v * 10_000
    return v


def now_iso() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class Listing:
    """统一标的 Schema，与开发文档 §4.1 及 Android 端 Listing.kt 对齐。"""
    source: str
    external_id: str
    title: str
    category: str = "C"                 # B=企业, C=个人
    asset_type: str = ""
    province: str = ""
    city: str = ""
    district: str = ""
    area_sqm: Optional[float] = None
    price_yuan: Optional[float] = None
    price_text: str = ""
    appraisal_yuan: Optional[float] = None
    unit_price: Optional[float] = None
    discount_rate: Optional[float] = None
    deadline: str = ""
    seller: str = ""
    seller_grade: str = ""
    second_listing: bool = False
    has_defect_note: bool = False
    use_type: str = ""
    url: str = ""
    published_at: str = ""
    collected_at: str = field(default_factory=now_iso)
    score: int = 0
    score_reasons: list = field(default_factory=list)
    # v2 评分明细（性价比/权属/安全/挂牌方/时效，0-100）
    value_score: float = 0
    title_score: float = 0
    risk_score: float = 0
    seller_score: float = 0
    time_score: float = 0
    score_detail: dict = field(default_factory=dict)
    market_basis: str = ""
    scoring_version: str = "v1"
    raw: str = ""

    @property
    def key(self):
        return (self.source, self.external_id)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["id"] = f"{self.source}:{self.external_id}"
        return d


def clean_text(s: Any) -> str:
    return re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", str(s or ""))).strip()
