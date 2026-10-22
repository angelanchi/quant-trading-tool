# -*- coding: utf-8 -*-
"""Textbook-value tests for core.quant (CQF math layer). No network."""
import math

import numpy as np
import pandas as pd
import pytest

from core.quant import (stochastic as st, volatility as vol, var, capm, options as op,
                        sizing, costs, fixed_income as fi, claims, tw_signals as tw)


# ---------------------------------------------------------------- M3 options
class TestBlackScholes:
    # Hull, Options Futures & Other Derivatives, Example 15.6
    S, K, r, sig, T = 42.0, 40.0, 0.10, 0.20, 0.5

    def test_hull_example(self):
        assert op.bs_price(self.S, self.K, self.T, self.r, self.sig, kind="call") == pytest.approx(4.76, abs=0.005)
        assert op.bs_price(self.S, self.K, self.T, self.r, self.sig, kind="put") == pytest.approx(0.81, abs=0.005)

    def test_put_call_parity(self):
        c = op.bs_price(self.S, self.K, self.T, self.r, self.sig, q=0.02, kind="call")
        p = op.bs_price(self.S, self.K, self.T, self.r, self.sig, q=0.02, kind="put")
        assert op.parity_gap(c, p, self.S, self.K, self.T, self.r, q=0.02) == pytest.approx(0, abs=1e-10)

    def test_implied_vol_roundtrip(self):
        c = op.bs_price(self.S, self.K, self.T, self.r, 0.37)
        assert op.implied_vol(c, self.S, self.K, self.T, self.r) == pytest.approx(0.37, abs=1e-8)

    def test_implied_vol_rejects_arbitrage_price(self):
        assert math.isnan(op.implied_vol(0.01, self.S, self.K, self.T, self.r))  # below intrinsic

    @pytest.mark.parametrize("kind", ["call", "put"])
    def test_greeks_match_finite_differences(self, kind):
        g = op.bs_greeks(self.S, self.K, self.T, self.r, self.sig, kind=kind)
        f = lambda **kw: op.bs_price(**{**dict(S=self.S, K=self.K, T=self.T, r=self.r, sigma=self.sig, kind=kind), **kw})
        h = 1e-4
        assert g["delta"] == pytest.approx((f(S=self.S + h) - f(S=self.S - h)) / (2 * h), abs=1e-6)
        assert g["gamma"] == pytest.approx((f(S=self.S + h) - 2 * f() + f(S=self.S - h)) / h ** 2, abs=1e-3)
        assert g["vega"] == pytest.approx((f(sigma=self.sig + h) - f(sigma=self.sig - h)) / (2 * h) / 100, abs=1e-6)
        assert g["rho"] == pytest.approx((f(r=self.r + h) - f(r=self.r - h)) / (2 * h) / 100, abs=1e-6)
        assert g["theta"] == pytest.approx(-(f(T=self.T + h) - f(T=self.T - h)) / (2 * h) / 365, abs=1e-6)

    def test_delta_hedge_error_shrinks_with_rebalancing(self):
        a = op.delta_hedge_simulation(100, 100, 0.25, 0.01, 0.2, 0.2, n_rebalance=10, n_paths=4000)
        b = op.delta_hedge_simulation(100, 100, 0.25, 0.01, 0.2, 0.2, n_rebalance=160, n_paths=4000)
        assert b["std"] < a["std"] * 0.5            # ~ 1/sqrt(16) = 0.25
        assert abs(b["mean"]) < 0.1 * b["premium"]

    def test_short_vol_loses_when_realised_higher(self):
        res = op.delta_hedge_simulation(100, 100, 0.25, 0.01, 0.2, 0.35, n_rebalance=100, n_paths=3000)
        assert res["mean"] < 0


