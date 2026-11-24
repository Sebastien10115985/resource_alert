# -*- coding: utf-8 -*-
"""采集器抽象基类：统一 fetch + collect 接口，内置重试与礼貌间隔。"""
import time
import ssl
import urllib.request
from abc import ABC, abstractmethod

from common import Listing

CTX = ssl._create_unverified_context()
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120 Safari/537.36",
}


class BaseCollector(ABC):
    name = "base"

    def __init__(self, config: dict):
        self.config = config
        self.interval = float(config.get("request_interval_sec", 0.2))

    def get(self, url: str, headers: dict | None = None, retry: int = 2, timeout: int = 40) -> str:
        h = {**UA, **(headers or {})}
        for i in range(retry + 1):
            try:
                req = urllib.request.Request(url, headers=h)
                return urllib.request.urlopen(req, timeout=timeout, context=CTX).read().decode("utf-8", "ignore")
            except Exception:
                if i == retry:
                    return ""
                time.sleep(1 + i)
        return ""

    def polite_sleep(self):
        if self.interval > 0:
            time.sleep(self.interval)

    @abstractmethod
    def collect(self) -> list[Listing]:
        """返回统一 Listing 列表。"""
        raise NotImplementedError
