# -*- coding: utf-8 -*-
"""
Unit tests for risk calculation module.

Tests cover:
- VaR calculations (Historical, Parametric, Monte Carlo)
- CVaR / Expected Shortfall
- Risk ratios (Sharpe, Sortino, Calmar)
- Drawdown calculations
- Distribution metrics
"""

import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.risk import RiskCalculator, RiskMetrics


class TestRiskCalculator:
    """Test suite for RiskCalculator class."""

    def test_var_historical(self, sample_returns):
        """Test historical VaR calculation."""
        calc = RiskCalculator(sample_returns, risk_free_rate=0.02)
        var_95 = calc.var_historical(confidence=0.95)

        # VaR should be negative (representing a loss)
        assert var_95 < 0

        # 95% VaR should be less negative than 99% VaR
        var_99 = calc.var_historical(confidence=0.99)
        assert var_99 < var_95

    def test_var_parametric(self, sample_returns):
        """Test parametric VaR calculation."""
        calc = RiskCalculator(sample_returns, risk_free_rate=0.02)
        var_95 = calc.var_parametric(confidence=0.95)

        # VaR should be negative
        assert var_95 < 0

        # Check that parametric VaR is reasonable
        assert var_95 > -0.2  # Should not be too extreme for normal returns

    def test_cvar(self, sample_returns):
        """Test CVaR (Expected Shortfall) calculation."""
        calc = RiskCalculator(sample_returns, risk_free_rate=0.02)
        cvar_95 = calc.cvar(confidence=0.95)
        var_95 = calc.var_historical(confidence=0.95)

        # CVaR should be more negative than VaR (larger expected loss)
        assert cvar_95 <= var_95

    def test_sharpe_ratio(self, sample_returns):
        """Test Sharpe ratio calculation."""
        calc = RiskCalculator(sample_returns, risk_free_rate=0.02)
        sharpe = calc.sharpe_ratio()

        # Sharpe ratio should be a finite number
        assert np.isfinite(sharpe)

    def test_sortino_ratio(self, sample_returns):
        """Test Sortino ratio calculation."""
        calc = RiskCalculator(sample_returns, risk_free_rate=0.02)
        sortino = calc.sortino_ratio()

        # Sortino ratio should be a finite number or 0
        assert np.isfinite(sortino)

    def test_calmar_ratio(self, sample_returns):
        """Test Calmar ratio calculation."""
        calc = RiskCalculator(sample_returns, risk_free_rate=0.02)
        calmar = calc.calmar_ratio()

        # Calmar ratio should be a finite number
        assert np.isfinite(calmar)

    def test_max_drawdown(self, sample_returns):
        """Test maximum drawdown calculation."""
        calc = RiskCalculator(sample_returns, risk_free_rate=0.02)
        max_dd = calc.max_drawdown()

        # Max drawdown should be negative
        assert max_dd <= 0

        # Max drawdown should not exceed -100%
        assert max_dd >= -1.0

    def test_calculate_all_metrics(self, sample_returns):
        """Test comprehensive metrics calculation."""
        calc = RiskCalculator(sample_returns, risk_free_rate=0.02)
        metrics = calc.calculate_all()

        # Check that all metrics are present
        assert isinstance(metrics, RiskMetrics)
        assert hasattr(metrics, 'var_95_historical')
        assert hasattr(metrics, 'var_95_parametric')
        assert hasattr(metrics, 'cvar_95')
        assert hasattr(metrics, 'sharpe_ratio')
        assert hasattr(metrics, 'sortino_ratio')
        assert hasattr(metrics, 'calmar_ratio')
        assert hasattr(metrics, 'max_drawdown')
        assert hasattr(metrics, 'volatility')
        assert hasattr(metrics, 'skewness')
        assert hasattr(metrics, 'kurtosis')

    def test_volatility(self, sample_returns):
        """Test volatility calculation."""
        calc = RiskCalculator(sample_returns, risk_free_rate=0.02)
        vol = calc.volatility()

        # Volatility should be positive
        assert vol > 0

        # Annualized volatility for normal data should be reasonable
        assert vol < 1.0  # Less than 100% annual

    def test_total_return(self, sample_returns):
        """Test total return calculation."""
        calc = RiskCalculator(sample_returns, risk_free_rate=0.02)
        total_ret = calc.total_return()

        # Total return should be finite
        assert np.isfinite(total_ret)

    def test_cagr(self, sample_returns):
        """Test CAGR calculation."""
        calc = RiskCalculator(sample_returns, risk_free_rate=0.02)
        cagr = calc.cagr()

        # CAGR should be finite
        assert np.isfinite(cagr)

    def test_empty_returns(self):
        """Test handling of empty returns."""
        empty_returns = pd.Series([], dtype=float)

        # Should handle gracefully or raise appropriate error
        try:
            calc = RiskCalculator(empty_returns)
            # If it doesn't raise, results should handle edge cases
        except (ValueError, ZeroDivisionError):
            pass  # Expected behavior

    def test_constant_returns(self):
        """Test handling of constant returns (zero volatility)."""
        constant_returns = pd.Series([0.01] * 100)
        calc = RiskCalculator(constant_returns)

        # Volatility should be 0 or very small
        vol = calc.volatility()
        assert vol == 0 or vol < 0.001


