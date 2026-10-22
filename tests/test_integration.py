# -*- coding: utf-8 -*-
"""
Integration tests for quantitative trading tool.

Tests the complete workflow from data fetching to analysis.
Uses synthetic data to avoid API dependencies.
"""

import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestDataToBacktestWorkflow:
    """Test data fetching to backtesting workflow."""

    def test_backtest_with_generated_data(self):
        """Test complete backtest workflow with synthetic data."""
        from scripts.generate_sample_data import generate_correlated_assets
        from core import BacktestEngine, BacktestConfig

        # Generate data
        symbols = ['AAPL', 'MSFT']
        prices_df = generate_correlated_assets(symbols, n_days=252, seed=42)
        dates = pd.date_range(start='2023-01-01', periods=252, freq='B')
        prices_df.index = dates

        # Run backtest
        engine = BacktestEngine(config=BacktestConfig(initial_capital=100000))
        result = engine.run_mean_reversion(
            prices_df,
            lookback=20,
            entry_zscore=-2.0,  # signed: enter when z-score < -2 (oversold)
            exit_zscore=0.5
        )

        # Verify results
        assert result is not None
        assert hasattr(result, 'total_return')
        assert hasattr(result, 'sharpe_ratio')
        assert hasattr(result, 'max_drawdown')
        assert np.isfinite(result.total_return)
        assert result.initial_capital == 100000
        assert result.equity_curve['equity'].iloc[-1] == pytest.approx(result.final_value)

    def test_strategy_to_backtest(self):
        """Test strategy signal generation to backtest."""
        from scripts.generate_sample_data import generate_correlated_assets
        from strategies import MeanReversionStrategy

        # Generate data
        symbols = ['AAPL', 'MSFT']
        prices_df = generate_correlated_assets(symbols, n_days=252, seed=42)
        dates = pd.date_range(start='2023-01-01', periods=252, freq='B')
        prices_df.index = dates

        # Generate signals
        strategy = MeanReversionStrategy(lookback=20, entry_zscore=2.0)
        signals = strategy.generate_signals(prices_df)

        # Verify signals
        assert 'signal' in signals.columns
        assert len(signals) == len(prices_df)

        # Signals should have reasonable distribution
        signal_counts = signals['signal'].value_counts()
        assert len(signal_counts) > 0


class TestDataToOptimizationWorkflow:
    """Test data to portfolio optimization workflow."""

    def test_optimization_with_generated_data(self):
        """Test portfolio optimization with synthetic data."""
        from scripts.generate_sample_data import generate_correlated_assets
        from core import PortfolioOptimizer

        # Generate data
        symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN']
        prices_df = generate_correlated_assets(symbols, n_days=252, seed=42)
        dates = pd.date_range(start='2023-01-01', periods=252, freq='B')
        prices_df.index = dates

        # Run optimization
        optimizer = PortfolioOptimizer(prices_df, risk_free_rate=0.02)
        result = optimizer.optimize('max_sharpe')

        # Verify results
        assert result is not None
        assert hasattr(result, 'weights')
        assert len(result.weights) == len(symbols)

        # Weights should sum to 1
        weight_sum = sum(result.weights.values())
        assert abs(weight_sum - 1.0) < 0.01

    def test_all_optimization_methods(self):
        """Test all optimization methods work."""
        from scripts.generate_sample_data import generate_correlated_assets
        from core import PortfolioOptimizer
        from core.optimizer import equal_weight_portfolio

        # Generate data
        symbols = ['AAPL', 'MSFT', 'GOOGL']
        prices_df = generate_correlated_assets(symbols, n_days=252, seed=42)
        dates = pd.date_range(start='2023-01-01', periods=252, freq='B')
        prices_df.index = dates

        optimizer = PortfolioOptimizer(prices_df, risk_free_rate=0.02)

        # Test each optimize() method
        for method_name in ['max_sharpe', 'min_volatility', 'risk_parity']:
            result = optimizer.optimize(method_name)

            assert result is not None, f"{method_name} failed"
            assert result.method == method_name
            assert set(result.weights) == set(symbols), f"{method_name} assets missing"
            assert abs(sum(result.weights.values()) - 1.0) < 0.01, f"{method_name} weights invalid"

        # Equal weight is a standalone helper, not an optimize() method
        ew = equal_weight_portfolio(symbols)
        assert ew == pytest.approx({s: 1 / 3 for s in symbols})


