# -*- coding: utf-8 -*-
"""
Verifiable market-structure signals (replaces untestable "teacher" rules).

1. TAIFEX settlement days: TX monthly futures/options settle on the third
   Wednesday of the month (moved to the next business day on holidays —
   this module does NOT know Taiwan holidays; dates are approximate).
   Claim to test: "settlement days are more volatile".
2. Event study: compare |return| on event days vs other days (Welch t-test).
3. Cycle position: where price sits in its own history (52-week range,
   distance from 200-day MA, drawdown, 12-1 momentum).
4. Percentile of any level series (e.g. market margin balance 融資餘額).
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from scipy.stats import ttest_ind


def third_wednesdays(start, end) -> pd.DatetimeIndex:
    months = pd.date_range(pd.Timestamp(start).to_period("M").to_timestamp(),
                           pd.Timestamp(end), freq="MS")
    out = []
    for m in months:
        first = m.weekday()            # Mon=0 … Wed=2
        offset = (2 - first) % 7
        d = m + pd.Timedelta(days=offset + 14)
        if pd.Timestamp(start) <= d <= pd.Timestamp(end):
            out.append(d)
    return pd.DatetimeIndex(out)


def align_to_trading_days(events: pd.DatetimeIndex, trading_index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Move each event to the first trading day on/after it (handles holidays approximately)."""
    idx = pd.DatetimeIndex(trading_index).sort_values()
    pos = idx.searchsorted(events)
    pos = pos[pos < len(idx)]
    return pd.DatetimeIndex(sorted(set(idx[pos])))


def event_study(returns: pd.Series, events: pd.DatetimeIndex) -> dict:
    r = returns.dropna()
    ev = align_to_trading_days(events, r.index)
    mask = r.index.isin(ev)
    a, b = r[mask].abs(), r[~mask].abs()
    if len(a) < 3 or len(b) < 3:
        return {"n_events": int(mask.sum()), "p_value": float("nan")}
    t = ttest_ind(a, b, equal_var=False)
    return {"n_events": int(mask.sum()), "mean_abs_event": float(a.mean()),
            "mean_abs_other": float(b.mean()), "ratio": float(a.mean() / b.mean()),
            "t_stat": float(t.statistic), "p_value": float(t.pvalue),
            "significant_5pct": bool(t.pvalue < 0.05), "event_days": ev}


def next_settlement(today: date | None = None) -> pd.Timestamp:
    today = pd.Timestamp(today or date.today()).normalize()
    cands = third_wednesdays(today, today + pd.Timedelta(days=70))
    return cands[0]


def cycle_position(close: pd.Series) -> dict:
    c = close.dropna().astype(float)
    last = c.iloc[-1]
    w = c.iloc[-252:]
    hi, lo = w.max(), w.min()
    ma200 = c.rolling(200).mean().iloc[-1] if len(c) >= 200 else np.nan
    mom = c.iloc[-22] / c.iloc[-253] - 1 if len(c) >= 253 else np.nan
    return {
        "pct_of_52w_range": float((last - lo) / (hi - lo)) if hi > lo else float("nan"),
        "dist_ma200": float(last / ma200 - 1) if np.isfinite(ma200) else float("nan"),
        "drawdown_from_52w_high": float(last / hi - 1),
        "momentum_12_1": float(mom) if np.isfinite(mom) else float("nan"),
        "above_ma200": bool(last > ma200) if np.isfinite(ma200) else None,
    }


def series_percentile(series: pd.Series, lookback: int = 750) -> float:
    s = series.dropna().iloc[-lookback:]
    if s.empty:
        return float("nan")
    return float((s < s.iloc[-1]).mean() * 100)