class TestRiskMetricsDataclass:
    """Test suite for RiskMetrics dataclass."""

    def test_risk_metrics_creation(self):
        """Test RiskMetrics dataclass creation."""
        metrics = RiskMetrics(
            total_return=0.15,
            cagr=0.12,
            volatility=0.20,
            downside_deviation=0.15,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            calmar_ratio=1.2,
            max_drawdown=-0.15,
            avg_drawdown=-0.05,
            max_drawdown_duration=30,
            var_95_historical=-0.02,
            var_99_historical=-0.03,
            var_95_parametric=-0.021,
            cvar_95=-0.03,
            skewness=-0.3,
            kurtosis=0.5,
            positive_days_ratio=0.55
        )

        assert metrics.var_95_historical == -0.02
        assert metrics.sharpe_ratio == 1.5
        assert metrics.max_drawdown == -0.15

    def test_to_dict(self):
        """Test conversion to dictionary."""
        metrics = RiskMetrics(
            total_return=0.15,
            cagr=0.12,
            volatility=0.20,
            downside_deviation=0.15,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            calmar_ratio=1.2,
            max_drawdown=-0.15,
            avg_drawdown=-0.05,
            max_drawdown_duration=30,
            var_95_historical=-0.02,
            var_99_historical=-0.03,
            var_95_parametric=-0.021,
            cvar_95=-0.03,
            skewness=-0.3,
            kurtosis=0.5,
            positive_days_ratio=0.55
        )

        d = metrics.to_dict()
        assert isinstance(d, dict)
        assert d['sharpe_ratio'] == 1.5

    def test_summary(self):
        """Test summary generation."""
        metrics = RiskMetrics(
            total_return=0.15,
            cagr=0.12,
            volatility=0.20,
            downside_deviation=0.15,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            calmar_ratio=1.2,
            max_drawdown=-0.15,
            avg_drawdown=-0.05,
            max_drawdown_duration=30,
            var_95_historical=-0.02,
            var_99_historical=-0.03,
            var_95_parametric=-0.021,
            cvar_95=-0.03,
            skewness=-0.3,
            kurtosis=0.5,
            positive_days_ratio=0.55
        )

        summary = metrics.summary()
        assert isinstance(summary, str)
        assert 'Sharpe Ratio' in summary


class TestDrawdownAnalysis:
    """Test suite for drawdown analysis functions."""

    def test_drawdown_series(self, sample_returns):
        """Test drawdown series calculation."""
        calc = RiskCalculator(sample_returns)
        dd_series = calc.drawdown_series()

        # All drawdowns should be non-positive
        assert (dd_series <= 0).all()

        # Maximum drawdown should match max_drawdown result
        max_dd = calc.max_drawdown()
        assert abs(dd_series.min() - max_dd) < 0.001

    def test_average_drawdown(self, sample_returns):
        """Test average drawdown calculation."""
        calc = RiskCalculator(sample_returns)
        avg_dd = calc.average_drawdown()

        # Average drawdown should be negative or zero
        assert avg_dd <= 0

        # Should be less severe than max drawdown
        max_dd = calc.max_drawdown()
        assert avg_dd >= max_dd

    def test_max_drawdown_duration(self, sample_returns):
        """Test max drawdown duration calculation."""
        calc = RiskCalculator(sample_returns)
        duration = calc.max_drawdown_duration()

        # Duration should be non-negative
        assert duration >= 0

        # Duration should be reasonable
        assert duration <= len(sample_returns)

    def test_underwater_periods(self, sample_returns):
        """Test underwater periods analysis."""
        calc = RiskCalculator(sample_returns)
        periods = calc.underwater_periods()

        # Should return DataFrame
        assert isinstance(periods, pd.DataFrame)

        # If we have drawdowns, should have columns
        if len(periods) > 0:
            assert 'start' in periods.columns
            assert 'end' in periods.columns
            assert 'depth' in periods.columns
