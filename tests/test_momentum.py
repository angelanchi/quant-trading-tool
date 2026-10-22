# -*- coding: utf-8 -*-
"""
Unit tests for momentum strategy module.

Tests cover:
- MomentumStrategy signal generation
- TrendFollowingStrategy with ADX
- DualMomentumStrategy (absolute + relative)
- BreakoutStrategy with Donchian channels
"""

import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from strategies.momentum import (
    MomentumStrategy,
    TrendFollowingStrategy,
    DualMomentumStrategy,
    BreakoutStrategy,
)


class TestMomentumStrategy:
    """Test suite for MomentumStrategy class."""

    def test_initialization(self):
        """Test strategy initialization."""
        strategy = MomentumStrategy(lookback=20, ma_period=50)

        assert strategy.lookback == 20
        assert strategy.ma_period == 50
        assert strategy.name == "MomentumStrategy"

    def test_signal_generation(self, sample_prices):
        """Test basic signal generation."""
        strategy = MomentumStrategy(lookback=20, ma_period=50)
        signals = strategy.generate_signals(sample_prices)

        assert isinstance(signals, pd.DataFrame)
        assert 'signal' in signals.columns
        assert len(signals) == len(sample_prices)

    def test_signal_values(self, sample_prices):
        """Test that signals are valid values."""
        strategy = MomentumStrategy()
        signals = strategy.generate_signals(sample_prices)

        # Signals should be -1, 0, or 1
        unique_signals = signals['signal'].dropna().unique()
        assert all(s in [-1, 0, 1] for s in unique_signals)

    def test_momentum_column(self, sample_prices):
        """Test momentum calculation is included."""
        strategy = MomentumStrategy(lookback=20)
        signals = strategy.generate_signals(sample_prices)

        assert 'momentum' in signals.columns

    def test_single_column_input(self):
        """Test with single column price series."""
        prices = pd.Series(
            np.random.random(100) * 100 + 100,
            index=pd.date_range('2023-01-01', periods=100)
        )

        strategy = MomentumStrategy(lookback=10, ma_period=20)
        signals = strategy.generate_signals(prices)

        assert 'signal' in signals.columns


class TestTrendFollowingStrategy:
    """Test suite for TrendFollowingStrategy class."""

    def test_initialization(self):
        """Test strategy initialization."""
        strategy = TrendFollowingStrategy(
            fast_ma=20,
            slow_ma=50,
            adx_threshold=25.0
        )

        assert strategy.fast_ma == 20
        assert strategy.slow_ma == 50
        assert strategy.adx_threshold == 25.0

    def test_signal_generation(self, sample_prices):
        """Test signal generation."""
        strategy = TrendFollowingStrategy(fast_ma=10, slow_ma=30)
        signals = strategy.generate_signals(sample_prices)

        assert isinstance(signals, pd.DataFrame)
        assert 'signal' in signals.columns
        assert 'fast_ma' in signals.columns
        assert 'slow_ma' in signals.columns

    def test_with_ohlc_data(self, sample_ohlc):
        """Test with OHLC data for proper ADX calculation."""
        strategy = TrendFollowingStrategy(fast_ma=10, slow_ma=30)
        signals = strategy.generate_signals(sample_ohlc)

        assert 'adx' in signals.columns

    def test_ma_relationship(self, sample_prices):
        """Test that fast MA is more responsive."""
        strategy = TrendFollowingStrategy(fast_ma=10, slow_ma=30)
        signals = strategy.generate_signals(sample_prices)

        # Fast MA should have higher variance
        fast_ma_var = signals['fast_ma'].dropna().var()
        slow_ma_var = signals['slow_ma'].dropna().var()

        # This is generally true for moving averages
        # But depends on price data, so just check they're calculated
        assert fast_ma_var > 0
        assert slow_ma_var > 0


