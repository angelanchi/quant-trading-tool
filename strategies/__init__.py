# -*- coding: utf-8 -*-
"""
Trading strategies module.

This module contains various trading strategy implementations:
- base: Base strategy class and Signal/StrategyResult data classes
- mean_reversion: Mean reversion and Bollinger Band strategies
- pairs_trading: Statistical arbitrage pairs trading strategy
- momentum: Momentum and trend following strategies
- registry: Strategy registration and factory
"""

from .base import BaseStrategy, Signal, StrategyResult
from .mean_reversion import MeanReversionStrategy, BollingerBandStrategy
from .pairs_trading import PairsTradingStrategy
from .momentum import (
    MomentumStrategy,
    TrendFollowingStrategy,
    DualMomentumStrategy,
    BreakoutStrategy,
)
from .registry import (
    StrategyRegistry,
    StrategyRunner,
    StrategyInfo,
)

__all__ = [
    # Base
    'BaseStrategy',
    'Signal',
    'StrategyResult',
    # Mean Reversion
    'MeanReversionStrategy',
    'BollingerBandStrategy',
    # Pairs Trading
    'PairsTradingStrategy',
    # Momentum
    'MomentumStrategy',
    'TrendFollowingStrategy',
    'DualMomentumStrategy',
    'BreakoutStrategy',
    # Registry
    'StrategyRegistry',
    'StrategyRunner',
    'StrategyInfo',
]
