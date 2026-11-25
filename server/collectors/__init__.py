from .base import BaseCollector
from .land_market import LandMarketCollector
from .mining import MiningCollector
from .ejy import EJyCollector
from .ggzy import GGzyCollector
from .rmfysszc import RmfyCollector
from .property_exchanges import (
    WuhanCollector, QinghaiCollector, GuizhouCollector,
    ShenzhenCollector, XiamenCollector, CspeaCollector,
)

REGISTRY = {
    "land_market": LandMarketCollector,
    "mining": MiningCollector,
    "ejy": EJyCollector,
    "ggzy": GGzyCollector,
    "rmfysszc": RmfyCollector,
    # 第二批：国资委认定产权交易机构
    "wuhan_ovupre": WuhanCollector,
    "qinghai_cqjy": QinghaiCollector,
    "guizhou_cqjy": GuizhouCollector,
    "shenzhen_sotcbb": ShenzhenCollector,
    "xiamen_cqjy": XiamenCollector,
    # 全国产权行业信息化综合服务平台（聚合全国交易所）
    "cspea_national": CspeaCollector,
}


def build_collectors(config: dict) -> list:
    out = []
    for name, cls in REGISTRY.items():
        cfg = config.get("sources", {}).get(name, {})
        if cfg.get("enabled", False):
            out.append(cls(cfg))
    return out
