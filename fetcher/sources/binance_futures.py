from __future__ import annotations

from fetcher.http import get_json, HttpError

BASE = "https://fapi.binance.com"


def perp_contracts():
    """TRADING 的 USDT/USDC 永续合约列表。"""
    d = get_json(BASE + "/fapi/v1/exchangeInfo")
    return [
        s for s in d["symbols"]
        if s.get("contractType") == "PERPETUAL" and s.get("status") == "TRADING"
        and s.get("quoteAsset") in ("USDT", "USDC")
    ]


def premium_index():
    """symbol → {mark, funding}"""
    out = {}
    for x in get_json(BASE + "/fapi/v1/premiumIndex"):
        out[x["symbol"]] = {"mark": _f(x.get("markPrice")), "funding": _f(x.get("lastFundingRate"))}
    return out


def ticker_24h():
    """symbol → quoteVolume (USD)"""
    return {x["symbol"]: _f(x.get("quoteVolume")) for x in get_json(BASE + "/fapi/v1/ticker/24hr")}


def open_interest_usd(symbol, mark):
    """名义 OI（USD）。优先 openInterestHist，失败则用 openInterest × markPrice。"""
    try:
        h = get_json(BASE + "/futures/data/openInterestHist", {"symbol": symbol, "period": "5m", "limit": 1})
        if h:
            v = _f(h[-1].get("sumOpenInterestValue"))
            if v is not None:
                return v
    except HttpError:
        pass
    d = get_json(BASE + "/fapi/v1/openInterest", {"symbol": symbol})
    qty = _f(d.get("openInterest"))
    return qty * mark if qty is not None and mark else None


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
