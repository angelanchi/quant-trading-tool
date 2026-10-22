# -*- coding: utf-8 -*-
"""
Momentum trading strategies.

Strategies based on price momentum and trend following.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

from .base import BaseStrategy, Signal, StrategyResult


class MomentumStrategy(BaseStrategy):
    """
    Classic momentum strategy.

    Buys assets with positive momentum (price above moving average)
    and sells when momentum turns negative.

    Parameters:
        lookback: Period for momentum calculation
        ma_period: Moving average period for trend filter
        min_momentum: Minimum momentum threshold to trigger signal
    """

    def __init__(
        self,
        lookback: int = 20,
        ma_period: int = 50,
        min_momentum: float = 0.0,
        **kwargs
    ):
        super().__init__(
            name="MomentumStrategy",
            lookback=lookback,
            ma_period=ma_period,
            min_momentum=min_momentum,
            **kwargs
        )
        self.lookback = lookback
        self.ma_period = ma_period
        self.min_momentum = min_momentum

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """
        Generate momentum-based trading signals.

        Signal logic:
        - Buy when: momentum > min_momentum AND price > MA
        - Sell when: momentum < -min_momentum OR price < MA

        Args:
            prices: DataFrame with price data

        Returns:
            DataFrame with signals (1=long, -1=short, 0=neutral)
        """
        if isinstance(prices, pd.Series):
            prices = prices.to_frame()

        signals = pd.DataFrame(index=prices.index)

        for col in prices.columns:
            price = prices[col]

            # Calculate momentum (rate of change)
            momentum = price.pct_change(self.lookback)

            # Calculate moving average
            ma = price.rolling(self.ma_period).mean()

            # Generate signals
            signal = pd.Series(0, index=prices.index)

            # Long signal: positive momentum and price above MA
            long_condition = (momentum > self.min_momentum) & (price > ma)
            signal[long_condition] = 1

            # Short signal: negative momentum and price below MA
            short_condition = (momentum < -self.min_momentum) & (price < ma)
            signal[short_condition] = -1

            signals[col] = signal

        # Aggregate signal if multiple columns
        if len(signals.columns) > 1:
            signals['signal'] = signals.mean(axis=1).apply(
                lambda x: 1 if x > 0.5 else (-1 if x < -0.5 else 0)
            )
        else:
            signals['signal'] = signals.iloc[:, 0]

        signals['momentum'] = momentum if len(prices.columns) == 1 else prices.iloc[:, 0].pct_change(self.lookback)

        return signals


class TrendFollowingStrategy(BaseStrategy):
    """
    Trend following strategy using multiple timeframes.

    Uses short-term and long-term moving averages to identify trends,
    combined with ADX for trend strength confirmation.

    Parameters:
        fast_ma: Fast moving average period
        slow_ma: Slow moving average period
        adx_period: ADX calculation period
        adx_threshold: Minimum ADX for trend confirmation
    """

    def __init__(
        self,
        fast_ma: int = 20,
        slow_ma: int = 50,
        adx_period: int = 14,
        adx_threshold: float = 25.0,
        **kwargs
    ):
        super().__init__(
            name="TrendFollowingStrategy",
            fast_ma=fast_ma,
            slow_ma=slow_ma,
            adx_period=adx_period,
            adx_threshold=adx_threshold,
            **kwargs
        )
        self.fast_ma = fast_ma
        self.slow_ma = slow_ma
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold

    def _calculate_adx(self, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        """
        Calculate Average Directional Index (ADX).

        ADX measures trend strength regardless of direction.
        Values > 25 indicate a strong trend.
        """
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # Directional Movement
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

        # Smoothed values
        atr = tr.rolling(self.adx_period).mean()
        plus_di = 100 * pd.Series(plus_dm).rolling(self.adx_period).mean() / atr
        minus_di = 100 * pd.Series(minus_dm).rolling(self.adx_period).mean() / atr

        # ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(self.adx_period).mean()

        return adx

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trend following signals.

        Signal logic:
        - Buy when: fast_ma > slow_ma AND ADX > threshold (strong uptrend)
        - Sell when: fast_ma < slow_ma AND ADX > threshold (strong downtrend)
        - Neutral when: ADX < threshold (weak/no trend)

        Args:
            prices: DataFrame with OHLC or close prices

        Returns:
            DataFrame with signals
        """
        signals = pd.DataFrame(index=prices.index)

        # Get close prices
        if 'close' in prices.columns:
            close = prices['close']
            high = prices.get('high', close)
            low = prices.get('low', close)
        else:
            close = prices.iloc[:, 0] if isinstance(prices, pd.DataFrame) else prices
            high = close
            low = close

        # Calculate moving averages
        fast_ma = close.rolling(self.fast_ma).mean()
        slow_ma = close.rolling(self.slow_ma).mean()

        # Calculate ADX if we have OHLC data
        if 'high' in prices.columns and 'low' in prices.columns:
            adx = self._calculate_adx(high, low, close)
        else:
            # Simplified: use volatility as trend strength proxy
            adx = close.pct_change().rolling(self.adx_period).std() * 100 * np.sqrt(252)
            adx = adx / adx.rolling(50).mean() * 25  # Normalize

        # Generate signals
        signal = pd.Series(0, index=prices.index)

        # Strong uptrend
        uptrend = (fast_ma > slow_ma) & (adx > self.adx_threshold)
        signal[uptrend] = 1

        # Strong downtrend
        downtrend = (fast_ma < slow_ma) & (adx > self.adx_threshold)
        signal[downtrend] = -1

        signals['signal'] = signal
        signals['fast_ma'] = fast_ma
        signals['slow_ma'] = slow_ma
        signals['adx'] = adx

        return signals


