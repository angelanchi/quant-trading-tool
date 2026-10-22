# -*- coding: utf-8 -*-
"""
CQF Module 6 — Fixed income basics.

  Price      P = sum_i CF_i / (1 + y/f)^(i)          (f coupons per year)
  Macaulay D = sum t_i * PV(CF_i) / P               (years)
  Modified D = D_mac / (1 + y/f)
  Convexity  C = sum t_i (t_i + 1/f) PV(CF_i) / (P (1 + y/f)^2)
  dP/P  ~=  -D_mod * dy + 0.5 * C * dy^2

Vasicek short rate: dr = a (b - r) dt + sigma dW  (mean-reverting; can go negative)
  zero-coupon bond P(0,T) = A(T) exp(-B(T) r0),
  B = (1 - e^{-aT}) / a,
  ln A = (B - T)(a^2 b - sigma^2/2) / a^2 - sigma^2 B^2 / (4a)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import brentq


def _cashflows(face, coupon_rate, years, freq):
    n = int(round(years * freq))
    t = np.arange(1, n + 1) / freq
    cf = np.full(n, face * coupon_rate / freq)
    cf[-1] += face
    return t, cf


def bond_price(face, coupon_rate, ytm, years, freq=2) -> float:
    t, cf = _cashflows(face, coupon_rate, years, freq)
    return float(np.sum(cf / (1 + ytm / freq) ** (t * freq)))


def bond_ytm(price, face, coupon_rate, years, freq=2) -> float:
    return float(brentq(lambda y: bond_price(face, coupon_rate, y, years, freq) - price, -0.5, 2.0))


def bond_risk(face, coupon_rate, ytm, years, freq=2) -> dict:
    t, cf = _cashflows(face, coupon_rate, years, freq)
    disc = (1 + ytm / freq) ** (t * freq)
    pv = cf / disc
    p = pv.sum()
    d_mac = float(np.sum(t * pv) / p)
    d_mod = d_mac / (1 + ytm / freq)
    conv = float(np.sum(t * (t + 1 / freq) * pv) / (p * (1 + ytm / freq) ** 2))
    return {"price": float(p), "macaulay_duration": d_mac, "modified_duration": float(d_mod),
            "convexity": conv, "dv01": float(d_mod * p / 10000)}


def price_change_approx(risk: dict, dy: float) -> dict:
    """Duration-only vs duration+convexity approximation of the % price change."""
    lin = -risk["modified_duration"] * dy
    quad = lin + 0.5 * risk["convexity"] * dy ** 2
    return {"duration_only": lin, "with_convexity": quad}


def vasicek_zcb(r0, a, b, sigma, T) -> float:
    if a <= 0:
        raise ValueError("a must be > 0")
    B = (1 - np.exp(-a * T)) / a
    lnA = (B - T) * (a ** 2 * b - 0.5 * sigma ** 2) / a ** 2 - sigma ** 2 * B ** 2 / (4 * a)
    return float(np.exp(lnA - B * r0))


def vasicek_yield_curve(r0, a, b, sigma, maturities=(0.25, 0.5, 1, 2, 3, 5, 7, 10, 20, 30)) -> pd.Series:
    return pd.Series({T: -np.log(vasicek_zcb(r0, a, b, sigma, T)) / T for T in maturities},
                     name="zero_yield")


def simulate_vasicek(r0, a, b, sigma, years=5, steps_per_year=252, n_paths=200, seed=0) -> np.ndarray:
    """Exact discretisation of the OU process."""
    rng = np.random.default_rng(seed)
    dt = 1 / steps_per_year
    n = int(years * steps_per_year)
    e = np.exp(-a * dt)
    sd = sigma * np.sqrt((1 - np.exp(-2 * a * dt)) / (2 * a))
    r = np.empty((n + 1, n_paths))
    r[0] = r0
    for i in range(1, n + 1):
        r[i] = b + (r[i - 1] - b) * e + sd * rng.standard_normal(n_paths)
    return r
