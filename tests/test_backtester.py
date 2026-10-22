# -*- coding: utf-8 -*-
"""
Unit tests for backtesting engine module.

Tests cover:
- Mean reversion strategy backtesting
- MA crossover strategy backtesting
- RSI strategy backtesting
- Bollinger Bands strategy backtesting
- Performance metrics calculation
- Parameter optimization

API notes (current core/backtester.py):
- Run-level settings (initial_capital, commission, slippage, ...) live in
  BacktestConfig and are passed via BacktestEngine(config=...).
- entry_zscore is signed: entry happens when z-score < entry_zscore,
  so an "oversold at 2 sigma" entry is entry_zscore=-2.0.
- equity_curve is a DataFrame with 'date' and 'equity' columns.
- parameter_optimization() takes a callable strategy (e.g. engine.run_ma_crossover).
"""

import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.backtester import BacktestEngine, BacktestConfig, BacktestResult


class TestBacktestEngine:
    """Test suite for BacktestEngine class."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        self.engine = BacktestEngine(config=BacktestConfig(initial_capital=100000))

    def test_run_mean_reversion(self, sample_multi_asset_prices):
        """Test mean reversion strategy backtest."""
        result = self.engine.run_mean_reversion(
            sample_multi_asset_prices,
            lookback=20,
            entry_zscore=-2.0,
            exit_zscore=0.5
        )

        # Check result type
        assert isinstance(result, BacktestResult)

        # Initial capital comes from the engine's config
        assert result.initial_capital == 100000

        # Check metrics are present and reasonable
        assert np.isfinite(result.total_return)
        assert np.isfinite(result.sharpe_ratio)
        assert np.isfinite(result.max_drawdown)
        assert result.max_drawdown <= 0  # Drawdown is negative

        # Parameters are recorded
        assert result.parameters == {
            'lookback': 20, 'entry_zscore': -2.0, 'exit_zscore': 0.5
        }

        # Check equity curve exists
        assert result.equity_curve is not None
        assert len(result.equity_curve) > 0

    def test_run_ma_crossover(self, sample_multi_asset_prices):
        """Test MA crossover strategy backtest."""
        result = self.engine.run_ma_crossover(
            sample_multi_asset_prices,
            fast_period=10,
            slow_period=30
        )

        # Check result type
        assert isinstance(result, BacktestResult)

        # Check metrics
        assert np.isfinite(result.total_return)
        assert 0 <= result.win_rate <= 1
        assert result.total_trades >= 0

    def test_run_rsi_strategy(self, sample_ohlcv):
        """Test RSI strategy backtest."""
        # RSI is computed on the close series only
        result = self.engine.run_rsi_strategy(
            sample_ohlcv[['close']],
            period=14,
            oversold=30,
            overbought=70
        )

        # Check result type
        assert isinstance(result, BacktestResult)
        assert result.symbols == ['close']

        # Check metrics are present
        assert np.isfinite(result.total_return)

    def test_run_bollinger_bands(self, sample_ohlcv):
        """Test Bollinger Bands strategy backtest."""
        result = self.engine.run_bollinger_bands(
            sample_ohlcv[['close']],
            period=20,
            num_std=2.0
        )

        # Check result type
        assert isinstance(result, BacktestResult)

        # Check metrics
        assert np.isfinite(result.total_return)
        assert result.parameters == {'period': 20, 'num_std': 2.0}

    def test_commission_impact(self, sample_multi_asset_prices):
        """Test that commission reduces returns."""
        no_comm = BacktestEngine(BacktestConfig(commission=0.0, slippage=0.0))
        with_comm = BacktestEngine(BacktestConfig(commission=0.01, slippage=0.0))  # 1%

        result_no_comm = no_comm.run_ma_crossover(
            sample_multi_asset_prices, fast_period=10, slow_period=30
        )
        result_with_comm = with_comm.run_ma_crossover(
            sample_multi_asset_prices, fast_period=10, slow_period=30
        )

        # The comparison is only meaningful if some trades happened
        assert result_no_comm.total_trades > 0

        # Commission should reduce total return
        assert result_with_comm.total_return < result_no_comm.total_return

    def test_slippage_impact(self, sample_multi_asset_prices):
        """Test that slippage reduces returns."""
        no_slip = BacktestEngine(BacktestConfig(commission=0.0, slippage=0.0))
        with_slip = BacktestEngine(BacktestConfig(commission=0.0, slippage=0.005))  # 0.5%

        result_no_slip = no_slip.run_ma_crossover(
            sample_multi_asset_prices, fast_period=10, slow_period=30
        )
        result_with_slip = with_slip.run_ma_crossover(
            sample_multi_asset_prices, fast_period=10, slow_period=30
        )

        assert result_no_slip.total_trades > 0

        # Slippage should reduce total return
        assert result_with_slip.total_return < result_no_slip.total_return

    def test_equity_curve_properties(self, sample_multi_asset_prices):
        """Test equity curve properties."""
        result = self.engine.run_mean_reversion(
            sample_multi_asset_prices,
            lookback=20
        )

        equity_curve = result.equity_curve
        assert isinstance(equity_curve, pd.DataFrame)
        assert 'equity' in equity_curve.columns
        equity = equity_curve['equity']

        # Equity curve starts at initial capital (before any trade)
        assert equity.iloc[0] == pytest.approx(100000)

        # Final equity matches reported final value
        assert equity.iloc[-1] == pytest.approx(result.final_value)

        # Equity should be positive throughout
        assert (equity > 0).all()

    def test_returns_calculation(self, sample_multi_asset_prices):
        """Test returns derived from the equity curve match total return."""
        result = self.engine.run_ma_crossover(
            sample_multi_asset_prices,
            fast_period=10,
            slow_period=30
        )

        returns = result.equity_curve['equity'].pct_change().dropna()

        # Compounded daily returns should equal reported total return
        cumulative_return = (1 + returns).prod() - 1
        assert cumulative_return == pytest.approx(result.total_return, abs=1e-9)

    def test_parameter_optimization(self, sample_multi_asset_prices):
        """Test parameter optimization."""
        param_grid = {
            'fast_period': [5, 10],
            'slow_period': [20, 30]
        }

        results = self.engine.parameter_optimization(
            sample_multi_asset_prices,
            self.engine.run_ma_crossover,
            param_grid
        )

        # Should return DataFrame with all combinations
        assert isinstance(results, pd.DataFrame)
        assert len(results) == 4  # 2 x 2 combinations

        # Should have parameter and sharpe_ratio columns
        assert {'fast_period', 'slow_period', 'sharpe_ratio'} <= set(results.columns)

        # Sorted by the optimization metric (descending)
        assert results['sharpe_ratio'].is_monotonic_decreasing

    def test_single_asset_backtest(self, sample_prices):
        """Test backtest with single asset."""
        # Convert Series to DataFrame
        prices_df = pd.DataFrame({'AAPL': sample_prices})

        result = self.engine.run_mean_reversion(
            prices_df,
            lookback=20,
            entry_zscore=-2.0,
            exit_zscore=0.5
        )

        assert isinstance(result, BacktestResult)
        assert result.symbols == ['AAPL']
        assert np.isfinite(result.total_return)


class TestBacktestConfig:
    """Test suite for BacktestConfig dataclass."""

    def test_config_creation(self):
        """Test BacktestConfig creation with defaults."""
        config = BacktestConfig()

        assert config.initial_capital == 1_000_000  # Default
        assert config.commission == 0.001  # Default
        assert config.slippage == 0.0005  # Default
        assert config.allow_shorting is False

        # Engine without a config uses defaults
        assert BacktestEngine().config == config

    def test_config_custom_values(self):
        """Test BacktestConfig with custom values."""
        config = BacktestConfig(
            initial_capital=50000,
            commission=0.002,
            slippage=0.001
        )

        assert config.initial_capital == 50000
        assert config.commission == 0.002
        assert config.slippage == 0.001

        engine = BacktestEngine(config=config)
        assert engine.config.initial_capital == 50000


def _make_result(**overrides):
    """Build a BacktestResult with all required fields."""
    kwargs = dict(
        strategy_name='mean_reversion',
        symbols=['AAPL'],
        start_date=pd.Timestamp('2022-01-03').date(),
        end_date=pd.Timestamp('2022-01-05').date(),
        initial_capital=100000,
        final_value=115000,
        total_return=0.15,
        cagr=0.12,
        sharpe_ratio=1.5,
        sortino_ratio=2.0,
        max_drawdown=-0.10,
        calmar_ratio=1.2,
        total_trades=50,
        win_rate=0.55,
        profit_factor=1.8,
        avg_trade_return=0.003,
        equity_curve=pd.DataFrame({
            'date': pd.date_range('2022-01-03', periods=3, freq='B'),
            'equity': [100000, 105000, 115000],
        }),
        trades=pd.DataFrame(),
    )
    kwargs.update(overrides)
    return BacktestResult(**kwargs)


class TestBacktestResult:
    """Test suite for BacktestResult dataclass."""

    def test_result_creation(self):
        """Test BacktestResult creation."""
        result = _make_result()

        assert result.total_return == 0.15
        assert result.sharpe_ratio == 1.5
        assert result.win_rate == 0.55
        assert result.total_trades == 50
        assert result.parameters == {}

        d = result.to_dict()
        assert d['total_return'] == 0.15
        assert d['strategy_name'] == 'mean_reversion'
        assert 'mean_reversion' in result.summary()

    def test_result_with_trades(self):
        """Test BacktestResult with trade log."""
        trades = pd.DataFrame({
            'entry_date': ['2022-01-15', '2022-02-20'],
            'exit_date': ['2022-01-25', '2022-03-01'],
            'symbol': ['AAPL', 'AAPL'],
            'pnl': [500, -200]
        })

        result = _make_result(
            total_return=0.03,
            win_rate=0.5,
            profit_factor=2.5,
            total_trades=2,
            trades=trades,
        )

        assert result.trades is not None
        assert len(result.trades) == 2
        assert result.trades['pnl'].sum() == 300
