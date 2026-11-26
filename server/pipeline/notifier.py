# -*- coding: utf-8 -*-
"""推送：企业微信/钉钉机器人 + Server酱。密钥从环境变量读取，不写死在代码里。"""
import os
import json
import time
import hmac
import hashlib
import base64
import urllib.parse
import urllib.request

from common import Listing


def _dingtalk_signed_url(webhook: str, secret: str) -> str:
    """按钉钉加签规则生成带 timestamp/sign 的 Webhook。无 secret 时原样返回。

    钉钉加签：string_to_sign = timestamp + "\\n" + secret，用 secret 做 HMAC-SHA256，
    Base64 后 URL 编码，作为 sign 参数，与 timestamp 一起拼到 Webhook 查询串。
    """
    if not secret:
        return webhook
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"),
                         digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    sep = "&" if "?" in webhook else "?"
    return f"{webhook}{sep}timestamp={timestamp}&sign={sign}"


def _post_json(url: str, payload: dict) -> bool:
    try:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data,
                                     headers={"Content-Type": "application/json; charset=utf-8"})
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode("utf-8", "ignore")
            # 钉钉/企微即使 HTTP 200 也可能在 body 里返回 errcode != 0（如签名错误、关键词不匹配）
            try:
                j = json.loads(raw)
                if "errcode" in j:
                    if j["errcode"] != 0:
                        print("  push ERR errcode", j["errcode"], str(j.get("errmsg", ""))[:80])
                        return False
            except (ValueError, TypeError):
                pass
            return r.status == 200
    except Exception as e:
        print("  push ERR", str(e)[:100])
        return False


def build_daily_markdown(date: str, by_cat: dict[str, list[Listing]]) -> str:
    # 标题含小写 resource：钉钉机器人若设了自定义关键词 resource，正文必须包含它才能推送成功
    lines = [f"## resource · 每日资源优选 · {date}"]
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
    # 钉钉机器人（支持加签：DINGTALK_BOT_SECRET / channels.dingtalk_secret）
    ding = os.environ.get("DINGTALK_BOT_WEBHOOK") or pcfg.get("channels", {}).get("dingtalk_bot", "")
    if ding:
        if not (already_pushed_fn and already_pushed_fn(date, "dingtalk")):
            secret = os.environ.get("DINGTALK_BOT_SECRET") or pcfg.get("channels", {}).get("dingtalk_secret", "")
            ok = _post_json(_dingtalk_signed_url(ding, secret),
                            {"msgtype": "markdown", "markdown": {"title": "每日资源优选", "text": md}})
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
