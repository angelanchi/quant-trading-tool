# -*- coding: utf-8 -*-
"""
Download real daily prices for the watchlist into data/prices/*.csv.

Why a separate script: the panel should not hit the network on every page
load, and this script needs only the Python standard library (no pip install).

Sources (first that works wins, per symbol):
  1. Yahoo Finance chart API — dividend/split ADJUSTED prices (Taiwan: 2330.TW / .TWO)
  2. FinMind TaiwanStockPrice (Taiwan only) — UNADJUSTED; used only if Yahoo fails
     (FinMind's adjusted dataset needs a paid tier.)
Also saves FRED 10Y / 2Y / 3M Treasury yields to data/macro/ (risk-free rate).

Usage:
  python scripts/fetch_market_data.py                # core groups + benchmarks, 12 years
  python scripts/fetch_market_data.py --all          # every watchlist group (~100 symbols)
  python scripts/fetch_market_data.py 2330 NVDA      # specific symbols
  python scripts/fetch_market_data.py --years 5
Keys are read from .env and are never printed.
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
PRICE_DIR = ROOT / "data" / "prices"
MACRO_DIR = ROOT / "data" / "macro"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
BENCHMARKS = ["0050", "SPY", "QQQ"]


def load_env() -> dict:
    env = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def http_get(url: str, headers: dict | None = None, timeout: int = 30) -> bytes:
    """urllib first; on TLS/network errors fall back to curl.exe (Windows Schannel)."""
    hdr = {"User-Agent": UA, **(headers or {})}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise                       # rate limit: caller backs off
        err = e                         # 403 etc.: some CDNs reject Python's TLS fingerprint
    except Exception as e:
        err = e
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        raise err
    cmd = [curl, "-s", "--fail", "--max-time", str(timeout)]
    for k, v in hdr.items():
        cmd += ["-H", f"{k}: {v}"]
    out = subprocess.run(cmd + [url], capture_output=True)
    if out.returncode != 0:
        raise RuntimeError(f"urllib: {type(err).__name__}; curl exit {out.returncode}")
    return out.stdout


def is_tw(sym: str) -> bool:
    return sym.split(".")[0][:4].isdigit()


def yahoo(sym: str, years: int) -> list[dict]:
    cands = [sym] if not is_tw(sym) or "." in sym else [f"{sym}.TW", f"{sym}.TWO"]
    p2 = int(time.time())
    p1 = int((datetime.now(timezone.utc) - timedelta(days=int(years * 365.25))).timestamp())
    for c in cands:
        url = (f"https://query2.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(c)}"
               f"?period1={p1}&period2={p2}&interval=1d&events=div%2Csplit&includeAdjustedClose=true")
        for attempt in range(2):
            try:
                j = json.loads(http_get(url, timeout=15))
                break
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    time.sleep(3)
                    continue
                j = None
                break
            except Exception:
                j = None
                break
        else:
            j = None
        res = (j or {}).get("chart", {}).get("result")
        if not res:
            continue
        r = res[0]
        ts = r.get("timestamp") or []
        q = r["indicators"]["quote"][0]
        adj = (r["indicators"].get("adjclose") or [{}])[0].get("adjclose") or q["close"]
        tz = r.get("meta", {}).get("gmtoffset", 0)
        rows = []
        for i, t in enumerate(ts):
            c_raw, a = q["close"][i], adj[i]
            if c_raw in (None, 0) or a is None or q["open"][i] is None:
                continue
            f = a / c_raw
            rows.append({"date": datetime.fromtimestamp(t + tz, timezone.utc).strftime("%Y-%m-%d"),
                         "open": q["open"][i] * f, "high": q["high"][i] * f, "low": q["low"][i] * f,
                         "close": a, "volume": q["volume"][i] or 0, "raw_close": c_raw})
        if len(rows) > 60:
            return rows
    return []


def finmind(sym: str, years: int, token: str) -> list[dict]:
    start = (datetime.now() - timedelta(days=int(years * 365.25))).strftime("%Y-%m-%d")
    url = "https://api.finmindtrade.com/api/v4/data?" + urllib.parse.urlencode(
        {"dataset": "TaiwanStockPrice", "data_id": sym.split(".")[0], "start_date": start})
    j = json.loads(http_get(url, {"Authorization": f"Bearer {token}"} if token else None))
    rows = []
    for d in j.get("data", []):
        if d.get("close"):
            rows.append({"date": d["date"], "open": d["open"], "high": d["max"], "low": d["min"],
                         "close": d["close"], "volume": d["Trading_Volume"], "raw_close": d["close"]})
    return rows


def finmind_adjust(sym: str, rows: list[dict], years: int, token: str) -> tuple[list[dict], bool]:
    """
    Back-adjust FinMind raw prices with TaiwanStockDividendResult (free dataset).
    On each ex-date d: factor = after_price / before_price; every price BEFORE d is
    multiplied by the product of all later factors. Same idea as Yahoo's adjclose.
    """
    start = (datetime.now() - timedelta(days=int(years * 365.25))).strftime("%Y-%m-%d")
    url = "https://api.finmindtrade.com/api/v4/data?" + urllib.parse.urlencode(
        {"dataset": "TaiwanStockDividendResult", "data_id": sym.split(".")[0], "start_date": start})
    try:
        j = json.loads(http_get(url, {"Authorization": f"Bearer {token}"} if token else None))
        events = sorted((d["date"], d["after_price"] / d["before_price"]) for d in j.get("data", [])
                        if d.get("before_price") and d.get("after_price"))
    except Exception:
        return rows, False
    if not events:
        return rows, True
    for r in rows:
        f = 1.0
        for d, k in events:
            if r["date"] < d:
                f *= k
        for c in ("open", "high", "low", "close"):
            r[c] = r[c] * f
    return rows, True


def fred(series: str, key: str, years: int) -> list[dict]:
    start = (datetime.now() - timedelta(days=int(years * 365.25))).strftime("%Y-%m-%d")
    url = ("https://api.stlouisfed.org/fred/series/observations?" + urllib.parse.urlencode(
        {"series_id": series, "observation_start": start, "file_type": "json", "api_key": key}))
    j = json.loads(http_get(url))
    return [{"date": o["date"], "value": float(o["value"]) / 100}
            for o in j.get("observations", []) if o["value"] not in (".", "")]


CORE_GROUPS = ["範例組合", "我的持股", "台股_觀察_金融", "美股_我的關注", "台股_AI_半導體", "美股_AI_七巨頭"]


def watchlist_symbols(groups: list[str] | None = None) -> list[str]:
    raw = json.loads((ROOT / "config" / "watchlists.json").read_text(encoding="utf-8"))
    out = []
    for name, g in raw.items():
        if groups is not None and name not in groups:
            continue
        if isinstance(g, dict) and "symbols" in g:
            out += [s for s in g["symbols"] if s not in out]
    return out


def write_csv(path: pathlib.Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("symbols", nargs="*")
    ap.add_argument("--years", type=int, default=12)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--all", action="store_true", help="every watchlist group (about 100 symbols)")
    a = ap.parse_args()
    env = load_env()
    syms = a.symbols or list(dict.fromkeys(BENCHMARKS + watchlist_symbols(None if a.all else CORE_GROUPS)))
    manifest_path = PRICE_DIR / "_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    from concurrent.futures import ThreadPoolExecutor

    def one(s):
        t0 = time.time()
        src, rows, err = "", [], []
        try:
            rows = yahoo(s, a.years)
            src = "Yahoo（還原權值）"
        except Exception as e:
            err.append(f"Yahoo {type(e).__name__}")
        if not rows and is_tw(s):
            try:
                rows = finmind(s, a.years, env.get("FINMIND_API_TOKEN", ""))
                rows, adjusted = finmind_adjust(s, rows, a.years, env.get("FINMIND_API_TOKEN", ""))
                src = "FinMind（除權息還原）" if adjusted else "FinMind（未還原權值）"
            except Exception as e:
                err.append(f"FinMind {type(e).__name__}")
        if rows:
            write_csv(PRICE_DIR / f"{s}.csv", rows)
        return s, src, rows, err, time.time() - t0

    ok, fail = 0, []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for s, src, rows, err, dt in ex.map(one, syms):
            if rows:
                manifest[s] = {"source": src, "rows": len(rows), "first": rows[0]["date"],
                               "last": rows[-1]["date"], "fetched": datetime.now().strftime("%Y-%m-%d %H:%M")}
                ok += 1
                print(f"OK   {s:8s} {len(rows):5d} rows  {rows[0]['date']} → {rows[-1]['date']}  {src}  ({dt:.1f}s)", flush=True)
            else:
                fail.append(s)
                print(f"FAIL {s:8s} {'; '.join(err) or 'no data'}  ({dt:.1f}s)", flush=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    key = env.get("FRED_API_KEY", "")
    if key:
        for series in ("DGS10", "DGS2", "DGS3MO"):
            try:
                rows = fred(series, key, a.years)
                write_csv(MACRO_DIR / f"{series}.csv", rows)
                print(f"OK   FRED {series} {len(rows)} rows, last {rows[-1]['date']} = {rows[-1]['value']:.2%}")
            except Exception as e:
                print(f"FAIL FRED {series}: {type(e).__name__}")
    print(f"\nDone: {ok} ok, {len(fail)} failed {fail if fail else ''}")
    return 0 if not fail else 1


if __name__ == "__main__":
    sys.exit(main())
