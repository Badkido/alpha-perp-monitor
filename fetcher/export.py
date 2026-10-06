from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from fetcher.chains import chain_info


def _links(t):
    ci = chain_info(t["chain_id"])
    l = {"binance_futures": "https://www.binance.com/en/futures/%s" % t["perp_symbol"]}
    if ci["dex"]:
        l["dexscreener"] = "https://dexscreener.com/%s/%s" % (ci["dex"], t["address"])
    if ci["explorer"]:
        l["explorer"] = ci["explorer"].format(a=t["address"])
    return l


def sort_key(t):
    c = t["cond_level"]
    oi = t["metrics"]["oi_to_mcap"]["value"]
    return (-c["alert"], -c["warn"], -(oi if oi is not None else -1))


def export(path, ts, stage, thresholds, tokens, unmatched, errors):
    tokens = sorted(tokens, key=sort_key)
    out = {
        "generated_at": ts,
        "stage": stage,
        "thresholds": thresholds,
        "summary": {
            "n_universe": len(tokens),
            "n_alert": sum(1 for t in tokens if t["cond_level"]["alert"] > 0),
            "n_warn": sum(1 for t in tokens if t["cond_level"]["alert"] == 0 and t["cond_level"]["warn"] > 0),
            "n_unmatched": len(unmatched),
        },
        "tokens": [{
            "ticker": t["ticker"], "perp_symbol": t["perp_symbol"], "chain": t["chain"], "address": t["address"],
            "perp_onboard_date": t["perp_onboard_date"], "is_new_perp": t["is_new_perp"],
            "price": t["price"], "mcap_usd": t["mcap_usd"], "fdv_usd": t["fdv_usd"], "fdv_to_mcap": t["fdv_to_mcap"],
            "oi_usd": t["oi_usd"], "perp_vol_24h_usd": t["perp_vol_24h_usd"],
            "alpha_vol_24h_usd": t["alpha_vol_24h_usd"], "dex_liq_usd": t["dex_liq_usd"],
            "dex_vol_24h_usd": t["dex_vol_24h_usd"], "funding_rate": t["funding_rate"],
            "circ_supply": t["circ_used"], "total_supply": t["total_supply"],
            "metrics": t["metrics"], "cond_level": t["cond_level"], "flags": t["flags"], "links": _links(t),
        } for t in tokens],
        "unmatched": unmatched,
        "errors": errors,
    }
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, allow_nan=False)
    os.replace(tmp, path)
