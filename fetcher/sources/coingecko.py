from __future__ import annotations

from fetcher.http import get_json

BASE = "https://api.coingecko.com/api/v3"


def circulating_supply(platform, address):
    d = get_json("%s/coins/%s/contract/%s" % (BASE, platform, address))
    v = ((d.get("market_data") or {}).get("circulating_supply"))
    return float(v) if v else None
