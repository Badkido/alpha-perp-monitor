from __future__ import annotations

from fetcher.http import get_json

URL = "https://www.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list"
REQUIRED = ("symbol", "chainId", "contractAddress", "price", "circulatingSupply", "totalSupply")


class AlphaFormatError(Exception):
    pass


def alpha_tokens():
    """非官方接口，字段可能变化：解析前严格校验，失败即清楚报错。"""
    d = get_json(URL)
    if not isinstance(d, dict) or not d.get("success") or not isinstance(d.get("data"), list):
        raise AlphaFormatError("Alpha 响应结构异常: %s" % str(d)[:200])
    rows = d["data"]
    if not rows:
        raise AlphaFormatError("Alpha 列表为空")
    missing = [k for k in REQUIRED if k not in rows[0]]
    if missing:
        raise AlphaFormatError("Alpha 字段缺失: %s（样本见 samples/alpha_list.json）" % missing)
    out = []
    for r in rows:
        if r.get("fullyDelisted"):  # 完全摘牌：成交/流动性基本为零，过滤
            continue
        out.append({
            "symbol": str(r["symbol"]).upper(),
            "name": r.get("name"),
            "chain_id": str(r["chainId"]),
            "address": r["contractAddress"],
            "price": _f(r.get("price")),
            "volume24h": _f(r.get("volume24h")),
            "market_cap": _f(r.get("marketCap")),
            "liquidity": _f(r.get("liquidity")),
            "circ_supply": _f(r.get("circulatingSupply")),
            "total_supply": _f(r.get("totalSupply")),
            "holders": _f(r.get("holders")),
            "offline": bool(r.get("offline")),  # 已下线但未完全摘牌：保留并标记
        })
    return out


def _f(v):
    try:
        x = float(v)
        return x
    except (TypeError, ValueError):
        return None
