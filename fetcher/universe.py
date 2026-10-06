"""Universe = Alpha ∩ 永续(TRADING) − 现货(TRADING)，含倍数前缀归一化与 overrides。"""
from __future__ import annotations

import re
from collections import defaultdict

_PREFIX = re.compile(r"^(1000000|10000|1000|1M)(.+)$")
_MULT = {"1000000": 1_000_000, "10000": 10_000, "1000": 1000, "1M": 1_000_000}


def normalize(base_asset):
    """'1000PEPE' → ('PEPE', 1000)；无前缀 → (原名, 1)。"""
    b = base_asset.upper()
    m = _PREFIX.match(b)
    if m:
        return m.group(2), _MULT[m.group(1)]
    return b, 1


def build(contracts, spot_assets, alpha, overrides, marks, cfg):
    """返回 (universe, unmatched)。

    universe 每项: ticker, multiplier, contracts{USDT/USDC: info}, primary, alpha, flags
    """
    spot_norm = {normalize(a)[0] for a in spot_assets} | set(spot_assets)

    groups = defaultdict(lambda: {"contracts": {}})
    for c in contracts:
        t, mult = normalize(c["baseAsset"])
        g = groups[t]
        g["multiplier"] = mult
        g["raw_base"] = c["baseAsset"].upper()
        g["contracts"][c["quoteAsset"]] = c

    by_symbol = defaultdict(list)
    by_addr = {}
    for a in alpha:
        by_symbol[a["symbol"]].append(a)
        by_addr[a["address"].lower()] = a

    universe, unmatched = [], []
    for ticker, g in sorted(groups.items()):
        primary = g["contracts"].get("USDT") or g["contracts"].get("USDC")
        psym = primary["symbol"]
        if ticker in spot_norm or g["raw_base"] in spot_norm:
            continue
        ov = overrides.get(psym) or {}
        if ov.get("exclude"):
            continue

        flags = []
        mark = (marks.get(psym) or {}).get("mark")
        unit_price = mark / g["multiplier"] if mark else None

        if ov.get("address"):
            chosen = by_addr.get(str(ov["address"]).lower())
            if not chosen:
                unmatched.append({"perp_symbol": psym, "reason": "override_address_not_in_alpha"})
                continue
            flags.append("override")
        else:
            cands = list(by_symbol.get(ticker, []))
            if not cands:
                continue  # 不在 Alpha：不属于监控范围，也不算未匹配
            tol = cfg["price_match_tolerance"]
            priced = [a for a in cands
                      if unit_price and a["price"] and abs(a["price"] / unit_price - 1) <= tol]
            if not priced:
                unmatched.append({"perp_symbol": psym, "reason": "alpha_price_mismatch",
                                  "detail": "同名 Alpha 币价格与合约价格不符，疑似同名不同币"})
                continue
            online = [a for a in priced if not a.get("offline")]
            priced = online if online else priced  # 有在线的同名币时，忽略已下线的
            if len(priced) == 1:
                chosen = priced[0]
            else:
                priced.sort(key=lambda a: a["liquidity"] or 0, reverse=True)
                top, second = (priced[0]["liquidity"] or 0), (priced[1]["liquidity"] or 0)
                if top >= cfg["multi_alpha_dominance"] * max(second, 1):
                    chosen = priced[0]
                    flags.append("multi_alpha")
                else:
                    unmatched.append({"perp_symbol": psym, "reason": "alpha_ambiguous",
                                      "detail": "Alpha 有 %d 个同名币，请用 overrides 指定地址" % len(priced)})
                    continue

        if chosen.get("offline"):
            flags.append("alpha_offline")
        universe.append({"ticker": ticker, "multiplier": g["multiplier"], "contracts": g["contracts"],
                         "primary": primary, "alpha": chosen, "flags": flags, "override": ov})
    return universe, unmatched
