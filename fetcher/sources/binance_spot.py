from __future__ import annotations

from fetcher.http import get_json, HttpError

URLS = [
    "https://api.binance.com/api/v3/exchangeInfo",
    "https://data-api.binance.vision/api/v3/exchangeInfo",  # 备用域名
]


def spot_base_assets():
    """现货 TRADING 的 baseAsset 集合（不论计价币种）。"""
    last = None
    for u in URLS:
        try:
            d = get_json(u)
            return {s["baseAsset"].upper() for s in d["symbols"] if s.get("status") == "TRADING"}
        except HttpError as e:
            last = e
    raise last
