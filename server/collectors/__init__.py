from .base import BaseCollector
from .land_market import LandMarketCollector
from .mining import MiningCollector
from .ejy import EJyCollector
from .ggzy import GGzyCollector
from .rmfysszc import RmfyCollector

REGISTRY = {
    "land_market": LandMarketCollector,
    "mining": MiningCollector,
    "ejy": EJyCollector,
    "ggzy": GGzyCollector,
    "rmfysszc": RmfyCollector,
}


def build_collectors(config: dict) -> list:
    out = []
    for name, cls in REGISTRY.items():
        cfg = config.get("sources", {}).get(name, {})
        if cfg.get("enabled", False):
            out.append(cls(cfg))
    return out
