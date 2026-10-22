# -*- coding: utf-8 -*-
"""
CQF Module 3 — Black-Scholes(-Merton) pricing, Greeks, implied vol, delta hedging.

  d1 = [ln(S/K) + (r - q + sigma^2/2) T] / (sigma sqrt T),  d2 = d1 - sigma sqrt T
  Call = S e^{-qT} N(d1) - K e^{-rT} N(d2)
  Put  = K e^{-rT} N(-d2) - S e^{-qT} N(-d1)
  Put-call parity: C - P = S e^{-qT} - K e^{-rT}

Greek units returned here (trader convention):
  delta  per 1 unit of S
  gamma  per 1 unit of S (change in delta)
  vega   per 1 vol POINT (sigma + 0.01)
  theta  per CALENDAR DAY (T in years / 365)
  rho    per 1 rate point (r + 0.01)
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm


def _d1d2(S, K, T, r, sigma, q=0.0):
    sqt = sigma * np.sqrt(T)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / sqt
    return d1, d1 - sqt


def bs_price(S, K, T, r, sigma, q=0.0, kind="call"):
    if T <= 0 or sigma <= 0:
        intrinsic = max(S - K, 0.0) if kind == "call" else max(K - S, 0.0)
        return float(intrinsic)
    d1, d2 = _d1d2(S, K, T, r, sigma, q)
    if kind == "call":
        return float(S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2))
    return float(K * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-q * T) * norm.cdf(-d1))


def bs_greeks(S, K, T, r, sigma, q=0.0, kind="call") -> dict:
    d1, d2 = _d1d2(S, K, T, r, sigma, q)
    pdf = norm.pdf(d1)
    dq, dr = np.exp(-q * T), np.exp(-r * T)
    gamma = dq * pdf / (S * sigma * np.sqrt(T))
    vega = S * dq * pdf * np.sqrt(T) / 100
    if kind == "call":
        delta = dq * norm.cdf(d1)
        theta = (-S * dq * pdf * sigma / (2 * np.sqrt(T)) - r * K * dr * norm.cdf(d2)
                 + q * S * dq * norm.cdf(d1)) / 365
        rho = K * T * dr * norm.cdf(d2) / 100
    else:
        delta = -dq * norm.cdf(-d1)
        theta = (-S * dq * pdf * sigma / (2 * np.sqrt(T)) + r * K * dr * norm.cdf(-d2)
                 - q * S * dq * norm.cdf(-d1)) / 365
        rho = -K * T * dr * norm.cdf(-d2) / 100
    return {"price": bs_price(S, K, T, r, sigma, q, kind), "delta": float(delta),
            "gamma": float(gamma), "vega": float(vega), "theta": float(theta), "rho": float(rho)}


def implied_vol(price, S, K, T, r, q=0.0, kind="call", lo=1e-4, hi=5.0) -> float:
    """Invert BS by Brent's method. NaN if the price violates no-arbitrage bounds."""
    intrinsic = max(S * np.exp(-q * T) - K * np.exp(-r * T), 0) if kind == "call" \
        else max(K * np.exp(-r * T) - S * np.exp(-q * T), 0)
    upper = S * np.exp(-q * T) if kind == "call" else K * np.exp(-r * T)
    if not (intrinsic - 1e-10 <= price <= upper):
        return float("nan")
    f = lambda s: bs_price(S, K, T, r, s, q, kind) - price
    try:
        return float(brentq(f, lo, hi, xtol=1e-10))
    except ValueError:
        return float("nan")


def parity_gap(call, put, S, K, T, r, q=0.0) -> float:
    """C - P - (S e^{-qT} - K e^{-rT}); non-zero = arbitrage (before costs)."""
    return float(call - put - (S * np.exp(-q * T) - K * np.exp(-r * T)))


def payoff(S_T, K, kind="call"):
    S_T = np.asarray(S_T, dtype=float)
    return np.maximum(S_T - K, 0) if kind == "call" else np.maximum(K - S_T, 0)


def delta_hedge_simulation(S0, K, T, r, sigma_implied, sigma_real, mu=0.0,
                           n_rebalance=52, n_paths=2000, seed=0, kind="call") -> dict:
    """
    Sell one option at the implied-vol price and delta-hedge it n_rebalance times.

    Lessons (Wilmott ch. on hedging):
      - sigma_real == sigma_implied: mean P&L ~ 0; std shrinks ~ 1/sqrt(n_rebalance).
      - sigma_real >  sigma_implied: short option LOSES on average (you sold vol too cheap).
    Returns final hedged P&L per path in currency units and as % of premium.
    """
    rng = np.random.default_rng(seed)
    dt = T / n_rebalance
    S = np.full(n_paths, float(S0))
    premium = bs_price(S0, K, T, r, sigma_implied, kind=kind)
    delta = bs_greeks(S0, K, T, r, sigma_implied, kind=kind)["delta"]
    cash = premium - delta * S
    for i in range(1, n_rebalance + 1):
        z = rng.standard_normal(n_paths)
        S = S * np.exp((mu - 0.5 * sigma_real ** 2) * dt + sigma_real * np.sqrt(dt) * z)
        cash = cash * np.exp(r * dt)
        tau = T - i * dt
        if tau > 1e-12:
            d1, _ = _d1d2(S, K, tau, r, sigma_implied)
            new_delta = norm.cdf(d1) if kind == "call" else norm.cdf(d1) - 1
        else:
            new_delta = delta
        cash = cash - (new_delta - delta) * S
        delta = new_delta
    pnl = cash + delta * S - payoff(S, K, kind)
    return {"premium": premium, "pnl": pnl, "pnl_pct_premium": pnl / premium * 100,
            "mean": float(pnl.mean()), "std": float(pnl.std())}
