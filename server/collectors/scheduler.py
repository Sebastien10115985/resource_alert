# -*- coding: utf-8 -*-
"""采集调度器：把数据源分两组，用不同节奏抓取。

- open      组：无反爬，按注册顺序连续抓，站点间不额外等待。
- throttled 组：有限流/反爬，round-robin 轮询——每个站点抓一次就换下一个；
  同一站点的两次尝试之间强制冷却 cooldown_sec（默认 120 秒）。
  所有站点都在冷却时，睡到最近一个站点到期再继续，不忙等。

为什么按"任务级"冷却而不是"HTTP 请求级"：
采集器内部翻页/详情已经有自己的 request_interval_sec（0.15~0.3s）做礼貌间隔；
这里的 2 分钟是**同一站点两次采集任务**之间的间隔，避免高频轮询触发风控。

失败也计入冷却：某站点报错后不会立刻重试，而是排到 2 分钟后，
期间先抓其他站点。每站点最多尝试 max_attempts 轮，避免无限重试。
"""
import time
from dataclasses import dataclass, field

from .base import BaseCollector
from common import Listing

OPEN = "open"
THROTTLED = "throttled"


@dataclass
class FetchResult:
    collector: str
    group: str
    attempt: int
    items: list = field(default_factory=list)
    error: str = ""
    waited_sec: float = 0.0
    block_reason: str = ""     # 采集器自报的风控/限流降级原因


@dataclass
class _SiteState:
    collector: BaseCollector
    group: str
    cooldown: float
    max_attempts: int
    attempts: int = 0
    last_finished: float = 0.0     # 上次任务结束的单调时间
    done: bool = False


class CollectionScheduler:
    def __init__(self, collectors: list[BaseCollector], config: dict,
                 now_fn=None, sleep_fn=None, on_result=None):
        """
        config 里读 sources.<name>.group / cooldown_sec / max_attempts。
        now_fn / sleep_fn 可注入，方便测试时不用真等 2 分钟。
        on_result(FetchResult) 每次抓完回调，便于主流程即时入库。
        """
        self.cfg = config
        self.now = now_fn or time.monotonic
        self.sleep = sleep_fn or time.sleep
        self.on_result = on_result
        self.sites: list[_SiteState] = []
        sources_cfg = config.get("sources", {})
        for c in collectors:
            sc = sources_cfg.get(c.name, {})
            group = sc.get("group", OPEN)
            if group not in (OPEN, THROTTLED):
                group = OPEN
            cooldown = float(sc.get("cooldown_sec", 120))
            max_attempts = int(sc.get("max_attempts", 1))
            self.sites.append(_SiteState(
                collector=c, group=group, cooldown=cooldown, max_attempts=max_attempts,
            ))

    @property
    def open_sites(self):
        return [s for s in self.sites if s.group == OPEN]

    @property
    def throttled_sites(self):
        return [s for s in self.sites if s.group == THROTTLED]

    def _fetch(self, site: _SiteState) -> FetchResult:
        site.attempts += 1
        c = site.collector
        try:
            items = c.collect()
            err = ""
        except Exception as e:
            items, err = [], str(e)[:200]
        site.last_finished = self.now()
        block = getattr(c, "last_block_reason", "")
        r = FetchResult(c.name, site.group, site.attempts, items, err,
                        block_reason=block)
        if self.on_result:
            self.on_result(r)
        return r

    def run(self) -> list[FetchResult]:
        results: list[FetchResult] = []

        # 1) 不反爬组：连续抓，站点间不额外等待
        for site in self.open_sites:
            results.append(self._fetch(site))

        # 2) 反爬组：round-robin，每站点一次，同站点间隔 cooldown
        throttled = self.throttled_sites
        if not throttled:
            return results

        pending = [s for s in throttled if s.attempts < s.max_attempts]
        while pending:
            t = self.now()
            # 找出当前已冷却完毕、可以抓的站点
            ready = [s for s in pending if t - s.last_finished >= s.cooldown]
            if not ready:
                # 全部在冷却：睡到最近一个站点到期（不忙等）
                soonest = min(s.last_finished + s.cooldown for s in pending)
                wait = max(0.0, soonest - self.now())
                if wait > 0:
                    self.sleep(wait)
                continue
            # 轮询：每次只抓一个站点，抓完立刻回到循环，
            # 该站点进入冷却，下一轮自然抓别的站点
            site = ready[0]
            # 该站点本次实际等待了多久（首次为 0）
            waited = max(0.0, t - site.last_finished) if site.attempts > 0 else 0.0
            r = self._fetch(site)
            r.waited_sec = waited
            results.append(r)
            if site.attempts >= site.max_attempts:
                pending.remove(site)
        return results
