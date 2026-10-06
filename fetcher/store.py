from __future__ import annotations

import json
import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
  ts_utc TEXT NOT NULL, ticker TEXT NOT NULL, perp_symbol TEXT, chain TEXT, address TEXT,
  price REAL, oi_usd REAL, perp_vol_24h_usd REAL, funding_rate REAL,
  circ_supply REAL, total_supply REAL, circ_supply_cg REAL,
  alpha_vol_24h_usd REAL, dex_liq_usd REAL, dex_vol_24h_usd REAL,
  oi_to_mcap REAL, oi_to_dex_liq REAL, perp_to_spot_vol REAL, float_ratio REAL,
  raw_json TEXT,
  PRIMARY KEY (ts_utc, ticker)
);
CREATE TABLE IF NOT EXISTS runs (ts_utc TEXT PRIMARY KEY, n_universe INT, n_unmatched INT, errors TEXT);
"""

COLS = ["ticker", "perp_symbol", "chain", "address", "price", "oi_usd", "perp_vol_24h_usd", "funding_rate",
        "circ_supply", "total_supply", "circ_supply_cg", "alpha_vol_24h_usd", "dex_liq_usd", "dex_vol_24h_usd"]
METRIC_COLS = ["oi_to_mcap", "oi_to_dex_liq", "perp_to_spot_vol", "float_ratio"]


def save(db_path, ts, tokens, n_unmatched, errors):
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    with con:
        for t in tokens:
            row = [ts] + [t.get(c) for c in COLS] + [(t["metrics"].get(m) or {}).get("value") for m in METRIC_COLS]
            raw = json.dumps(t.get("raw") or {}, ensure_ascii=False, separators=(",", ":"))
            con.execute("INSERT OR REPLACE INTO snapshots VALUES (%s)" % ",".join("?" * (len(row) + 1)), row + [raw])
        con.execute("INSERT OR REPLACE INTO runs VALUES (?,?,?,?)",
                    (ts, len(tokens), n_unmatched, json.dumps(errors, ensure_ascii=False)))
    con.close()
