# -*- coding: utf-8 -*-
"""
Base strategy class for trading strategies.

This module provides the abstract base class that all trading strategies
should inherit from.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np


@dataclass
class Signal:
    """Trading signal data class."""
    timestamp: pd.Timestamp
    symbol: str
    action: str  # 'BUY', 'SELL', 'HOLD'
    quantity: float
    price: float
    confidence: float = 1.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class StrategyResult:
    """Strategy execution result."""
    signals: pd.DataFrame
    entries: pd.Series
    exits: pd.Series
    positions: pd.Series
    returns: pd.Series
    metadata: Dict[str, Any] = None


class BaseStrategy(ABC):
    """
    Abstract base class for trading strategies.

    All custom strategies should inherit from this class and implement
    the required abstract methods.

    Attributes:
        name: Strategy name
        parameters: Strategy parameters dictionary
    """

    def __init__(self, name: str = "BaseStrategy", **kwargs):
        """
        Initialize the strategy.

        Args:
            name: Strategy name
            **kwargs: Strategy-specific parameters
        """
        self.name = name
        self.parameters = kwargs
        self._fitted = False

    @abstractmethod
    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals based on price data.

        Args:
            prices: DataFrame with OHLCV data or close prices

        Returns:
            DataFrame with signal columns (-1: short, 0: neutral, 1: long)
        """
        pass

    def fit(self, prices: pd.DataFrame) -> 'BaseStrategy':
        """
        Fit the strategy to historical data (optional).

        Some strategies may need to estimate parameters from data.

        Args:
            prices: Historical price data

        Returns:
            Self for method chaining
        """
        self._fitted = True
        return self

    def get_entry_signals(self, signals: pd.DataFrame) -> pd.DataFrame:
        """
        Extract entry signals from signal DataFrame.

        Args:
            signals: Signal DataFrame

        Returns:
            DataFrame with entry signals (True where entering position)
        """
        # Entry when signal changes from 0 to non-zero
        return signals.diff().abs() > 0

    def get_exit_signals(self, signals: pd.DataFrame) -> pd.DataFrame:
        """
        Extract exit signals from signal DataFrame.

        Args:
            signals: Signal DataFrame

        Returns:
            DataFrame with exit signals (True where exiting position)
        """
        # Exit when signal changes to 0 from non-zero
        prev_signals = signals.shift(1)
        return (signals == 0) & (prev_signals != 0)

    def backtest(
        self,
        prices: pd.DataFrame,
        initial_capital: float = 100000,
        commission: float = 0.001,
        slippage: float = 0.0005
    ) -> StrategyResult:
        """
        Run a simple backtest of the strategy.

        Args:
            prices: Price data
            initial_capital: Starting capital
            commission: Commission rate per trade
            slippage: Slippage rate per trade

        Returns:
            StrategyResult with backtest results
        """
        signals = self.generate_signals(prices)

        # Calculate position sizes (simple: all-in or all-out)
        positions = signals.copy()

        # Get close prices for return calculation
        if isinstance(prices, pd.DataFrame):
            if 'close' in prices.columns:
                close = prices['close']
            else:
                close = prices.iloc[:, 0]  # Use first column
        else:
            close = prices

        # Calculate returns
        price_returns = close.pct_change()

        # Strategy returns = position * price return
        if isinstance(positions, pd.DataFrame):
            strategy_returns = (positions.shift(1) * price_returns).mean(axis=1)
        else:
            strategy_returns = positions.shift(1) * price_returns

        # Apply transaction costs
        trades = positions.diff().abs()
        if isinstance(trades, pd.DataFrame):
            trade_costs = trades.sum(axis=1) * (commission + slippage)
        else:
            trade_costs = trades * (commission + slippage)

        net_returns = strategy_returns - trade_costs

        return StrategyResult(
            signals=signals,
            entries=self.get_entry_signals(signals),
            exits=self.get_exit_signals(signals),
            positions=positions,
            returns=net_returns,
            metadata={
                'initial_capital': initial_capital,
                'commission': commission,
                'slippage': slippage
            }
        )

    def __repr__(self) -> str:
        params_str = ", ".join(f"{k}={v}" for k, v in self.parameters.items())
        return f"{self.name}({params_str})"
