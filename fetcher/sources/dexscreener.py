from __future__ import annotations

from fetcher.http import get_json

BASE = "https://api.dexscreener.com/tokens/v1"


def token_stats(chain_dex_id, addresses, min_pair_liq):
    """批量（每次 ≤30 个地址）。返回 {地址小写: {liq, vol}}；无满足条件 pair 的地址 liq=vol=0。"""
    out = {a.lower(): {"liq": 0.0, "vol": 0.0} for a in addresses}
    for i in range(0, len(addresses), 30):
        batch = addresses[i:i + 30]
        pairs = get_json("%s/%s/%s" % (BASE, chain_dex_id, ",".join(batch)))
        if not isinstance(pairs, list):
            continue
        for p in pairs:
            liq = ((p.get("liquidity") or {}).get("usd")) or 0
            if liq < min_pair_liq:
                continue
            vol = ((p.get("volume") or {}).get("h24")) or 0
            for side in ("baseToken", "quoteToken"):
                a = ((p.get(side) or {}).get("address") or "").lower()
                if a in out:
                    out[a]["liq"] += liq
                    out[a]["vol"] += vol
    return out