# ---------------------------------------------------------------- M1 GBM
class TestGBM:
    def test_simulated_mean_matches_theory(self):
        p = st.simulate_gbm(100, 0.10, 0.30, 252, n_paths=200_000, seed=1)
        assert p[-1].mean() == pytest.approx(100 * math.exp(0.10), rel=0.01)
        assert np.median(p[-1]) == pytest.approx(100 * math.exp(0.10 - 0.045), rel=0.01)

    def test_estimate_params_recovers_inputs(self):
        p = st.simulate_gbm(100, 0.08, 0.25, 252 * 40, n_paths=1, seed=2)[:, 0]
        est = st.estimate_gbm_params(pd.Series(p))
        assert est.sigma == pytest.approx(0.25, rel=0.03)

    def test_touch_probability_vs_monte_carlo(self):
        s0, h, mu, sig, n = 100, 110, 0.05, 0.3, 60
        paths = st.simulate_gbm(s0, mu, sig, n * 20, n_paths=20_000, seed=3, periods=252 * 20)
        mc = (paths.max(axis=0) >= h).mean()
        assert st.prob_touch(s0, h, mu, sig, n) == pytest.approx(mc, abs=0.02)
        assert st.prob_touch(s0, h, mu, sig, n) >= st.prob_terminal_above(s0, h, mu, sig, n)

    def test_touch_down(self):
        s0, h, mu, sig, n = 100, 90, 0.05, 0.3, 60
        paths = st.simulate_gbm(s0, mu, sig, n * 20, n_paths=20_000, seed=4, periods=252 * 20)
        mc = (paths.min(axis=0) <= h).mean()
        assert st.prob_touch(s0, h, mu, sig, n) == pytest.approx(mc, abs=0.02)

    def test_cone_median(self):
        cone = st.terminal_quantiles(100, 0.1, 0.2, [252])
        assert cone.loc[252, "q50"] == pytest.approx(100 * math.exp(0.1 - 0.02))


# ---------------------------------------------------------------- M2 volatility & VaR
def _simulate_garch(n, omega, alpha, beta, seed=0):
    rng = np.random.default_rng(seed)
    r = np.empty(n)
    s2 = omega / (1 - alpha - beta)
    for t in range(n):
        r[t] = math.sqrt(s2) * rng.standard_normal()
        s2 = omega + alpha * r[t] ** 2 + beta * s2
    return pd.Series(r, index=pd.bdate_range("2010-01-01", periods=n))


class TestVolatility:
    def test_garch_recovers_parameters(self):
        r = _simulate_garch(5000, 2e-6, 0.08, 0.90, seed=5)
        g = vol.fit_garch11(r)
        assert g.converged
        assert g.alpha == pytest.approx(0.08, abs=0.03)
        assert g.beta == pytest.approx(0.90, abs=0.04)
        assert g.long_run_vol_annual == pytest.approx(math.sqrt(2e-6 / 0.02 * 252), rel=0.25)

    def test_garch_forecast_reverts_to_long_run(self):
        g = vol.fit_garch11(_simulate_garch(3000, 2e-6, 0.08, 0.90, seed=6))
        f = g.forecast_variance(2000)
        assert f[-1] == pytest.approx(g.long_run_var, rel=1e-3)

    def test_ewma_is_one_step_ahead(self):
        r = pd.Series([0.0] * 50 + [0.1] + [0.0] * 5)
        e = vol.ewma_variance(r, 0.94)
        assert e.iloc[50] == pytest.approx(e.iloc[49] * 0.94)      # shock not yet known
        assert e.iloc[51] > e.iloc[50]                              # known the next day

    def test_regime(self):
        h = pd.Series(np.linspace(0.1, 0.5, 101))
        assert vol.vol_regime(0.49, h)["regime"] == "極端"
        assert vol.vol_regime(0.11, h)["regime"] == "低波動"


class TestVaR:
    def test_normal_var(self):
        r = pd.Series(np.random.default_rng(0).normal(0, 0.01, 200_000))
        assert var.var_normal(r, 0.99) == pytest.approx(0.02326, rel=0.01)
        assert var.var_historical(r, 0.99) == pytest.approx(0.02326, rel=0.02)
        assert var.es_normal(r, 0.99) == pytest.approx(0.02665, rel=0.01)

    def test_cornish_fisher_equals_normal_for_normal_data(self):
        r = pd.Series(np.random.default_rng(1).normal(0, 0.01, 200_000))
        assert var.var_cornish_fisher(r, 0.99) == pytest.approx(var.var_normal(r, 0.99), rel=0.02)

    def test_kupiec_zero_exceptions(self):
        k = var.kupiec_pof(0, 250, 0.99)
        assert k["LR"] == pytest.approx(-2 * 250 * math.log(0.99), rel=1e-9)

    def test_kupiec_accepts_expected_count(self):
        assert not var.kupiec_pof(10, 1000, 0.99)["reject_at_5pct"]
        assert var.kupiec_pof(30, 1000, 0.99)["reject_at_5pct"]

    def test_traffic_light(self):
        assert var.basel_traffic_light(2).startswith("綠")
        assert var.basel_traffic_light(6).startswith("黃")
        assert var.basel_traffic_light(12).startswith("紅")

    def test_backtest_runs_on_garch_data(self):
        r = _simulate_garch(1500, 2e-6, 0.08, 0.9, seed=7)
        f = var.rolling_var_forecasts(r, 0.99, "ewma")
        out = var.backtest_var(r, f, 0.99)
        assert out["n_obs"] > 1000
        assert 0 <= out["kupiec"]["p_value"] <= 1


