# -*- coding: utf-8 -*-
"""
Position sizing — turning a risk budget into a number of shares.

1. Fixed-fractional risk: lose at most `risk_pct` of capital if the stop hits.
       shares = capital * risk_pct / (entry - stop)
2. Volatility stop: stop = entry * exp(-k * sigma_daily * sqrt(h))
   (k standard deviations of an h-day move; replaces a gut-feel stop).
3. Volatility targeting: weight = target_vol / asset_vol (capped).
4. Kelly (continuous-time, CQF M2): f* = (mu - r) / sigma^2.
   Full Kelly is very aggressive and assumes mu is known; most practitioners use
   1/4 to 1/2 Kelly because estimation error in mu is large.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def vol_stop(entry: float, sigma_annual: float, k: float = 2.0, horizon_days: int = 5,
             periods: int = 252) -> float:
    sd = sigma_annual / math.sqrt(periods) * math.sqrt(horizon_days)
    return float(entry * math.exp(-k * sd))


def atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """Average True Range from a frame with high/low/close columns."""
    prev_close = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_close).abs(),
                    (df["low"] - prev_close).abs()], axis=1).max(axis=1)
    return tr.rolling(window).mean().rename("ATR")


def fixed_fractional_shares(capital: float, risk_pct: float, entry: float, stop: float,
                            lot_size: int = 1, max_weight: float = 1.0) -> dict:
    """Shares such that hitting the stop loses `risk_pct` of capital (before costs)."""
    if entry <= stop:
        raise ValueError("stop must be below entry for a long position")
    raw = capital * risk_pct / (entry - stop)
    cap = capital * max_weight / entry
    shares = math.floor(min(raw, cap) / lot_size) * lot_size
    return {"shares": int(shares), "position_value": shares * entry,
            "weight": shares * entry / capital if capital else 0.0,
            "loss_at_stop": shares * (entry - stop),
            "capped_by_max_weight": raw > cap}


def vol_target_weight(target_vol: float, asset_vol: float, max_weight: float = 1.0) -> float:
    if asset_vol <= 0:
        return 0.0
    return float(min(target_vol / asset_vol, max_weight))


def kelly_fraction(mu: float, sigma: float, r: float = 0.0) -> float:
    """Continuous-time Kelly leverage f* = (mu - r) / sigma^2 (can be > 1 or < 0)."""
    if sigma <= 0:
        return 0.0
    return float((mu - r) / sigma ** 2)


def kelly_growth(f: float, mu: float, sigma: float, r: float = 0.0) -> float:
    """Expected log-growth g(f) = r + f(mu - r) - f^2 sigma^2 / 2. Peaks at f*."""
    return float(r + f * (mu - r) - 0.5 * f ** 2 * sigma ** 2)


def kelly_curve(mu: float, sigma: float, r: float = 0.0, f_max: float = None, n: int = 101) -> pd.DataFrame:
    fstar = kelly_fraction(mu, sigma, r)
    hi = f_max if f_max is not None else max(2.5 * abs(fstar), 1.0)
    fs = np.linspace(0, hi, n)
    return pd.DataFrame({"fraction": fs, "growth": [kelly_growth(f, mu, sigma, r) for f in fs]})
