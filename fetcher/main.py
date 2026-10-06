"""编排：universe → collect → metrics → store → export。

任一必需源（合约/现货/Alpha 列表）失败 → 非零退出，不写任何输出（保留上一版 data.json）。
单币的可选字段（OI、DEX、CoinGecko）失败 → 该字段 null，记录到 errors。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import yaml

from fetcher import export, store, universe
from fetcher.chains import chain_info
from fetcher.http import HttpError
from fetcher.metrics import stage_a
from fetcher.sources import binance_alpha, binance_futures, binance_spot, coingecko, dexscreener

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = "A"
STAGES = [stage_a]  # 以后追加 stage_b, stage_c, scoring
CG_TTL = 24 * 3600
CG_BUDGET = 40  # 每次运行最多请求 CoinGecko 次数（6s 间隔 ≈ 4 分钟；缓存 24h，多轮运行补齐）


def load_yaml(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def collect_cg(uni, cache_path, errors, enabled):
    cache = {}
    if os.path.exists(cache_path):
        try:
            cache = json.load(open(cache_path))
        except ValueError:
            cache = {}
    now, calls = time.time(), 0
    for u in uni:
        a = u["alpha"]
        ci = chain_info(a["chain_id"])
        key = "%s:%s" % (ci["cg"], a["address"].lower())
        hit = cache.get(key)
        if hit and now - hit["ts"] < CG_TTL:
            u["circ_cg"] = hit["v"]
            continue
        if not enabled or not ci["cg"] or calls >= CG_BUDGET:
            u["circ_cg"] = hit["v"] if hit else None  # 过期缓存也比没有强
            continue
        calls += 1
        try:
            v = coingecko.circulating_supply(ci["cg"], a["address"])
            cache[key] = {"ts": now, "v": v}
            u["circ_cg"] = v
        except HttpError as e:
            if e.status == 429:  # 限速熔断：本次不再请求，剩余币下次运行补
                errors.append("coingecko rate-limited, skipped remaining")
                enabled = False
            elif e.status != 404:
                errors.append("coingecko %s: %s" % (u["ticker"], e.status))
            cache[key] = {"ts": now - CG_TTL + 3600, "v": None} if e.status == 404 else cache.get(key)
            u["circ_cg"] = (cache.get(key) or {}).get("v")
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    json.dump(cache, open(cache_path, "w"))


def collect_dex(uni, cfg, errors):
    by_chain = {}
    for u in uni:
        d = chain_info(u["alpha"]["chain_id"])["dex"]
        if d:
            by_chain.setdefault(d, []).append(u)
    for chain, items in by_chain.items():
        try:
            stats = dexscreener.token_stats(chain, [u["alpha"]["address"] for u in items], cfg["dex_min_pair_liq_usd"])
        except HttpError as e:
            errors.append("dexscreener %s: %s" % (chain, e.status))
            continue
        for u in items:
            s = stats.get(u["alpha"]["address"].lower())
            if s:
                u["dex_liq"], u["dex_vol"] = s["liq"], s["vol"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "site", "data.json"))
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "history.db"))
    ap.add_argument("--no-store", action="store_true", help="不写 SQLite")
    ap.add_argument("--no-cg", action="store_true", help="跳过 CoinGecko")
    args = ap.parse_args(argv)

    cfg, overrides = load_yaml("config/thresholds.yaml"), load_yaml("config/overrides.yaml")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    errors = []

    # 1. 必需数据源：失败即整体失败
    try:
        contracts = binance_futures.perp_contracts()
        spot = binance_spot.spot_base_assets()
        alpha = binance_alpha.alpha_tokens()
        marks = binance_futures.premium_index()
        vols = binance_futures.ticker_24h()
    except (HttpError, binance_alpha.AlphaFormatError, KeyError) as e:
        print("FATAL: 必需数据源失败: %r" % e, file=sys.stderr)
        return 1

    uni, unmatched = universe.build(contracts, spot, alpha, overrides, marks, cfg)
    print("perps=%d spot=%d alpha=%d → universe=%d unmatched=%d" %
          (len(contracts), len(spot), len(alpha), len(uni), len(unmatched)))

    # 2. 逐币采集
    collect_cg(uni, os.path.join(ROOT, "data", "cg_cache.json"), errors, not args.no_cg)
    collect_dex(uni, cfg, errors)

    tokens = []
    for u in uni:
        a, mult = u["alpha"], u["multiplier"]
        ci = chain_info(a["chain_id"])
        oi, vol = None, None
        for q, c in u["contracts"].items():
            sym = c["symbol"]
            mark = (marks.get(sym) or {}).get("mark")
            try:
                v = binance_futures.open_interest_usd(sym, mark)
            except HttpError as e:
                errors.append("oi %s: %s" % (sym, e.status))
                v = None
            if v is not None:
                oi = (oi or 0) + v
            qv = vols.get(sym)
            if qv is not None:
                vol = (vol or 0) + qv
        p = u["primary"]
        pm = marks.get(p["symbol"]) or {}
        onboard = datetime.fromtimestamp(p["onboardDate"] / 1000, timezone.utc) if p.get("onboardDate") else None
        age = (datetime.now(timezone.utc) - onboard).days if onboard else None
        tok = {
            "ticker": u["ticker"], "perp_symbol": p["symbol"], "chain": ci["slug"], "chain_id": a["chain_id"],
            "address": a["address"], "override": u["override"], "multiplier": mult,
            "perp_onboard_date": onboard.strftime("%Y-%m-%d") if onboard else None,
            "is_new_perp": age is not None and age <= cfg["new_perp_days"],
            "price": pm["mark"] / mult if pm.get("mark") else None,
            "funding_rate": pm.get("funding"),
            "oi_usd": oi, "perp_vol_24h_usd": vol,
            "circ_supply": a["circ_supply"] or None, "total_supply": a["total_supply"] or None,
            "circ_supply_cg": u.get("circ_cg"),
            "alpha_vol_24h_usd": a["volume24h"],
            "dex_liq_usd": u.get("dex_liq"), "dex_vol_24h_usd": u.get("dex_vol"),
            "flags": list(u["flags"]),
            "metrics": {},
        }
        for st in STAGES:
            r = st.compute(tok, cfg)
            tok["metrics"].update(r.get("metrics", {}))
            tok.update(r.get("fields", {}))
            tok["flags"] += r.get("flags", [])
        tok["raw"] = {"alpha": a, "perp_symbols": [c["symbol"] for c in u["contracts"].values()],
                      "mark": pm.get("mark"), "multiplier": mult}
        tokens.append(tok)

    # 3. 落库 + 导出（导出最后做，且原子替换）
    if not args.no_store:
        store.save(args.db, ts, tokens, len(unmatched), errors)
    export.export(args.out, ts, STAGE, cfg, tokens, unmatched, errors)
    print("wrote %s (%d tokens, %d soft errors)" % (args.out, len(tokens), len(errors)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
