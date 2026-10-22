# -*- coding: utf-8 -*-
"""
Pairs Trading (Statistical Arbitrage) Strategy.

This module implements a cointegration-based pairs trading strategy
that exploits mean-reverting price relationships between correlated assets.
"""

import pandas as pd
import numpy as np
from typing import Optional, Tuple, Dict
from .base import BaseStrategy

try:
    import statsmodels.api as sm
    from statsmodels.tsa.stattools import adfuller, coint
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False


class PairsTradingStrategy(BaseStrategy):
    """
    Pairs trading strategy using cointegration.

    The strategy:
    1. Tests for cointegration between two assets
    2. Calculates hedge ratio (beta) via linear regression
    3. Computes spread = Y - beta * X
    4. Trades the spread using Z-score signals

    Attributes:
        entry_zscore: Z-score threshold to enter position
        exit_zscore: Z-score threshold to exit position
        lookback: Window for rolling calculations
        hedge_ratio: Calculated or fixed hedge ratio
    """

    def __init__(
        self,
        entry_zscore: float = 2.0,
        exit_zscore: float = 0.5,
        lookback: int = 60,
        hedge_ratio: Optional[float] = None,
        **kwargs
    ):
        """
        Initialize pairs trading strategy.

        Args:
            entry_zscore: Entry threshold Z-score
            exit_zscore: Exit threshold Z-score
            lookback: Rolling window for spread calculation
            hedge_ratio: Fixed hedge ratio (if None, calculated dynamically)
        """
        super().__init__(
            name="PairsTrading",
            entry_zscore=entry_zscore,
            exit_zscore=exit_zscore,
            lookback=lookback,
            hedge_ratio=hedge_ratio,
            **kwargs
        )
        self.entry_zscore = entry_zscore
        self.exit_zscore = exit_zscore
        self.lookback = lookback
        self.hedge_ratio = hedge_ratio
        self._calculated_hedge_ratio = None
        self._spread = None

    @staticmethod
    def test_cointegration(
        series_x: pd.Series,
        series_y: pd.Series,
        significance: float = 0.05
    ) -> Tuple[bool, float, float]:
        """
        Test for cointegration between two price series.

        Uses Engle-Granger two-step method.

        Args:
            series_x: First price series
            series_y: Second price series
            significance: Significance level for test

        Returns:
            Tuple of (is_cointegrated, p_value, hedge_ratio)
        """
        if not HAS_STATSMODELS:
            raise ImportError("statsmodels required for cointegration test")

        # Align series
        aligned = pd.concat([series_x, series_y], axis=1).dropna()
        x = aligned.iloc[:, 0]
        y = aligned.iloc[:, 1]

        # Run cointegration test
        score, pvalue, _ = coint(x, y)

        # Calculate hedge ratio via OLS
        X = sm.add_constant(x)
        model = sm.OLS(y, X).fit()
        hedge_ratio = model.params.iloc[1]

        is_cointegrated = pvalue < significance

        return is_cointegrated, pvalue, hedge_ratio

    def calculate_spread(
        self,
        series_x: pd.Series,
        series_y: pd.Series,
        hedge_ratio: Optional[float] = None
    ) -> pd.Series:
        """
        Calculate spread between two series.

        Args:
            series_x: First price series (X)
            series_y: Second price series (Y)
            hedge_ratio: Optional fixed hedge ratio

        Returns:
            Spread series = Y - hedge_ratio * X
        """
        if hedge_ratio is None:
            if self.hedge_ratio is not None:
                hedge_ratio = self.hedge_ratio
            else:
                # Calculate rolling hedge ratio
                if HAS_STATSMODELS:
                    X = sm.add_constant(series_x)
                    model = sm.OLS(series_y, X).fit()
                    hedge_ratio = model.params.iloc[1]
                else:
                    # Simple correlation-based estimate
                    hedge_ratio = (
                        series_y.cov(series_x) / series_x.var()
                    )

        self._calculated_hedge_ratio = hedge_ratio
        spread = series_y - hedge_ratio * series_x

        return spread

    def calculate_zscore(self, spread: pd.Series) -> pd.Series:
        """
        Calculate Z-score of spread.

        Args:
            spread: Spread series

        Returns:
            Z-score series
        """
        rolling_mean = spread.rolling(window=self.lookback).mean()
        rolling_std = spread.rolling(window=self.lookback).std()

        zscore = (spread - rolling_mean) / rolling_std
        return zscore

    def calculate_half_life(self, spread: pd.Series) -> float:
        """
        Calculate half-life of mean reversion.

        Uses Ornstein-Uhlenbeck process estimation.

        Args:
            spread: Spread series

        Returns:
            Half-life in periods
        """
        if not HAS_STATSMODELS:
            return np.nan

        # AR(1) regression to estimate mean reversion speed
        spread_lag = spread.shift(1)
        spread_diff = spread - spread_lag

        # Drop NaN
        valid_idx = ~(spread_lag.isna() | spread_diff.isna())
        X = sm.add_constant(spread_lag[valid_idx])
        y = spread_diff[valid_idx]

        try:
            model = sm.OLS(y, X).fit()
            theta = -model.params.iloc[1]  # Mean reversion speed

            if theta <= 0:
                return np.inf  # No mean reversion

            half_life = np.log(2) / theta
            return half_life
        except Exception:
            return np.nan

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """
        Generate pairs trading signals.

        Args:
            prices: DataFrame with two columns (X and Y price series)

        Returns:
            DataFrame with signals for each asset
        """
        if prices.shape[1] < 2:
            raise ValueError("Pairs trading requires at least two assets")

        # Use first two columns as the pair
        col_x = prices.columns[0]
        col_y = prices.columns[1]

        series_x = prices[col_x]
        series_y = prices[col_y]

        # Calculate spread
        spread = self.calculate_spread(series_x, series_y)
        self._spread = spread

        # Calculate Z-score
        zscore = self.calculate_zscore(spread)

        # Generate signals
        signals = self._generate_spread_signals(zscore)

        # Return signals for both assets
        # When spread signal is 1 (long spread): long Y, short X
        # When spread signal is -1 (short spread): short Y, long X
        return pd.DataFrame({
            col_x: -signals,  # Opposite of spread signal
            col_y: signals,   # Same as spread signal
            'spread_signal': signals
        }, index=prices.index)

    def _generate_spread_signals(self, zscore: pd.Series) -> pd.Series:
        """
        Generate signals from spread Z-score.

        Args:
            zscore: Z-score of spread

        Returns:
            Signal series
        """
        signals = pd.Series(index=zscore.index, data=0.0)
        position = 0

        for i in range(len(zscore)):
            z = zscore.iloc[i]

            if pd.isna(z):
                signals.iloc[i] = 0
                continue

            # Entry conditions
            if position == 0:
                if z < -self.entry_zscore:
                    position = 1  # Long spread (spread too low)
                elif z > self.entry_zscore:
                    position = -1  # Short spread (spread too high)

            # Exit conditions
            elif position == 1:  # Long spread
                if z >= -self.exit_zscore:
                    position = 0
                elif z > self.entry_zscore:
                    position = -1  # Reverse

            elif position == -1:  # Short spread
                if z <= self.exit_zscore:
                    position = 0
                elif z < -self.entry_zscore:
                    position = 1  # Reverse

            signals.iloc[i] = position

        return signals

    def get_spread_analysis(self, prices: pd.DataFrame) -> Dict:
        """
        Get spread analysis data.

        Args:
            prices: Price data with two columns

        Returns:
            Dictionary with analysis results
        """
        col_x = prices.columns[0]
        col_y = prices.columns[1]

        series_x = prices[col_x]
        series_y = prices[col_y]

        # Calculate spread
        spread = self.calculate_spread(series_x, series_y)

        # Calculate Z-score
        zscore = self.calculate_zscore(spread)

        # Calculate half-life
        half_life = self.calculate_half_life(spread)

        # Test cointegration
        if HAS_STATSMODELS:
            is_coint, pvalue, _ = self.test_cointegration(series_x, series_y)
        else:
            is_coint, pvalue = None, None

        return {
            'spread': spread,
            'zscore': zscore,
            'hedge_ratio': self._calculated_hedge_ratio,
            'half_life': half_life,
            'is_cointegrated': is_coint,
            'cointegration_pvalue': pvalue,
            'spread_mean': spread.mean(),
            'spread_std': spread.std()
        }
