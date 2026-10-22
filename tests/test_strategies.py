# -*- coding: utf-8 -*-
"""
Unit tests for trading strategies module.

Tests cover:
- BaseStrategy interface
- MeanReversionStrategy
- BollingerBandStrategy
- PairsTradingStrategy
- Signal generation
- Backtest integration
"""

import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from strategies import (
    BaseStrategy,
    Signal,
    StrategyResult,
    MeanReversionStrategy,
    BollingerBandStrategy,
    PairsTradingStrategy
)


class TestBaseStrategy:
    """Test suite for BaseStrategy class."""

    def test_signal_dataclass(self):
        """Test Signal dataclass creation."""
        signal = Signal(
            timestamp=pd.Timestamp('2022-01-15'),
            symbol='AAPL',
            action='BUY',
            quantity=100,
            price=150.0,
            confidence=0.8
        )

        assert signal.symbol == 'AAPL'
        assert signal.action == 'BUY'
        assert signal.confidence == 0.8

    def test_strategy_result_dataclass(self):
        """Test StrategyResult dataclass creation."""
        signals = pd.DataFrame({'signal': [0, 1, 1, 0, -1]})
        entries = pd.Series([False, True, False, False, True])
        exits = pd.Series([False, False, False, True, False])
        positions = pd.Series([0, 1, 1, 0, -1])
        returns = pd.Series([0.0, 0.01, 0.02, -0.01, 0.0])

        result = StrategyResult(
            signals=signals,
            entries=entries,
            exits=exits,
            positions=positions,
            returns=returns
        )

        assert result.signals is not None
        assert len(result.positions) == 5


