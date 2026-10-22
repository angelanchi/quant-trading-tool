# -*- coding: utf-8 -*-
"""
core.quant — pure-math CQF layer (no network, no Streamlit).

Module map:
  stochastic    M1  GBM, price cone, terminal / touch probabilities
  volatility    M2  realised, EWMA, GARCH(1,1)
  var           M2  VaR / ES and VaR backtests (Kupiec, Christoffersen)
  capm          M2  alpha, beta, risk split
  options       M3  Black-Scholes, Greeks, implied vol, delta hedging
  sizing        M2  position sizing, Kelly
  costs         --  Taiwan / US transaction costs
  ml            M4  walk-forward direction classifier vs baseline
  fixed_income  M6  bond price, duration, convexity, Vasicek
  claims        M1  claim checker (說法驗證器)
  tw_signals    --  settlement-day event study, cycle position
"""
from . import (stochastic, volatility, var, capm, options, sizing, costs,  # noqa: F401
               fixed_income, claims, tw_signals)
