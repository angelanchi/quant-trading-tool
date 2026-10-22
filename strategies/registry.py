# -*- coding: utf-8 -*-
"""
Strategy registry and factory.

Provides centralized management of trading strategies with:
- Registration and discovery
- Parameter validation
- Strategy comparison
- Batch execution
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Type, Any, Callable
from dataclasses import dataclass, field
import inspect
import logging

from .base import BaseStrategy, StrategyResult

logger = logging.getLogger(__name__)


@dataclass
class StrategyInfo:
    """Information about a registered strategy."""
    name: str
    cls: Type[BaseStrategy]
    category: str
    description: str
    parameters: Dict[str, Dict[str, Any]]
    author: str = "System"
    version: str = "1.0"
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'category': self.category,
            'description': self.description,
            'parameters': self.parameters,
            'author': self.author,
            'version': self.version,
            'tags': self.tags
        }


class StrategyRegistry:
    """
    Central registry for trading strategies.

    Features:
    - Register strategies with metadata
    - Create strategy instances with validated parameters
    - List and filter strategies by category/tags
    - Run multiple strategies for comparison
    """

    _instance = None
    _strategies: Dict[str, StrategyInfo] = {}

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(
        cls,
        name: str = None,
        category: str = "general",
        description: str = "",
        author: str = "System",
        version: str = "1.0",
        tags: List[str] = None
    ) -> Callable:
        """
        Decorator to register a strategy class.

        Usage:
            @StrategyRegistry.register(
                name="MyStrategy",
                category="momentum",
                description="My custom strategy"
            )
            class MyStrategy(BaseStrategy):
                ...
        """
        def decorator(strategy_cls: Type[BaseStrategy]) -> Type[BaseStrategy]:
            strategy_name = name or strategy_cls.__name__

            # Extract parameters from __init__
            sig = inspect.signature(strategy_cls.__init__)
            parameters = {}

            for param_name, param in sig.parameters.items():
                if param_name in ('self', 'kwargs'):
                    continue

                param_info = {
                    'type': str(param.annotation) if param.annotation != inspect.Parameter.empty else 'any',
                    'default': param.default if param.default != inspect.Parameter.empty else None,
                    'required': param.default == inspect.Parameter.empty
                }
                parameters[param_name] = param_info

            info = StrategyInfo(
                name=strategy_name,
                cls=strategy_cls,
                category=category,
                description=description or strategy_cls.__doc__ or "",
                parameters=parameters,
                author=author,
                version=version,
                tags=tags or []
            )

            cls._strategies[strategy_name] = info
            logger.info(f"Registered strategy: {strategy_name}")

            return strategy_cls

        return decorator

    @classmethod
    def get(cls, name: str) -> Optional[StrategyInfo]:
        """Get strategy info by name."""
        return cls._strategies.get(name)

    @classmethod
    def create(cls, name: str, **kwargs) -> Optional[BaseStrategy]:
        """
        Create a strategy instance.

        Args:
            name: Strategy name
            **kwargs: Strategy parameters

        Returns:
            Strategy instance or None if not found
        """
        info = cls.get(name)
        if info is None:
            logger.error(f"Strategy not found: {name}")
            return None

        try:
            return info.cls(**kwargs)
        except Exception as e:
            logger.error(f"Error creating strategy {name}: {e}")
            return None

    @classmethod
    def list_all(cls) -> List[StrategyInfo]:
        """List all registered strategies."""
        return list(cls._strategies.values())

    @classmethod
    def list_by_category(cls, category: str) -> List[StrategyInfo]:
        """List strategies by category."""
        return [s for s in cls._strategies.values() if s.category == category]

    @classmethod
    def list_by_tag(cls, tag: str) -> List[StrategyInfo]:
        """List strategies by tag."""
        return [s for s in cls._strategies.values() if tag in s.tags]

    @classmethod
    def get_categories(cls) -> List[str]:
        """Get all unique categories."""
        return list(set(s.category for s in cls._strategies.values()))

    @classmethod
    def get_tags(cls) -> List[str]:
        """Get all unique tags."""
        tags = set()
        for s in cls._strategies.values():
            tags.update(s.tags)
        return list(tags)

    @classmethod
    def search(cls, query: str) -> List[StrategyInfo]:
        """Search strategies by name or description."""
        query = query.lower()
        results = []
        for info in cls._strategies.values():
            if query in info.name.lower() or query in info.description.lower():
                results.append(info)
        return results


class StrategyRunner:
    """
    Run and compare multiple strategies.

    Features:
    - Run single strategy
    - Run multiple strategies in parallel
    - Compare strategy performance
    - Parameter optimization
    """

    def __init__(self, registry: StrategyRegistry = None):
        self.registry = registry or StrategyRegistry()
        self.results: Dict[str, StrategyResult] = {}

    def run_strategy(
        self,
        strategy_name: str,
        prices: pd.DataFrame,
        **kwargs
    ) -> Optional[StrategyResult]:
        """
        Run a single strategy.

        Args:
            strategy_name: Name of registered strategy
            prices: Price data
            **kwargs: Strategy parameters

        Returns:
            StrategyResult or None
        """
        strategy = self.registry.create(strategy_name, **kwargs)
        if strategy is None:
            return None

        try:
            signals = strategy.generate_signals(prices)
            result = strategy.backtest(prices)
            self.results[strategy_name] = result
            return result
        except Exception as e:
            logger.error(f"Error running {strategy_name}: {e}")
            return None

    def run_multiple(
        self,
        strategy_configs: List[Dict],
        prices: pd.DataFrame
    ) -> Dict[str, StrategyResult]:
        """
        Run multiple strategies.

        Args:
            strategy_configs: List of {'name': str, 'params': dict}
            prices: Price data

        Returns:
            Dictionary of results keyed by strategy name
        """
        results = {}

        for config in strategy_configs:
            name = config['name']
            params = config.get('params', {})
            label = config.get('label', name)

            result = self.run_strategy(name, prices, **params)
            if result:
                results[label] = result

        self.results.update(results)
        return results

    def compare(
        self,
        metric: str = 'sharpe_ratio'
    ) -> pd.DataFrame:
        """
        Compare strategy results.

        Args:
            metric: Primary sorting metric

        Returns:
            DataFrame with strategy comparison
        """
        if not self.results:
            return pd.DataFrame()

        data = []
        for name, result in self.results.items():
            data.append({
                'Strategy': name,
                'Total Return': result.total_return,
                'CAGR': result.cagr,
                'Sharpe Ratio': result.sharpe_ratio,
                'Sortino Ratio': result.sortino_ratio,
                'Max Drawdown': result.max_drawdown,
                'Win Rate': result.win_rate,
                'Total Trades': result.total_trades
            })

        df = pd.DataFrame(data)
        if metric in df.columns:
            df = df.sort_values(metric, ascending=False)

        return df

    def get_best(self, metric: str = 'sharpe_ratio') -> Optional[str]:
        """Get the best performing strategy by metric."""
        comparison = self.compare(metric)
        if comparison.empty:
            return None
        return comparison.iloc[0]['Strategy']

    def parameter_grid_search(
        self,
        strategy_name: str,
        prices: pd.DataFrame,
        param_grid: Dict[str, List],
        metric: str = 'sharpe_ratio'
    ) -> pd.DataFrame:
        """
        Grid search for optimal parameters.

        Args:
            strategy_name: Strategy name
            prices: Price data
            param_grid: Dictionary of parameter lists
            metric: Optimization metric

        Returns:
            DataFrame with parameter combinations and results
        """
        from itertools import product

        # Generate all combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        combinations = list(product(*param_values))

        results = []

        for combo in combinations:
            params = dict(zip(param_names, combo))

            result = self.run_strategy(strategy_name, prices, **params)
            if result:
                row = params.copy()
                row['total_return'] = result.total_return
                row['sharpe_ratio'] = result.sharpe_ratio
                row['max_drawdown'] = result.max_drawdown
                row['win_rate'] = result.win_rate
                results.append(row)

        df = pd.DataFrame(results)
        if metric in df.columns:
            df = df.sort_values(metric, ascending=False)

        return df


# Register built-in strategies
def register_builtin_strategies():
    """Register all built-in strategies."""
    from .mean_reversion import MeanReversionStrategy, BollingerBandStrategy
    from .pairs_trading import PairsTradingStrategy
    from .momentum import (
        MomentumStrategy,
        TrendFollowingStrategy,
        DualMomentumStrategy,
        BreakoutStrategy
    )

    # Mean Reversion
    StrategyRegistry.register(
        name="MeanReversion",
        category="mean_reversion",
        description="Z-score based mean reversion strategy",
        tags=["statistical", "short-term"]
    )(MeanReversionStrategy)

    StrategyRegistry.register(
        name="BollingerBands",
        category="mean_reversion",
        description="Bollinger Bands based strategy",
        tags=["technical", "volatility"]
    )(BollingerBandStrategy)

    # Pairs Trading
    StrategyRegistry.register(
        name="PairsTrading",
        category="statistical_arbitrage",
        description="Cointegration-based pairs trading",
        tags=["statistical", "market-neutral"]
    )(PairsTradingStrategy)

    # Momentum
    StrategyRegistry.register(
        name="Momentum",
        category="momentum",
        description="Classic momentum with MA filter",
        tags=["trend", "technical"]
    )(MomentumStrategy)

    StrategyRegistry.register(
        name="TrendFollowing",
        category="momentum",
        description="Trend following with ADX confirmation",
        tags=["trend", "technical"]
    )(TrendFollowingStrategy)

    StrategyRegistry.register(
        name="DualMomentum",
        category="momentum",
        description="Absolute + relative momentum",
        tags=["momentum", "cross-sectional"]
    )(DualMomentumStrategy)

    StrategyRegistry.register(
        name="Breakout",
        category="momentum",
        description="Donchian channel breakout",
        tags=["trend", "volatility"]
    )(BreakoutStrategy)

    logger.info("Registered built-in strategies")


# Auto-register on import
try:
    register_builtin_strategies()
except Exception as e:
    logger.warning(f"Could not register built-in strategies: {e}")