class TestDataToRiskWorkflow:
    """Test data to risk analysis workflow."""

    def test_risk_analysis_with_generated_data(self):
        """Test risk calculation with synthetic data."""
        from scripts.generate_sample_data import generate_gbm_prices
        from core import RiskCalculator

        # Generate returns
        np.random.seed(42)
        prices = generate_gbm_prices(n_days=252, seed=42)
        returns = pd.Series(prices).pct_change().dropna()
        returns.index = pd.date_range(start='2023-01-01', periods=len(returns), freq='B')

        # Calculate risk metrics
        calc = RiskCalculator(returns, risk_free_rate=0.02)
        metrics = calc.calculate_all()

        # Verify metrics
        assert metrics is not None
        assert np.isfinite(metrics.sharpe_ratio)
        assert np.isfinite(metrics.var_95_historical)
        assert metrics.max_drawdown <= 0

    def test_portfolio_risk(self):
        """Test portfolio-level risk calculation."""
        from scripts.generate_sample_data import generate_correlated_assets
        from core import RiskCalculator

        # Generate multi-asset data
        symbols = ['AAPL', 'MSFT', 'GOOGL']
        prices_df = generate_correlated_assets(symbols, n_days=252, seed=42)
        dates = pd.date_range(start='2023-01-01', periods=252, freq='B')
        prices_df.index = dates

        # Calculate portfolio returns (equal weight)
        returns = prices_df.pct_change().dropna()
        portfolio_returns = returns.mean(axis=1)

        # Calculate risk
        calc = RiskCalculator(portfolio_returns, risk_free_rate=0.02)

        var_95 = calc.var_historical(0.95)
        cvar_95 = calc.cvar(0.95)

        assert var_95 < 0  # VaR should be negative
        assert cvar_95 <= var_95  # CVaR should be more negative


class TestEndToEndWorkflow:
    """Test complete end-to-end workflow."""

    def test_full_analysis_pipeline(self):
        """Test complete analysis from data to results."""
        from scripts.generate_sample_data import generate_sample_dataset
        from core import BacktestEngine, BacktestConfig, PortfolioOptimizer, RiskCalculator

        # 1. Generate data
        data = generate_sample_dataset(
            symbols=['AAPL', 'MSFT', 'GOOGL'],
            n_days=252,
            seed=42
        )
        prices_df = data['close']

        # 2. Run backtest
        engine = BacktestEngine(config=BacktestConfig(initial_capital=100000))
        backtest_result = engine.run_mean_reversion(
            prices_df,
            lookback=20,
            entry_zscore=-2.0
        )

        # 3. Optimize portfolio
        optimizer = PortfolioOptimizer(prices_df, risk_free_rate=0.02)
        opt_result = optimizer.optimize('max_sharpe')

        # 4. Calculate risk
        returns = prices_df.pct_change().dropna()
        portfolio_returns = returns.mean(axis=1)
        calc = RiskCalculator(portfolio_returns, risk_free_rate=0.02)
        risk_metrics = calc.calculate_all()

        # Verify all results
        assert np.isfinite(backtest_result.total_return)
        assert len(opt_result.weights) == 3
        assert abs(sum(opt_result.weights.values()) - 1.0) < 0.01
        assert risk_metrics.sharpe_ratio is not None

        print("\n--- Full Pipeline Results ---")
        print(f"Backtest Return: {backtest_result.total_return:.2%}")
        print(f"Optimal Weights: {opt_result.weights}")
        print(f"Portfolio Sharpe: {risk_metrics.sharpe_ratio:.2f}")


class TestStrategyComparison:
    """Test comparing multiple strategies."""

    def test_compare_strategies(self):
        """Test running and comparing multiple strategies."""
        from scripts.generate_sample_data import generate_correlated_assets
        from core import BacktestEngine, BacktestConfig

        # Generate data
        symbols = ['AAPL', 'MSFT']
        prices_df = generate_correlated_assets(symbols, n_days=252, seed=42)
        dates = pd.date_range(start='2023-01-01', periods=252, freq='B')
        prices_df.index = dates

        engine = BacktestEngine(config=BacktestConfig(initial_capital=100000))

        results = {}

        # Mean Reversion
        results['Mean Reversion'] = engine.run_mean_reversion(
            prices_df, lookback=20
        )

        # MA Crossover
        results['MA Crossover'] = engine.run_ma_crossover(
            prices_df, fast_period=10, slow_period=30
        )

        # Compare
        assert len(results) == 2

        for name, result in results.items():
            assert result is not None, f"{name} failed"
            assert result.strategy_name == name
            assert result.initial_capital == 100000
            assert np.isfinite(result.sharpe_ratio), f"{name} Sharpe invalid"

        # Print comparison
        print("\n--- Strategy Comparison ---")
        for name, result in results.items():
            print(f"{name}: Return={result.total_return:.2%}, Sharpe={result.sharpe_ratio:.2f}")
