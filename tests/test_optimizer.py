# -*- coding: utf-8 -*-
"""
Unit tests for portfolio optimization module.

Tests cover:
- Maximum Sharpe ratio optimization
- Minimum volatility optimization
- Risk parity (HRP)
- Black-Litterman model
- Efficient frontier calculation
- Discrete allocation

API notes (current core/optimizer.py):
- PortfolioOptimizer(prices, risk_free_rate) binds the price data at construction.
- All mean-variance methods go through optimizer.optimize(method, weight_bounds=...).
- OptimizationResult fields: method, weights, expected_return,
  expected_volatility, sharpe_ratio, allocation, leftover.
"""

import importlib.util

import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.optimizer import PortfolioOptimizer, OptimizationResult

PYPFOPT_AVAILABLE = importlib.util.find_spec('pypfopt') is not None


class TestPortfolioOptimizer:
    """Test suite for PortfolioOptimizer class."""

    @pytest.fixture(autouse=True)
    def setup(self, sample_multi_asset_prices):
        """Set up test fixtures."""
        self.prices = sample_multi_asset_prices
        self.optimizer = PortfolioOptimizer(sample_multi_asset_prices, risk_free_rate=0.02)

    def test_max_sharpe(self):
        """Test maximum Sharpe ratio optimization."""
        result = self.optimizer.optimize('max_sharpe')

        # Check result type
        assert isinstance(result, OptimizationResult)
        assert result.method == 'max_sharpe'
        assert set(result.weights) == set(self.prices.columns)

        # Check weights sum to 1
        total_weight = sum(result.weights.values())
        assert abs(total_weight - 1.0) < 0.01

        # Check all weights are non-negative (long only)
        assert all(w >= -0.01 for w in result.weights.values())

        # Check metrics are present
        assert np.isfinite(result.expected_return)
        assert np.isfinite(result.expected_volatility)
        assert np.isfinite(result.sharpe_ratio)

        # Max-Sharpe should be at least as good as equal weight
        ew = self._equal_weight_stats()
        assert result.sharpe_ratio >= ew['sharpe'] - 1e-6

    def test_min_volatility(self):
        """Test minimum volatility optimization."""
        result = self.optimizer.optimize('min_volatility')

        # Check weights sum to 1
        total_weight = sum(result.weights.values())
        assert abs(total_weight - 1.0) < 0.01

        # Min vol portfolio should have lower volatility than equal weight
        equal_weight_vol = self._equal_weight_stats()['volatility']
        assert result.expected_volatility <= equal_weight_vol * 1.1  # Allow small margin

    def test_risk_parity(self):
        """Test risk parity (HRP) optimization."""
        result = self.optimizer.optimize('risk_parity')
        assert result.method == 'risk_parity'

        # Check weights sum to 1
        total_weight = sum(result.weights.values())
        assert abs(total_weight - 1.0) < 0.01

        # Check all weights are positive
        assert all(w > 0 for w in result.weights.values())

    def test_black_litterman(self):
        """Test Black-Litterman optimization."""
        market_caps = {
            'AAPL': 3.0e12, 'MSFT': 2.5e12, 'GOOGL': 1.8e12,
            'AMZN': 1.7e12, 'META': 1.0e12,
        }
        # Define views: AAPL will outperform
        views = {'AAPL': 0.15}  # 15% expected return for AAPL

        result = self.optimizer.optimize_black_litterman(
            market_caps,
            views,
            view_confidences=[0.8]
        )

        # Check weights sum to 1
        total_weight = sum(result.weights.values())
        assert abs(total_weight - 1.0) < 0.01

        if PYPFOPT_AVAILABLE:
            assert result.method == 'black_litterman'
            # AAPL should get a positive weight due to the bullish view
            assert result.weights.get('AAPL', 0) > 0
        else:
            # Documented fallback: without PyPortfolioOpt the views cannot be
            # applied and the optimizer returns a plain max-Sharpe portfolio.
            assert result.method == 'max_sharpe'
            assert result.weights == self.optimizer.optimize('max_sharpe').weights

    def test_weight_bounds(self):
        """Test weight constraints."""
        result = self.optimizer.optimize('max_sharpe', weight_bounds=(0.1, 0.4))

        # Check all weights respect bounds
        for weight in result.weights.values():
            assert weight >= 0.1 - 0.01  # Small tolerance
            assert weight <= 0.4 + 0.01

    def test_efficient_frontier(self):
        """Test efficient frontier calculation."""
        ef_data = self.optimizer.get_efficient_frontier(n_points=20)

        # Points that fail to solve may be dropped, never more than requested
        assert 2 <= len(ef_data) <= 20

        # Check columns exist
        assert {'return', 'volatility', 'sharpe'} <= set(ef_data.columns)

        # Every frontier point should be no riskier than the min-vol portfolio
        min_vol = self.optimizer.optimize('min_volatility').expected_volatility
        assert (ef_data['volatility'] >= min_vol - 1e-4).all()

        # On the efficient frontier, higher return requires higher volatility:
        # sorted by return, volatility must be non-decreasing.
        #
        # KNOWN CORE BUG (left failing on purpose): without PyPortfolioOpt,
        # PortfolioOptimizer._efficient_frontier_fallback (core/optimizer.py ~L568)
        # sweeps target returns from the *lowest single-asset* return instead of
        # the min-volatility portfolio's return, so it includes the dominated
        # lower branch of the minimum-variance curve (volatility falls as return
        # rises there). The PyPortfolioOpt path starts at the min-vol return.
        ef_sorted = ef_data.sort_values('return')
        volatilities = ef_sorted['volatility'].values
        assert all(volatilities[i] <= volatilities[i + 1] + 1e-6
                   for i in range(len(volatilities) - 1))

    def test_discrete_allocation(self, sample_portfolio_weights):
        """Test discrete share allocation."""
        allocation, leftover = self.optimizer.get_discrete_allocation(
            sample_portfolio_weights,
            total_value=100000
        )

        # Check allocation is a dictionary with integer shares
        assert isinstance(allocation, dict)
        assert len(allocation) > 0
        assert all(isinstance(v, (int, np.integer)) for v in allocation.values())

        # Check leftover is non-negative
        assert leftover >= 0

        # Check total value is close to target
        total_value = sum(
            allocation[s] * self.prices[s].iloc[-1]
            for s in allocation.keys()
        ) + leftover
        assert abs(total_value - 100000) < 1000  # Within $1000

    def test_single_asset(self):
        """Test handling of single asset (edge case)."""
        rng = np.random.default_rng(0)
        dates = pd.date_range(start='2022-01-01', periods=100, freq='B')
        single_asset = pd.DataFrame({'AAPL': rng.standard_normal(100).cumsum() + 100},
                                    index=dates)

        result = PortfolioOptimizer(single_asset).optimize('max_sharpe')

        # Single asset should have 100% weight
        assert result.weights.get('AAPL', 0) == pytest.approx(1.0, abs=0.01)

    def test_insufficient_data(self):
        """Test handling of insufficient data."""
        dates = pd.date_range(start='2022-01-01', periods=5, freq='B')
        small_data = pd.DataFrame({
            'AAPL': [100, 101, 99, 102, 101],
            'MSFT': [200, 202, 198, 203, 201]
        }, index=dates)

        # Should still work with limited data
        result = PortfolioOptimizer(small_data).optimize('max_sharpe')
        assert result is not None
        assert abs(sum(result.weights.values()) - 1.0) < 0.01

    def _equal_weight_stats(self):
        """Helper: equal weight portfolio stats using the optimizer's own inputs."""
        n_assets = len(self.prices.columns)
        weights = np.array([1 / n_assets] * n_assets)
        ret = float(np.dot(weights, self.optimizer.expected_returns))
        vol = float(np.sqrt(weights @ self.optimizer.cov_matrix.values @ weights))
        return {'return': ret, 'volatility': vol,
                'sharpe': (ret - self.optimizer.risk_free_rate) / vol}


class TestOptimizationResult:
    """Test suite for OptimizationResult dataclass."""

    def test_optimization_result_creation(self):
        """Test OptimizationResult dataclass creation."""
        result = OptimizationResult(
            method='max_sharpe',
            weights={'AAPL': 0.5, 'MSFT': 0.5},
            expected_return=0.12,
            expected_volatility=0.20,
            sharpe_ratio=0.50
        )

        assert result.weights['AAPL'] == 0.5
        assert result.expected_return == 0.12
        assert result.expected_volatility == 0.20
        assert result.sharpe_ratio == 0.50
        assert result.allocation is None
        assert result.leftover == 0.0
        assert result.to_dict()['expected_volatility'] == 0.20

    def test_weights_access(self):
        """Test accessing weights by symbol."""
        result = OptimizationResult(
            method='min_volatility',
            weights={'AAPL': 0.3, 'MSFT': 0.4, 'GOOGL': 0.3},
            expected_return=0.10,
            expected_volatility=0.15,
            sharpe_ratio=0.53
        )

        assert 'AAPL' in result.weights
        assert result.weights['MSFT'] == 0.4
        assert 'MSFT: 40.00%' in result.summary()
