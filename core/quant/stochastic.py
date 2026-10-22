# -*- coding: utf-8 -*-
"""
CQF Module 1 — Stochastic processes: Geometric Brownian Motion (GBM).

Model:  dS = mu * S dt + sigma * S dW
Itô's lemma on ln S gives the exact solution
        S_T = S_0 * exp((mu - sigma^2 / 2) * T + sigma * W_T)
so ln S_T is normal with mean ln S_0 + (mu - sigma^2/2) T and variance sigma^2 T.

The "- sigma^2 / 2" term is the Itô correction. It is why the MEDIAN price
grows slower than the MEAN price:
        E[S_T]      = S_0 * exp(mu * T)
        median(S_T) = S_0 * exp((mu - sigma^2 / 2) * T)

Units: mu and sigma are annual; T is in years; TRADING_DAYS converts days.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np
import pandas as pd
from scipy.stats import norm

TRADING_DAYS = 252


@dataclass
class GBMParams:
    """Annualised GBM parameters estimated from a price history."""
    mu: float       # annual drift of the price (arithmetic)
    sigma: float    # annual volatility
    n_obs: int

    @property
    def log_drift(self) -> float:
        """Annual drift of ln S (= mu - sigma^2/2)."""
        return self.mu - 0.5 * self.sigma ** 2


def estimate_gbm_params(prices: pd.Series, periods: int = TRADING_DAYS) -> GBMParams:
    """
    Estimate GBM parameters from prices by maximum likelihood on log returns.

    log return x = ln(S_t / S_{t-1}) ~ N((mu - sigma^2/2) dt, sigma^2 dt)
    => sigma = std(x) * sqrt(periods),  mu = mean(x) * periods + sigma^2 / 2
    """
    x = np.log(prices.astype(float)).diff().dropna()
    if len(x) < 2:
        raise ValueError("need at least 3 prices")
    sigma = float(x.std(ddof=1) * np.sqrt(periods))
    mu = float(x.mean() * periods + 0.5 * sigma ** 2)
    return GBMParams(mu=mu, sigma=sigma, n_obs=len(x))


def simulate_gbm(
    s0: float,
    mu: float,
    sigma: float,
    n_days: int,
    n_paths: int = 1000,
    seed: Optional[int] = None,
    periods: int = TRADING_DAYS,
) -> np.ndarray:
    """
    Simulate GBM paths with the exact (log-normal) scheme. No discretisation bias.

    Returns array of shape (n_days + 1, n_paths); row 0 equals s0.
    """
    rng = np.random.default_rng(seed)
    dt = 1.0 / periods
    z = rng.standard_normal((n_days, n_paths))
    increments = (mu - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * z
    log_paths = np.vstack([np.zeros((1, n_paths)), np.cumsum(increments, axis=0)])
    return s0 * np.exp(log_paths)


def terminal_quantiles(
    s0: float,
    mu: float,
    sigma: float,
    horizons_days: Iterable[int],
    quantiles: Iterable[float] = (0.05, 0.25, 0.5, 0.75, 0.95),
    periods: int = TRADING_DAYS,
) -> pd.DataFrame:
    """
    Analytic price cone: quantiles of S_T for each horizon (no simulation needed).

    q-quantile of S_T = S_0 * exp((mu - sigma^2/2) T + sigma sqrt(T) * z_q)
    """
    rows = []
    for d in horizons_days:
        t = d / periods
        row = {"days": d}
        for q in quantiles:
            row[f"q{int(round(q * 100)):02d}"] = s0 * np.exp(
                (mu - 0.5 * sigma ** 2) * t + sigma * np.sqrt(t) * norm.ppf(q)
            )
        row["mean"] = s0 * np.exp(mu * t)
        rows.append(row)
    return pd.DataFrame(rows).set_index("days")


def prob_terminal_above(s0: float, level: float, mu: float, sigma: float,
                        n_days: int, periods: int = TRADING_DAYS) -> float:
    """P(S_T >= level) under GBM, T = n_days / periods."""
    t = n_days / periods
    if t <= 0 or sigma <= 0:
        return float(s0 >= level)
    d = (np.log(s0 / level) + (mu - 0.5 * sigma ** 2) * t) / (sigma * np.sqrt(t))
    return float(norm.cdf(d))


def prob_touch(s0: float, level: float, mu: float, sigma: float,
               n_days: int, periods: int = TRADING_DAYS) -> float:
    """
    Probability that the price TOUCHES `level` at any time within n_days
    (first-passage of Brownian motion with drift; reflection principle).

    With X_t = ln(S_t / S_0), nu = mu - sigma^2/2, b = ln(level / S_0):
      up   (b > 0): P = N((-b + nu T)/(s sqrt T)) + exp(2 nu b / s^2) N((-b - nu T)/(s sqrt T))
      down (b < 0): P = N(( b - nu T)/(s sqrt T)) + exp(2 nu b / s^2) N(( b + nu T)/(s sqrt T))
    """
    t = n_days / periods
    b = np.log(level / s0)
    if b == 0:
        return 1.0
    if t <= 0 or sigma <= 0:
        return 0.0
    nu = mu - 0.5 * sigma ** 2
    st = sigma * np.sqrt(t)
    k = np.exp(2 * nu * b / sigma ** 2)
    if b > 0:
        p = norm.cdf((-b + nu * t) / st) + k * norm.cdf((-b - nu * t) / st)
    else:
        p = norm.cdf((b - nu * t) / st) + k * norm.cdf((b + nu * t) / st)
    return float(min(max(p, 0.0), 1.0))


def ito_gap(mu: float, sigma: float, n_days: int, periods: int = TRADING_DAYS) -> dict:
    """Mean vs median growth over the horizon — the Itô correction made visible."""
    t = n_days / periods
    return {
        "mean_growth": float(np.exp(mu * t) - 1),
        "median_growth": float(np.exp((mu - 0.5 * sigma ** 2) * t) - 1),
        "volatility_drag_annual": 0.5 * sigma ** 2,
    }
