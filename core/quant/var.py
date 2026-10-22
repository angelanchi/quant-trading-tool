# -*- coding: utf-8 -*-
"""
CQF Module 2 — Value at Risk and VaR backtesting.

Sign convention in this module: VaR and ES are POSITIVE numbers = loss
fraction. "1-day 99% VaR = 0.03" means: on 1% of days we expect to lose
more than 3%.

Backtests (is the VaR model honest?):
  Kupiec POF        — is the NUMBER of exceptions consistent with 1 - cl?
  Christoffersen    — are exceptions INDEPENDENT (not clustered)?
  Basel traffic light — regulatory zone for 250 days at 99%.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm, chi2, binom


def var_historical(returns: pd.Series, cl: float = 0.99) -> float:
    return float(-np.quantile(returns.dropna(), 1 - cl))


def es_historical(returns: pd.Series, cl: float = 0.99) -> float:
    r = returns.dropna()
    q = np.quantile(r, 1 - cl)
    return float(-r[r <= q].mean())


def var_normal(returns: pd.Series, cl: float = 0.99, horizon: int = 1) -> float:
    r = returns.dropna()
    mu, s = r.mean(), r.std(ddof=1)
    return float(-(mu * horizon + norm.ppf(1 - cl) * s * np.sqrt(horizon)))


def es_normal(returns: pd.Series, cl: float = 0.99) -> float:
    r = returns.dropna()
    mu, s = r.mean(), r.std(ddof=1)
    return float(-mu + s * norm.pdf(norm.ppf(1 - cl)) / (1 - cl))


def var_cornish_fisher(returns: pd.Series, cl: float = 0.99) -> float:
    """
    Normal VaR adjusted for skewness S and excess kurtosis K:
      z_cf = z + (z^2-1) S/6 + (z^3-3z) K/24 - (2z^3-5z) S^2/36
    """
    r = returns.dropna()
    mu, s = r.mean(), r.std(ddof=1)
    S = float(r.skew())
    K = float(r.kurt())  # pandas returns EXCESS kurtosis
    z = norm.ppf(1 - cl)
    zcf = z + (z ** 2 - 1) * S / 6 + (z ** 3 - 3 * z) * K / 24 - (2 * z ** 3 - 5 * z) * S ** 2 / 36
    return float(-(mu + zcf * s))


def var_from_sigma(sigma_daily: float, cl: float = 0.99, mu_daily: float = 0.0) -> float:
    """Conditional (e.g. GARCH/EWMA) VaR from a one-day sigma forecast."""
    return float(-(mu_daily + norm.ppf(1 - cl) * sigma_daily))


def rolling_var_forecasts(returns: pd.Series, cl: float = 0.99, method: str = "historical",
                          window: int = 250, lam: float = 0.94) -> pd.Series:
    """
    Out-of-sample one-day VaR forecasts. Value at date t uses data up to t-1.
    method: 'historical' | 'normal' | 'ewma'
    """
    r = returns.dropna()
    if method == "ewma":
        from .volatility import ewma_variance
        s = np.sqrt(ewma_variance(r, lam))
        out = -norm.ppf(1 - cl) * s
        out.iloc[:window] = np.nan
        return out.rename("VaR")
    past = r.shift(1)
    if method == "historical":
        out = -past.rolling(window).quantile(1 - cl)
    elif method == "normal":
        out = -(past.rolling(window).mean() + norm.ppf(1 - cl) * past.rolling(window).std())
    else:
        raise ValueError(method)
    return out.rename("VaR")


def kupiec_pof(n_exceptions: int, n_obs: int, cl: float = 0.99) -> dict:
    """Kupiec (1995) proportion-of-failures likelihood-ratio test (chi^2, 1 df)."""
    p = 1 - cl
    x, n = n_exceptions, n_obs
    phat = x / n if n else 0.0

    def xlogy(a, b):  # a * ln(b) with the convention 0 * ln(0) = 0
        return 0.0 if a == 0 else a * np.log(b)

    ll_null = xlogy(n - x, 1 - p) + xlogy(x, p)
    ll_alt = xlogy(n - x, 1 - phat) + xlogy(x, phat)
    lr = -2 * (ll_null - ll_alt)
    pval = float(1 - chi2.cdf(lr, 1))
    return {"exceptions": x, "expected": n * p, "rate": phat, "LR": float(lr),
            "p_value": pval, "reject_at_5pct": pval < 0.05}


def christoffersen_independence(hits: pd.Series) -> dict:
    """Christoffersen (1998) test that exceptions are not clustered (chi^2, 1 df)."""
    h = hits.dropna().astype(int).values
    if len(h) < 2:
        return {"LR": float("nan"), "p_value": float("nan"), "reject_at_5pct": False}
    prev, cur = h[:-1], h[1:]
    n00 = int(np.sum((prev == 0) & (cur == 0)))
    n01 = int(np.sum((prev == 0) & (cur == 1)))
    n10 = int(np.sum((prev == 1) & (cur == 0)))
    n11 = int(np.sum((prev == 1) & (cur == 1)))
    pi0 = n01 / (n00 + n01) if (n00 + n01) else 0.0
    pi1 = n11 / (n10 + n11) if (n10 + n11) else 0.0
    pi = (n01 + n11) / (n00 + n01 + n10 + n11)

    def safe_log(v):
        return np.log(v) if v > 0 else 0.0

    l0 = (n00 + n10) * safe_log(1 - pi) + (n01 + n11) * safe_log(pi)
    l1 = n00 * safe_log(1 - pi0) + n01 * safe_log(pi0) + n10 * safe_log(1 - pi1) + n11 * safe_log(pi1)
    lr = float(-2 * (l0 - l1))
    pval = float(1 - chi2.cdf(lr, 1))
    return {"LR": lr, "p_value": pval, "reject_at_5pct": pval < 0.05,
            "p_exception_after_exception": pi1, "p_exception_after_normal": pi0}


def basel_traffic_light(n_exceptions: int, n_obs: int = 250, cl: float = 0.99) -> str:
    """Zone by cumulative binomial probability (Basel 1996): green < 95%, yellow < 99.99%."""
    c = binom.cdf(n_exceptions, n_obs, 1 - cl)
    if c < 0.95:
        return "綠燈 green"
    if c < 0.9999:
        return "黃燈 yellow"
    return "紅燈 red"


def backtest_var(returns: pd.Series, var_forecast: pd.Series, cl: float = 0.99) -> dict:
    """Run all three backtests on aligned (return, VaR) pairs."""
    df = pd.concat([returns.rename("r"), var_forecast.rename("var")], axis=1).dropna()
    hits = (df["r"] < -df["var"]).astype(int)
    k = kupiec_pof(int(hits.sum()), len(hits), cl)
    c = christoffersen_independence(hits)
    last = hits.iloc[-250:]
    return {"n_obs": len(hits), "kupiec": k, "christoffersen": c,
            "traffic_light_last_250": basel_traffic_light(int(last.sum()), len(last), cl),
            "hits": hits, "frame": df}
