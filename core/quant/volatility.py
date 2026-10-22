# -*- coding: utf-8 -*-
"""
CQF Module 2 — Volatility modelling: realised, EWMA and GARCH(1,1).

Why it matters: volatility clusters (calm days follow calm days, wild days
follow wild days). A constant-sigma model (normal VaR, plain GBM) ignores this.

EWMA (RiskMetrics):  s2_t = lam * s2_{t-1} + (1 - lam) * r_{t-1}^2
GARCH(1,1):          s2_t = omega + alpha * r_{t-1}^2 + beta * s2_{t-1}
  persistence  = alpha + beta  (< 1 for stationarity)
  long-run var = omega / (1 - alpha - beta)
  k-step forecast: E[s2_{t+k}] = VL + (alpha + beta)^(k-1) * (s2_{t+1} - VL)

All returns are decimal daily log returns. Outputs are decimal (0.02 = 2%).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from scipy.optimize import minimize

TRADING_DAYS = 252


def log_returns(prices: pd.Series) -> pd.Series:
    return np.log(prices.astype(float)).diff().dropna()


def realized_vol(returns: pd.Series, window: int = 20, periods: int = TRADING_DAYS) -> pd.Series:
    """Rolling annualised standard deviation."""
    return returns.rolling(window).std() * np.sqrt(periods)


def ewma_variance(returns: pd.Series, lam: float = 0.94) -> pd.Series:
    """
    One-step-ahead EWMA variance. Value at index t uses information up to t-1,
    so it is a genuine forecast (safe for VaR backtesting).
    """
    r = returns.values.astype(float)
    s2 = np.empty_like(r)
    s2[0] = np.var(r[: min(len(r), 30)]) if len(r) > 1 else r[0] ** 2
    for t in range(1, len(r)):
        s2[t] = lam * s2[t - 1] + (1 - lam) * r[t - 1] ** 2
    return pd.Series(s2, index=returns.index, name="ewma_var")


@dataclass
class GarchResult:
    omega: float
    alpha: float
    beta: float
    mu: float
    loglik: float
    converged: bool
    cond_var: pd.Series = field(repr=False)   # one-step-ahead variance, aligned to returns
    next_var: float = 0.0                      # forecast for the day after the sample

    @property
    def persistence(self) -> float:
        return self.alpha + self.beta

    @property
    def long_run_var(self) -> float:
        p = self.persistence
        return self.omega / (1 - p) if p < 1 else float("nan")

    @property
    def long_run_vol_annual(self) -> float:
        return float(np.sqrt(self.long_run_var * TRADING_DAYS))

    @property
    def half_life_days(self) -> float:
        """Days for a variance shock to decay by half."""
        p = self.persistence
        return float(np.log(0.5) / np.log(p)) if 0 < p < 1 else float("inf")

    def forecast_variance(self, horizon: int) -> np.ndarray:
        """Daily variance forecasts for steps 1..horizon."""
        vl = self.long_run_var
        k = np.arange(horizon)
        return vl + self.persistence ** k * (self.next_var - vl)

    def term_structure_annual(self, horizons=(1, 5, 21, 63, 126, 252)) -> pd.Series:
        """Annualised average vol expected over each horizon (vol term structure)."""
        f = self.forecast_variance(max(horizons))
        return pd.Series(
            {h: float(np.sqrt(f[:h].mean() * TRADING_DAYS)) for h in horizons},
            name="garch_vol",
        )


def _garch_filter(eps: np.ndarray, omega: float, alpha: float, beta: float, s2_0: float) -> np.ndarray:
    s2 = np.empty(len(eps) + 1)
    s2[0] = s2_0
    for t in range(1, len(eps) + 1):
        s2[t] = omega + alpha * eps[t - 1] ** 2 + beta * s2[t - 1]
    return s2  # s2[t] = variance forecast for eps[t]; last element is out-of-sample


def fit_garch11(returns: pd.Series) -> GarchResult:
    """
    Gaussian quasi-MLE of GARCH(1,1) with constant mean.

    Returns are scaled by 100 internally for numerical stability, then scaled back.
    """
    r = returns.dropna().values.astype(float)
    if len(r) < 100:
        raise ValueError("GARCH needs at least 100 observations")
    scale = 100.0
    x = r * scale
    mu0 = x.mean()
    var0 = x.var()

    def unpack(p):
        return p[0], p[1], p[2], p[3]

    def nll(p):
        mu, omega, alpha, beta = unpack(p)
        if omega <= 0 or alpha < 0 or beta < 0 or alpha + beta >= 0.9999:
            return 1e10
        eps = x - mu
        s2 = _garch_filter(eps, omega, alpha, beta, var0)[:-1]
        if np.any(s2 <= 0):
            return 1e10
        return 0.5 * np.sum(np.log(2 * np.pi) + np.log(s2) + eps ** 2 / s2)

    best = None
    for a0, b0 in [(0.05, 0.90), (0.10, 0.85), (0.03, 0.95)]:
        p0 = np.array([mu0, var0 * (1 - a0 - b0), a0, b0])
        res = minimize(
            nll, p0, method="SLSQP",
            bounds=[(None, None), (1e-8, None), (0.0, 1.0), (0.0, 1.0)],
            constraints=[{"type": "ineq", "fun": lambda p: 0.9999 - p[2] - p[3]}],
            options={"maxiter": 500},
        )
        if best is None or res.fun < best.fun:
            best = res

    mu, omega, alpha, beta = unpack(best.x)
    eps = x - mu
    s2_all = _garch_filter(eps, omega, alpha, beta, var0)
    idx = returns.dropna().index
    return GarchResult(
        omega=float(omega / scale ** 2),
        alpha=float(alpha),
        beta=float(beta),
        mu=float(mu / scale),
        loglik=float(-best.fun),
        converged=bool(best.success),
        cond_var=pd.Series(s2_all[:-1] / scale ** 2, index=idx, name="garch_var"),
        next_var=float(s2_all[-1] / scale ** 2),
    )


def vol_regime(current: float, history: pd.Series) -> dict:
    """
    Classify today's volatility by its percentile in its own history.

    < 25th pct 'low'; 25–75 'normal'; 75–95 'high'; > 95 'extreme'.
    """
    h = history.dropna()
    if h.empty:
        return {"percentile": float("nan"), "regime": "unknown"}
    pct = float((h < current).mean() * 100)
    if pct < 25:
        regime = "低波動"
    elif pct < 75:
        regime = "正常"
    elif pct < 95:
        regime = "高波動"
    else:
        regime = "極端"
    return {"percentile": pct, "regime": regime}


def best_available_vol(returns: pd.Series, lam: float = 0.94) -> dict:
    """
    GARCH when it fits and is stationary; otherwise EWMA. Returns annualised
    next-day vol and the model actually used (honest fallback).
    """
    try:
        g = fit_garch11(returns)
        if g.converged and g.persistence < 0.999:
            return {"model": "GARCH(1,1)", "vol_annual": float(np.sqrt(g.next_var * TRADING_DAYS)),
                    "series_var": g.cond_var, "garch": g}
    except Exception:
        pass
    e = ewma_variance(returns, lam)
    nxt = lam * e.iloc[-1] + (1 - lam) * returns.iloc[-1] ** 2
    return {"model": f"EWMA(λ={lam})", "vol_annual": float(np.sqrt(nxt * TRADING_DAYS)),
            "series_var": e, "garch": None}