class TestMeanReversionStrategy:
    """Test suite for MeanReversionStrategy."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        self.strategy = MeanReversionStrategy(
            lookback=20,
            entry_zscore=2.0,
            exit_zscore=0.5
        )

    def test_initialization(self):
        """Test strategy initialization."""
        assert self.strategy.name == "MeanReversion"
        assert self.strategy.lookback == 20
        assert self.strategy.entry_zscore == 2.0
        assert self.strategy.exit_zscore == 0.5

    def test_calculate_zscore(self, sample_prices):
        """Test Z-score calculation."""
        zscore = self.strategy.calculate_zscore(sample_prices)

        # Z-score should have same length as input
        assert len(zscore) == len(sample_prices)

        # First lookback-1 values should be NaN
        assert zscore.iloc[:self.strategy.lookback-1].isna().all()

        # Z-score should be standardized (mean ~0, std ~1 after warmup)
        valid_zscore = zscore.dropna()
        assert abs(valid_zscore.mean()) < 0.5  # Should be close to 0
        assert 0.5 < valid_zscore.std() < 1.5  # Should be close to 1

    def test_generate_signals(self, sample_ohlcv):
        """Test signal generation."""
        signals = self.strategy.generate_signals(sample_ohlcv)

        # Should return DataFrame
        assert isinstance(signals, pd.DataFrame)

        # Signals should be -1, 0, or 1
        unique_signals = signals['signal'].dropna().unique()
        assert all(s in [-1, 0, 1] for s in unique_signals)

    def test_signal_logic(self):
        """Test signal generation logic."""
        # Create data with known Z-score pattern
        np.random.seed(42)
        dates = pd.date_range(start='2022-01-01', periods=100, freq='B')

        # Price that drops significantly then recovers
        prices = pd.Series([100] * 30 + [90] * 10 + [100] * 60, index=dates)

        strategy = MeanReversionStrategy(lookback=20, entry_zscore=1.5, exit_zscore=0.0)
        signals = strategy.generate_signals(pd.DataFrame({'close': prices}))

        # After price drop, should generate long signal
        # (This is a simplified check - actual behavior depends on Z-score)
        assert signals['signal'].sum() != 0  # Should have some signals

    def test_get_zscore_data(self, sample_prices):
        """Test Z-score data retrieval."""
        data = self.strategy.get_zscore_data(sample_prices)

        # Should have all required columns
        assert 'price' in data.columns
        assert 'rolling_mean' in data.columns
        assert 'rolling_std' in data.columns
        assert 'zscore' in data.columns
        assert 'upper_band' in data.columns
        assert 'lower_band' in data.columns

    def test_backtest_integration(self, sample_ohlcv):
        """Test backtest method."""
        result = self.strategy.backtest(
            sample_ohlcv,
            initial_capital=100000,
            commission=0.001
        )

        # Should return StrategyResult
        assert isinstance(result, StrategyResult)
        assert result.returns is not None


class TestBollingerBandStrategy:
    """Test suite for BollingerBandStrategy."""

    def test_initialization(self):
        """Test Bollinger Band strategy initialization."""
        strategy = BollingerBandStrategy(
            period=20,
            num_std=2.0,
            exit_std=0.5
        )

        assert strategy.name == "BollingerBands"
        assert strategy.lookback == 20
        assert strategy.entry_zscore == 2.0

    def test_inherits_from_mean_reversion(self):
        """Test that BB strategy inherits from MeanReversion."""
        strategy = BollingerBandStrategy()
        assert isinstance(strategy, MeanReversionStrategy)

    def test_generate_signals(self, sample_ohlcv):
        """Test signal generation."""
        strategy = BollingerBandStrategy(period=20, num_std=2.0)
        signals = strategy.generate_signals(sample_ohlcv)

        assert isinstance(signals, pd.DataFrame)
        assert 'signal' in signals.columns


class TestPairsTradingStrategy:
    """Test suite for PairsTradingStrategy."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        self.strategy = PairsTradingStrategy(
            entry_zscore=2.0,
            exit_zscore=0.5,
            lookback=60
        )

    def test_initialization(self):
        """Test strategy initialization."""
        assert self.strategy.name == "PairsTrading"
        assert self.strategy.entry_zscore == 2.0
        assert self.strategy.lookback == 60

    def test_cointegration_test(self, sample_cointegrated_pair):
        """Test cointegration testing."""
        try:
            is_coint, pvalue, hedge_ratio = self.strategy.test_cointegration(
                sample_cointegrated_pair['X'],
                sample_cointegrated_pair['Y']
            )

            # Should detect cointegration in our synthetic pair
            assert isinstance(is_coint, bool)
            assert 0 <= pvalue <= 1
            assert hedge_ratio > 0  # Positive hedge ratio for our data

        except ImportError:
            pytest.skip("statsmodels not available")

    def test_calculate_spread(self, sample_cointegrated_pair):
        """Test spread calculation."""
        spread = self.strategy.calculate_spread(
            sample_cointegrated_pair['X'],
            sample_cointegrated_pair['Y']
        )

        # Spread should be same length as input
        assert len(spread) == len(sample_cointegrated_pair)

        # Spread should be stationary (mean-reverting) for cointegrated pair
        # Check that spread doesn't trend too much
        spread_returns = spread.diff().dropna()
        assert abs(spread_returns.mean()) < spread_returns.std()

    def test_calculate_zscore(self, sample_cointegrated_pair):
        """Test spread Z-score calculation."""
        spread = self.strategy.calculate_spread(
            sample_cointegrated_pair['X'],
            sample_cointegrated_pair['Y']
        )
        zscore = self.strategy.calculate_zscore(spread)

        # Z-score should have same length as spread
        assert len(zscore) == len(spread)

        # Valid Z-scores should be roughly standardized
        valid_zscore = zscore.dropna()
        assert abs(valid_zscore.mean()) < 1.0

    def test_calculate_half_life(self, sample_cointegrated_pair):
        """Test half-life calculation."""
        spread = self.strategy.calculate_spread(
            sample_cointegrated_pair['X'],
            sample_cointegrated_pair['Y']
        )

        try:
            half_life = self.strategy.calculate_half_life(spread)

            # Half-life should be positive for mean-reverting spread
            if not np.isinf(half_life):
                assert half_life > 0

        except ImportError:
            pytest.skip("statsmodels not available")

    def test_generate_signals(self, sample_cointegrated_pair):
        """Test signal generation for pairs."""
        signals = self.strategy.generate_signals(sample_cointegrated_pair)

        # Should have signals for both assets
        assert 'X' in signals.columns
        assert 'Y' in signals.columns

        # X and Y signals should be opposite
        assert (signals['X'] == -signals['Y']).all()

    def test_get_spread_analysis(self, sample_cointegrated_pair):
        """Test spread analysis data."""
        analysis = self.strategy.get_spread_analysis(sample_cointegrated_pair)

        # Should have all analysis components
        assert 'spread' in analysis
        assert 'zscore' in analysis
        assert 'hedge_ratio' in analysis
        assert 'half_life' in analysis
        assert 'spread_mean' in analysis
        assert 'spread_std' in analysis

    def test_requires_two_assets(self, sample_prices):
        """Test that strategy requires at least two assets."""
        single_asset = pd.DataFrame({'AAPL': sample_prices})

        with pytest.raises(ValueError):
            self.strategy.generate_signals(single_asset)


class TestStrategyParameters:
    """Test suite for strategy parameter handling."""

    def test_strategy_repr(self):
        """Test strategy string representation."""
        strategy = MeanReversionStrategy(lookback=25, entry_zscore=1.5)
        repr_str = repr(strategy)

        assert 'MeanReversion' in repr_str
        assert 'lookback=25' in repr_str

    def test_parameter_storage(self):
        """Test that parameters are stored correctly."""
        strategy = MeanReversionStrategy(
            lookback=30,
            entry_zscore=2.5,
            exit_zscore=0.75,
            custom_param='test'
        )

        assert strategy.parameters['lookback'] == 30
        assert strategy.parameters['entry_zscore'] == 2.5
        assert strategy.parameters['custom_param'] == 'test'

    def test_fit_method(self, sample_prices):
        """Test fit method."""
        strategy = MeanReversionStrategy()
        result = strategy.fit(pd.DataFrame({'close': sample_prices}))

        # fit should return self for method chaining
        assert result is strategy
        assert strategy._fitted is True