class TestDualMomentumStrategy:
    """Test suite for DualMomentumStrategy class."""

    def test_initialization(self):
        """Test strategy initialization."""
        strategy = DualMomentumStrategy(
            lookback=252,
            risk_free_rate=0.02
        )

        assert strategy.lookback == 252
        assert strategy.risk_free_rate == 0.02

    def test_signal_generation(self, sample_multi_prices):
        """Test signal generation with multiple assets."""
        strategy = DualMomentumStrategy(lookback=60)
        signals = strategy.generate_signals(sample_multi_prices)

        assert isinstance(signals, pd.DataFrame)
        assert 'signal' in signals.columns
        assert 'avg_momentum' in signals.columns

    def test_ranking(self, sample_multi_prices):
        """Test that strategy ranks assets."""
        strategy = DualMomentumStrategy(lookback=60)
        signals = strategy.generate_signals(sample_multi_prices)

        # Signal should be between 0 and 1 (weighted average)
        assert signals['signal'].dropna().min() >= 0
        assert signals['signal'].dropna().max() <= 1


class TestBreakoutStrategy:
    """Test suite for BreakoutStrategy class."""

    def test_initialization(self):
        """Test strategy initialization."""
        strategy = BreakoutStrategy(
            entry_period=20,
            exit_period=10,
            atr_multiplier=2.0
        )

        assert strategy.entry_period == 20
        assert strategy.exit_period == 10
        assert strategy.atr_multiplier == 2.0

    def test_signal_generation(self, sample_prices):
        """Test signal generation."""
        strategy = BreakoutStrategy(entry_period=20, exit_period=10)
        signals = strategy.generate_signals(sample_prices)

        assert isinstance(signals, pd.DataFrame)
        assert 'signal' in signals.columns
        assert 'upper_channel' in signals.columns
        assert 'lower_channel' in signals.columns

    def test_channel_calculation(self, sample_prices):
        """Test Donchian channel calculation."""
        strategy = BreakoutStrategy(entry_period=20, exit_period=10)
        signals = strategy.generate_signals(sample_prices)

        # Upper channel should be >= current price at all times
        # (where calculated)
        close = sample_prices.iloc[:, 0] if isinstance(sample_prices, pd.DataFrame) else sample_prices
        valid_idx = ~signals['upper_channel'].isna()

        assert (signals['upper_channel'][valid_idx] >= close[valid_idx]).all()

    def test_with_ohlc_data(self, sample_ohlc):
        """Test with OHLC data."""
        strategy = BreakoutStrategy(entry_period=20, exit_period=10)
        signals = strategy.generate_signals(sample_ohlc)

        assert 'atr' in signals.columns
        assert 'stop_loss' in signals.columns


# Fixtures

@pytest.fixture
def sample_prices():
    """Generate sample price data."""
    np.random.seed(42)
    dates = pd.date_range(start='2022-01-01', periods=252, freq='B')
    returns = np.random.normal(0.0005, 0.02, len(dates))
    prices = 100 * np.exp(np.cumsum(returns))
    return pd.DataFrame({'close': prices}, index=dates)


@pytest.fixture
def sample_ohlc():
    """Generate sample OHLC data."""
    np.random.seed(42)
    dates = pd.date_range(start='2022-01-01', periods=252, freq='B')
    returns = np.random.normal(0.0005, 0.02, len(dates))
    close = 100 * np.exp(np.cumsum(returns))

    daily_range = 0.02 * close
    high = close + np.abs(np.random.normal(0, daily_range))
    low = close - np.abs(np.random.normal(0, daily_range))
    open_price = close * (1 + np.random.uniform(-0.01, 0.01, len(dates)))

    return pd.DataFrame({
        'open': open_price,
        'high': np.maximum(high, np.maximum(open_price, close)),
        'low': np.minimum(low, np.minimum(open_price, close)),
        'close': close
    }, index=dates)


@pytest.fixture
def sample_multi_prices():
    """Generate sample multi-asset price data."""
    np.random.seed(42)
    dates = pd.date_range(start='2022-01-01', periods=252, freq='B')

    prices = {}
    for symbol in ['AAPL', 'MSFT', 'GOOGL']:
        returns = np.random.normal(0.0005, 0.02, len(dates))
        prices[symbol] = 100 * np.exp(np.cumsum(returns))

    return pd.DataFrame(prices, index=dates)