# ---------------------------------------------------------------- M2 CAPM / sizing / costs
def test_capm_recovers_beta():
    rng = np.random.default_rng(8)
    m = pd.Series(rng.normal(0.0004, 0.01, 3000))
    a = 0.0001 + 1.3 * m + rng.normal(0, 0.008, 3000)
    res = capm.capm_regression(a, m, rf_annual=0.0)
    assert res.beta == pytest.approx(1.3, abs=0.05)
    assert 0 < res.systematic_share < 1


def test_fixed_fractional_and_kelly():
    s = sizing.fixed_fractional_shares(1_000_000, 0.01, 100, 95, lot_size=1)
    assert s["shares"] == 2000 and s["loss_at_stop"] == pytest.approx(10_000)
    assert sizing.kelly_fraction(0.10, 0.20, 0.02) == pytest.approx(2.0)
    c = sizing.kelly_curve(0.10, 0.20, 0.02)
    assert c.loc[c["growth"].idxmax(), "fraction"] == pytest.approx(2.0, abs=0.06)


def test_tw_costs():
    m = costs.TWCostModel(discount=1.0, min_fee=20)
    rt = m.round_trip(100, 100, 1000)
    assert rt["total_cost"] == pytest.approx(142.5 * 2 + 300)
    assert m.breakeven_move(100, 1000) == pytest.approx(0.00587, abs=2e-4)
    assert costs.is_tw_etf("00878") and not costs.is_tw_etf("2330")


# ---------------------------------------------------------------- M6 fixed income
def test_par_bond_and_zero_duration():
    assert fi.bond_price(100, 0.05, 0.05, 10, 2) == pytest.approx(100)
    z = fi.bond_risk(100, 0.0, 0.04, 5, 1)
    assert z["macaulay_duration"] == pytest.approx(5)
    assert fi.bond_ytm(fi.bond_price(100, 0.03, 0.045, 7), 100, 0.03, 7) == pytest.approx(0.045, abs=1e-9)


def test_convexity_improves_approximation():
    rk = fi.bond_risk(100, 0.04, 0.04, 20, 2)
    true = fi.bond_price(100, 0.04, 0.06, 20, 2) / rk["price"] - 1
    ap = fi.price_change_approx(rk, 0.02)
    assert abs(ap["with_convexity"] - true) < abs(ap["duration_only"] - true)


def test_vasicek_deterministic_limit():
    assert fi.vasicek_zcb(0.03, 0.5, 0.03, 1e-9, 10) == pytest.approx(math.exp(-0.3), rel=1e-6)


# ---------------------------------------------------------------- claim checker & signals
def test_claim_checker_flags_extreme_promise():
    a = claims.assess_claim(0.30, 5, 0.40)
    assert a.prob_end_above < 0.01
    assert a.annualized_equivalent > 100            # > 10,000 %
    assert a.verdict.startswith("極不可能")


def test_red_flags():
    s = claims.red_flag_score({"guaranteed_return": True, "tiered_by_capital": True, "deadline_pressure": True})
    assert s["level"] == "高風險" and s["count"] == 3


def test_third_wednesday():
    d = tw.third_wednesdays("2026-10-01", "2026-12-31")
    assert list(d.strftime("%Y-%m-%d")) == ["2026-10-21", "2026-11-18", "2026-12-16"]


def test_event_study_detects_injected_effect():
    idx = pd.bdate_range("2020-01-01", "2025-12-31")
    rng = np.random.default_rng(9)
    r = pd.Series(rng.normal(0, 0.01, len(idx)), index=idx)
    ev = tw.align_to_trading_days(tw.third_wednesdays(idx[0], idx[-1]), idx)
    r[ev] *= 3
    out = tw.event_study(r, tw.third_wednesdays(idx[0], idx[-1]))
    assert out["significant_5pct"] and out["ratio"] > 2


def test_ml_walk_forward_runs_and_reports_baseline():
    pytest.importorskip("sklearn")
    from core.quant import ml
    p = pd.Series(st.simulate_gbm(100, 0.05, 0.25, 1500, 1, seed=10)[:, 0],
                  index=pd.bdate_range("2019-01-01", periods=1501))
    rep = ml.walk_forward_classify(p, horizon=5)
    assert 0 <= rep.accuracy <= 1 and 0 <= rep.baseline_accuracy <= 1
    assert len(rep.folds) == 5
    # a pure random walk must not look significantly predictable
    assert rep.verdict().startswith("無可靠")
