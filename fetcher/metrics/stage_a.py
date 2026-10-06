"""A 阶段：杠杆相对筹码的静态比率。

阶段接口：compute(tok, cfg) -> {"metrics": {...}, "fields": {...}, "flags": [...]}
后续 stage_b / stage_c / scoring 实现同样接口并加入 main.STAGES 即可。
"""
from __future__ import annotations


def level(value, spec):
    if value is None:
        return "na"
    if spec["direction"] == "high":
        return "alert" if value >= spec["alert"] else "warn" if value >= spec["warn"] else "ok"
    return "alert" if value <= spec["alert"] else "warn" if value <= spec["warn"] else "ok"


def _div(a, b):
    return a / b if a is not None and b else None


def _pick_circ(tok, ov, flags):
    alpha, cg = tok.get("circ_supply"), tok.get("circ_supply_cg")
    src = ov.get("circ_source", "alpha")
    if src == "manual" and ov.get("circ_supply"):
        return float(ov["circ_supply"])
    if src == "cg" and cg:
        return cg
    return alpha or None


def compute(tok, cfg):
    sa = cfg["stage_a"]["metrics"]
    flags = []
    circ = _pick_circ(tok, tok.get("override") or {}, flags)
    total, price = tok.get("total_supply") or None, tok.get("price")

    a, g = tok.get("circ_supply"), tok.get("circ_supply_cg")
    if a and g and abs(a - g) / max(a, g) > cfg["circ_mismatch_pct"]:
        flags.append("circ_mismatch")
    if tok.get("dex_liq_usd") == 0:
        flags.append("no_dex_liq")

    mcap = price * circ if price and circ else None
    fdv = price * total if price and total else None
    vals = {
        "oi_to_mcap": _div(tok.get("oi_usd"), mcap),
        "oi_to_dex_liq": _div(tok.get("oi_usd"), tok.get("dex_liq_usd")),
        "perp_to_spot_vol": _div(tok.get("perp_vol_24h_usd"), tok.get("dex_vol_24h_usd")),
        "float_ratio": _div(circ, total),
    }
    metrics = {k: {"value": v, "level": level(v, sa[k])} for k, v in vals.items()}
    n = lambda lv: sum(1 for m in metrics.values() if m["level"] == lv)
    return {
        "metrics": metrics,
        "fields": {"circ_used": circ, "mcap_usd": mcap, "fdv_usd": fdv, "fdv_to_mcap": _div(fdv, mcap),
                   "cond_level": {"alert": n("alert"), "warn": n("warn")}},
        "flags": flags,
    }
