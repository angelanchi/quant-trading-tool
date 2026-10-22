# -*- coding: utf-8 -*-
"""
CQF Module 2 — CAPM / single-index model.

Regression on excess returns:  (R_i - r_f) = alpha + beta * (R_m - r_f) + e
  beta   — sensitivity to the market (systematic risk)
  alpha  — return NOT explained by the market (Jensen's alpha)
  R^2    — share of variance explained by the market
Total variance = beta^2 * var(R_m) + var(e)   (systematic + idiosyncratic)

A positive alpha only matters if its t-statistic is large (|t| > ~2).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import t as student_t

TRADING_DAYS = 252


@dataclass
class CAPMResult:
    alpha_daily: float
    beta: float
    alpha_t: float
    beta_t: float
    alpha_p: float
    r_squared: float
    n_obs: int
    systematic_var_annual: float
    idio_var_annual: float
    periods: int = TRADING_DAYS

    @property
    def alpha_annual(self) -> float:
        return self.alpha_daily * self.periods

    @property
    def systematic_share(self) -> float:
        tot = self.systematic_var_annual + self.idio_var_annual
        return self.systematic_var_annual / tot if tot > 0 else float("nan")


def capm_regression(asset_returns: pd.Series, market_returns: pd.Series,
                    rf_annual: float = 0.015, periods: int = TRADING_DAYS) -> CAPMResult:
    df = pd.concat([asset_returns.rename("a"), market_returns.rename("m")], axis=1).dropna()
    if len(df) < 30:
        raise ValueError("need at least 30 overlapping observations")
    rf = rf_annual / periods
    y = df["a"].values - rf
    x = df["m"].values - rf
    n = len(y)
    X = np.column_stack([np.ones(n), x])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    dof = n - 2
    s2 = resid @ resid / dof
    cov = s2 * np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(cov))
    with np.errstate(divide="ignore", invalid="ignore"):
        tvals = np.where(se > 1e-12, coef / se, np.nan)  # asset == market -> t undefined
    ss_tot = np.sum((y - y.mean()) ** 2)
    r2 = 1 - (resid @ resid) / ss_tot if ss_tot > 0 else float("nan")
    beta = float(coef[1])
    return CAPMResult(
        alpha_daily=float(coef[0]), beta=beta,
        alpha_t=float(tvals[0]), beta_t=float(tvals[1]),
        alpha_p=float(2 * (1 - student_t.cdf(abs(tvals[0]), dof))) if np.isfinite(tvals[0]) else float("nan"),
        r_squared=float(r2), n_obs=n,
        systematic_var_annual=float(beta ** 2 * np.var(x, ddof=1) * periods),
        idio_var_annual=float(np.var(resid, ddof=1) * periods),
        periods=periods,
    )


def rolling_beta(asset_returns: pd.Series, market_returns: pd.Series, window: int = 120) -> pd.Series:
    df = pd.concat([asset_returns.rename("a"), market_returns.rename("m")], axis=1).dropna()
    cov = df["a"].rolling(window).cov(df["m"])
    var = df["m"].rolling(window).var()
    return (cov / var).rename("beta")
