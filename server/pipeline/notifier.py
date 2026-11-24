# -*- coding: utf-8 -*-
"""推送：企业微信/钉钉机器人 + Server酱。密钥从环境变量读取，不写死在代码里。"""
import os
import json
import urllib.parse
import urllib.request

from common import Listing


def _post_json(url: str, payload: dict) -> bool:
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception as e:
        print("  push ERR", str(e)[:100])
        return False


def build_daily_markdown(date: str, by_cat: dict[str, list[Listing]]) -> str:
    lines = [f"## 每日资源优选 · {date}"]
    for cat, name in (("B", "企业类"), ("C", "个人类")):
        lines.append(f"\n**{name} Top{len(by_cat.get(cat, []))}**")
        items = by_cat.get(cat, [])[:10]
        if not items:
            lines.append("- 本类暂无符合条件的标的")
        for i, l in enumerate(items, 1):
            price = l.price_text or ("面议" if not l.price_yuan else f"{l.price_yuan:,.0f}元")
            reasons = "、".join(l.score_reasons[:2])
            link = f"[查看]({l.url})" if l.url else ""
            lines.append(f"{i}. {link} {l.title[:40]} — {price} · 评分{l.score}\n   {reasons}")
    lines.append("\n> 国资产权不担保瑕疵，出价前请自行尽调（权属/规划/抵押/环保）。")
    return "\n".join(lines)


def push_daily(config: dict, date: str, by_cat: dict[str, list[Listing]],
               already_pushed_fn=None) -> dict[str, bool]:
    pcfg = config.get("push", {})
    if not pcfg.get("enabled", False):
        return {"skipped": True}

    md = build_daily_markdown(date, by_cat)
    results = {}

    # 企业微信机器人
    wecom = os.environ.get("WECOM_BOT_WEBHOOK") or pcfg.get("channels", {}).get("wecom_bot", "")
    if wecom:
        if not (already_pushed_fn and already_pushed_fn(date, "wecom")):
            ok = _post_json(wecom, {"msgtype": "markdown", "markdown": {"content": md}})
            results["wecom"] = ok
    # 钉钉机器人
    ding = os.environ.get("DINGTALK_BOT_WEBHOOK") or pcfg.get("channels", {}).get("dingtalk_bot", "")
    if ding:
        if not (already_pushed_fn and already_pushed_fn(date, "dingtalk")):
            ok = _post_json(ding, {"msgtype": "markdown", "markdown": {"title": "每日资源优选", "text": md}})
            results["dingtalk"] = ok
    # Server酱
    key = os.environ.get("SERVERCHAN_KEY") or pcfg.get("channels", {}).get("serverchan_key", "")
    if key:
        if not (already_pushed_fn and already_pushed_fn(date, "serverchan")):
            try:
                data = urllib.parse.urlencode({"title": f"每日资源优选 {date}", "desp": md}).encode()
                req = urllib.request.Request(f"https://sctapi.ftqq.com/{key}.send", data=data)
                with urllib.request.urlopen(req, timeout=15) as r:
                    results["serverchan"] = r.status == 200
            except Exception as e:
                print("  serverchan ERR", str(e)[:100]); results["serverchan"] = False
    return results