class DualMomentumStrategy(BaseStrategy):
    """
    Dual momentum strategy (absolute + relative momentum).

    Combines:
    1. Absolute momentum: Is the asset trending up?
    2. Relative momentum: Is this asset outperforming others?

    Only takes positions when both conditions are met.

    Parameters:
        lookback: Period for momentum calculation
        risk_free_rate: Annual risk-free rate for excess return
    """

    def __init__(
        self,
        lookback: int = 252,
        risk_free_rate: float = 0.02,
        **kwargs
    ):
        super().__init__(
            name="DualMomentumStrategy",
            lookback=lookback,
            risk_free_rate=risk_free_rate,
            **kwargs
        )
        self.lookback = lookback
        self.risk_free_rate = risk_free_rate

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """
        Generate dual momentum signals.

        For each asset:
        1. Check absolute momentum (return > risk-free rate)
        2. Rank by relative momentum (cross-sectional)
        3. Only invest in top performers with positive absolute momentum

        Args:
            prices: DataFrame with multiple asset prices

        Returns:
            DataFrame with signals
        """
        if isinstance(prices, pd.Series):
            prices = prices.to_frame()

        signals = pd.DataFrame(index=prices.index)

        # Calculate returns
        returns = prices.pct_change(self.lookback)

        # Daily risk-free rate equivalent
        rf_period = (1 + self.risk_free_rate) ** (self.lookback / 252) - 1

        # Absolute momentum: excess return over risk-free
        excess_returns = returns - rf_period
        abs_momentum = excess_returns > 0

        # Relative momentum: rank assets
        rel_momentum_rank = returns.rank(axis=1, ascending=False)

        # Generate signals for each asset
        for col in prices.columns:
            signal = pd.Series(0, index=prices.index)

            # Long if:
            # 1. Positive absolute momentum
            # 2. Top half in relative momentum (rank <= n_assets/2)
            n_assets = len(prices.columns)
            top_rank_threshold = max(1, n_assets // 2)

            long_condition = (
                abs_momentum[col] &
                (rel_momentum_rank[col] <= top_rank_threshold)
            )
            signal[long_condition] = 1

            signals[col] = signal

        # Aggregate: equal weight top performers
        signals['signal'] = signals[prices.columns].sum(axis=1) / len(prices.columns)
        signals['avg_momentum'] = returns.mean(axis=1)

        return signals


class BreakoutStrategy(BaseStrategy):
    """
    Price breakout strategy.

    Trades breakouts from consolidation ranges using
    Donchian channels or N-period highs/lows.

    Parameters:
        entry_period: Period for entry breakout (e.g., 20-day high)
        exit_period: Period for exit (e.g., 10-day low)
        atr_period: ATR period for volatility filter
        atr_multiplier: ATR multiplier for position sizing
    """

    def __init__(
        self,
        entry_period: int = 20,
        exit_period: int = 10,
        atr_period: int = 14,
        atr_multiplier: float = 2.0,
        **kwargs
    ):
        super().__init__(
            name="BreakoutStrategy",
            entry_period=entry_period,
            exit_period=exit_period,
            atr_period=atr_period,
            atr_multiplier=atr_multiplier,
            **kwargs
        )
        self.entry_period = entry_period
        self.exit_period = exit_period
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier

    def _calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        """Calculate Average True Range."""
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(self.atr_period).mean()

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """
        Generate breakout signals.

        Signal logic:
        - Buy when: price breaks above N-period high
        - Sell when: price breaks below M-period low
        - Use ATR for stop-loss levels

        Args:
            prices: DataFrame with price data

        Returns:
            DataFrame with signals and levels
        """
        signals = pd.DataFrame(index=prices.index)

        # Get prices
        if 'close' in prices.columns:
            close = prices['close']
            high = prices.get('high', close)
            low = prices.get('low', close)
        else:
            close = prices.iloc[:, 0] if isinstance(prices, pd.DataFrame) else prices
            high = close
            low = close

        # Calculate Donchian channels
        upper_channel = high.rolling(self.entry_period).max()
        lower_channel = low.rolling(self.exit_period).min()

        # Calculate ATR
        atr = self._calculate_atr(high, low, close)

        # Generate signals
        signal = pd.Series(0, index=prices.index)
        position = 0

        for i in range(max(self.entry_period, self.exit_period), len(prices)):
            if position == 0:
                # No position: look for entry
                if close.iloc[i] > upper_channel.iloc[i-1]:
                    signal.iloc[i] = 1
                    position = 1
                elif close.iloc[i] < lower_channel.iloc[i-1]:
                    signal.iloc[i] = -1
                    position = -1
            elif position == 1:
                # Long position: look for exit
                if close.iloc[i] < lower_channel.iloc[i-1]:
                    signal.iloc[i] = 0
                    position = 0
                else:
                    signal.iloc[i] = 1
            elif position == -1:
                # Short position: look for exit
                if close.iloc[i] > upper_channel.iloc[i-1]:
                    signal.iloc[i] = 0
                    position = 0
                else:
                    signal.iloc[i] = -1

        signals['signal'] = signal
        signals['upper_channel'] = upper_channel
        signals['lower_channel'] = lower_channel
        signals['atr'] = atr
        signals['stop_loss'] = close - self.atr_multiplier * atr

        return signals
