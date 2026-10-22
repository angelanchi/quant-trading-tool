# -*- coding: utf-8 -*-
"""
Mean Reversion Trading Strategy.

This module implements a Z-score based mean reversion strategy
that trades based on price deviations from a rolling mean.
"""

import pandas as pd
import numpy as np
from typing import Optional
from .base import BaseStrategy


class MeanReversionStrategy(BaseStrategy):
    """
    Mean reversion strategy using Z-score signals.

    The strategy:
    - Calculates rolling mean and standard deviation
    - Computes Z-score = (price - mean) / std
    - Goes long when Z-score < -entry_threshold (price too low)
    - Goes short when Z-score > entry_threshold (price too high)
    - Exits when Z-score crosses exit_threshold

    Attributes:
        lookback: Rolling window for mean/std calculation
        entry_zscore: Z-score threshold to enter position
        exit_zscore: Z-score threshold to exit position
    """

    def __init__(
        self,
        lookback: int = 20,
        entry_zscore: float = 2.0,
        exit_zscore: float = 0.5,
        **kwargs
    ):
        """
        Initialize mean reversion strategy.

        Args:
            lookback: Rolling window period (default: 20)
            entry_zscore: Entry threshold Z-score (default: 2.0)
            exit_zscore: Exit threshold Z-score (default: 0.5)
        """
        super().__init__(
            name="MeanReversion",
            lookback=lookback,
            entry_zscore=entry_zscore,
            exit_zscore=exit_zscore,
            **kwargs
        )
        self.lookback = lookback
        self.entry_zscore = entry_zscore
        self.exit_zscore = exit_zscore

    def calculate_zscore(self, prices: pd.Series) -> pd.Series:
        """
        Calculate rolling Z-score.

        Args:
            prices: Price series

        Returns:
            Z-score series
        """
        rolling_mean = prices.rolling(window=self.lookback).mean()
        rolling_std = prices.rolling(window=self.lookback).std()

        zscore = (prices - rolling_mean) / rolling_std
        return zscore

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """
        Generate mean reversion trading signals.

        Args:
            prices: DataFrame with price data (uses 'close' if available)

        Returns:
            DataFrame with signals (-1: short, 0: flat, 1: long)
        """
        # Extract close prices
        if isinstance(prices, pd.DataFrame):
            if 'close' in prices.columns:
                close = prices['close']
            else:
                close = prices.iloc[:, 0]
            columns = prices.columns if 'close' not in prices.columns else ['close']
        else:
            close = prices
            columns = ['signal']

        # For single asset
        if isinstance(close, pd.Series):
            zscore = self.calculate_zscore(close)
            signals = self._generate_signal_series(zscore)
            return pd.DataFrame({'signal': signals}, index=close.index)

        # For multiple assets
        signals_dict = {}
        for col in prices.columns:
            if col in ['open', 'high', 'low', 'volume']:
                continue
            zscore = self.calculate_zscore(prices[col])
            signals_dict[col] = self._generate_signal_series(zscore)

        return pd.DataFrame(signals_dict)

    def _generate_signal_series(self, zscore: pd.Series) -> pd.Series:
        """
        Generate signal series from Z-score.

        Args:
            zscore: Z-score series

        Returns:
            Signal series
        """
        signals = pd.Series(index=zscore.index, data=0.0)

        # Track position state
        position = 0

        for i in range(len(zscore)):
            z = zscore.iloc[i]

            if pd.isna(z):
                signals.iloc[i] = 0
                continue

            # Entry conditions
            if position == 0:
                if z < -self.entry_zscore:
                    position = 1  # Long
                elif z > self.entry_zscore:
                    position = -1  # Short

            # Exit conditions
            elif position == 1:  # Currently long
                if z >= -self.exit_zscore:
                    position = 0  # Exit
                # Check for reversal
                elif z > self.entry_zscore:
                    position = -1  # Reverse to short

            elif position == -1:  # Currently short
                if z <= self.exit_zscore:
                    position = 0  # Exit
                # Check for reversal
                elif z < -self.entry_zscore:
                    position = 1  # Reverse to long

            signals.iloc[i] = position

        return signals

    def get_zscore_data(self, prices: pd.DataFrame) -> pd.DataFrame:
        """
        Get Z-score data for analysis.

        Args:
            prices: Price data

        Returns:
            DataFrame with price, mean, std, and Z-score
        """
        if isinstance(prices, pd.DataFrame):
            close = prices['close'] if 'close' in prices.columns else prices.iloc[:, 0]
        else:
            close = prices

        rolling_mean = close.rolling(window=self.lookback).mean()
        rolling_std = close.rolling(window=self.lookback).std()
        zscore = (close - rolling_mean) / rolling_std

        return pd.DataFrame({
            'price': close,
            'rolling_mean': rolling_mean,
            'rolling_std': rolling_std,
            'zscore': zscore,
            'upper_band': rolling_mean + self.entry_zscore * rolling_std,
            'lower_band': rolling_mean - self.entry_zscore * rolling_std
        })


class BollingerBandStrategy(MeanReversionStrategy):
    """
    Bollinger Band mean reversion strategy.

    Similar to mean reversion but uses Bollinger Bands terminology.
    """

    def __init__(
        self,
        period: int = 20,
        num_std: float = 2.0,
        exit_std: float = 0.5,
        **kwargs
    ):
        """
        Initialize Bollinger Band strategy.

        Args:
            period: Rolling window period
            num_std: Number of standard deviations for bands
            exit_std: Standard deviations for exit
        """
        super().__init__(
            lookback=period,
            entry_zscore=num_std,
            exit_zscore=exit_std,
            **kwargs
        )
        self.name = "BollingerBands"
