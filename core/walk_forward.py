# -*- coding: utf-8 -*-
"""
Walk-forward optimization module.

Implements walk-forward analysis for robust strategy parameter optimization.
Avoids overfitting by testing out-of-sample performance.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Callable, Any, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardWindow:
    """A single walk-forward window."""
    window_id: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    best_params: Dict[str, Any] = None
    train_metric: float = None
    test_metric: float = None
    test_return: float = None


@dataclass
class WalkForwardResult:
    """Results from walk-forward optimization."""
    windows: List[WalkForwardWindow]
    combined_test_return: float
    combined_test_sharpe: float
    avg_train_metric: float
    avg_test_metric: float
    parameter_stability: Dict[str, float]  # Std of best params across windows
    overfitting_ratio: float  # test_metric / train_metric

    def summary(self) -> str:
        """Generate summary string."""
        lines = [
            "Walk-Forward Optimization Results",
            "=" * 40,
            f"Number of Windows: {len(self.windows)}",
            f"Combined Test Return: {self.combined_test_return:.2%}",
            f"Combined Test Sharpe: {self.combined_test_sharpe:.2f}",
            f"Avg Train Metric: {self.avg_train_metric:.4f}",
            f"Avg Test Metric: {self.avg_test_metric:.4f}",
            f"Overfitting Ratio: {self.overfitting_ratio:.2f}",
            "",
            "Parameter Stability (lower = more stable):",
        ]

        for param, std in self.parameter_stability.items():
            lines.append(f"  {param}: {std:.4f}")

        return "\n".join(lines)


class WalkForwardOptimizer:
    """
    Walk-forward optimization for trading strategies.

    Walk-forward analysis splits data into multiple train/test windows,
    optimizes parameters on training data, and validates on test data.
    This helps identify robust parameters that generalize well.

    Window structure:
    |----Train 1----|--Test 1--|
              |----Train 2----|--Test 2--|
                        |----Train 3----|--Test 3--|
    """

    def __init__(
        self,
        train_period: int = 252,  # Training period in days
        test_period: int = 63,    # Test period in days
        step_size: int = 63,      # Step between windows
        min_train_samples: int = 100
    ):
        """
        Initialize walk-forward optimizer.

        Args:
            train_period: Number of days for training
            test_period: Number of days for testing
            step_size: Days to advance between windows
            min_train_samples: Minimum samples required for training
        """
        self.train_period = train_period
        self.test_period = test_period
        self.step_size = step_size
        self.min_train_samples = min_train_samples

    def generate_windows(
        self,
        data: pd.DataFrame
    ) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
        """
        Generate train/test window pairs.

        Args:
            data: Full price DataFrame

        Returns:
            List of (train_data, test_data) tuples
        """
        windows = []
        n_samples = len(data)

        start_idx = 0

        while start_idx + self.train_period + self.test_period <= n_samples:
            train_end_idx = start_idx + self.train_period
            test_end_idx = train_end_idx + self.test_period

            train_data = data.iloc[start_idx:train_end_idx]
            test_data = data.iloc[train_end_idx:test_end_idx]

            if len(train_data) >= self.min_train_samples:
                windows.append((train_data, test_data))

            start_idx += self.step_size

        logger.info(f"Generated {len(windows)} walk-forward windows")
        return windows

    def optimize_window(
        self,
        train_data: pd.DataFrame,
        param_grid: Dict[str, List],
        strategy_func: Callable,
        metric: str = 'sharpe_ratio'
    ) -> Tuple[Dict[str, Any], float]:
        """
        Find optimal parameters for a single training window.

        Args:
            train_data: Training price data
            param_grid: Parameter grid to search
            strategy_func: Function(data, **params) -> result with metric attribute
            metric: Optimization metric

        Returns:
            (best_params, best_metric)
        """
        from itertools import product

        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        combinations = list(product(*param_values))

        best_params = None
        best_metric = -np.inf

        for combo in combinations:
            params = dict(zip(param_names, combo))

            try:
                result = strategy_func(train_data, **params)
                metric_value = getattr(result, metric, None)

                if metric_value is not None and metric_value > best_metric:
                    best_metric = metric_value
                    best_params = params.copy()

            except Exception as e:
                logger.debug(f"Error with params {params}: {e}")
                continue

        return best_params, best_metric

    def run(
        self,
        data: pd.DataFrame,
        param_grid: Dict[str, List],
        strategy_func: Callable,
        metric: str = 'sharpe_ratio'
    ) -> WalkForwardResult:
        """
        Run walk-forward optimization.

        Args:
            data: Full price DataFrame
            param_grid: Parameter grid to search
            strategy_func: Strategy function
            metric: Optimization metric

        Returns:
            WalkForwardResult with all window results
        """
        windows = self.generate_windows(data)

        if not windows:
            raise ValueError("Not enough data for walk-forward analysis")

        results = []
        all_test_returns = []
        all_best_params = []

        for i, (train_data, test_data) in enumerate(windows):
            logger.info(f"Processing window {i+1}/{len(windows)}")

            # Optimize on training data
            best_params, train_metric = self.optimize_window(
                train_data, param_grid, strategy_func, metric
            )

            if best_params is None:
                logger.warning(f"No valid parameters found for window {i+1}")
                continue

            # Test on out-of-sample data
            try:
                test_result = strategy_func(test_data, **best_params)
                test_metric = getattr(test_result, metric, 0)
                test_return = getattr(test_result, 'total_return', 0)
            except Exception as e:
                logger.warning(f"Test failed for window {i+1}: {e}")
                test_metric = 0
                test_return = 0

            window_result = WalkForwardWindow(
                window_id=i,
                train_start=train_data.index[0],
                train_end=train_data.index[-1],
                test_start=test_data.index[0],
                test_end=test_data.index[-1],
                best_params=best_params,
                train_metric=train_metric,
                test_metric=test_metric,
                test_return=test_return
            )

            results.append(window_result)
            all_test_returns.append(test_return)
            all_best_params.append(best_params)

        # Calculate combined metrics
        combined_return = np.prod([1 + r for r in all_test_returns]) - 1
        combined_sharpe = self._calculate_combined_sharpe(all_test_returns, len(windows))

        # Calculate parameter stability
        param_stability = self._calculate_param_stability(all_best_params, param_grid)

        # Calculate overfitting ratio
        avg_train = np.mean([w.train_metric for w in results if w.train_metric])
        avg_test = np.mean([w.test_metric for w in results if w.test_metric])
        overfitting_ratio = avg_test / avg_train if avg_train != 0 else 0

        return WalkForwardResult(
            windows=results,
            combined_test_return=combined_return,
            combined_test_sharpe=combined_sharpe,
            avg_train_metric=avg_train,
            avg_test_metric=avg_test,
            parameter_stability=param_stability,
            overfitting_ratio=overfitting_ratio
        )

    def _calculate_combined_sharpe(
        self,
        returns: List[float],
        n_windows: int
    ) -> float:
        """Calculate approximate Sharpe ratio from window returns."""
        if not returns:
            return 0.0

        mean_return = np.mean(returns)
        std_return = np.std(returns) if len(returns) > 1 else 0.0001

        # Annualize based on window frequency
        periods_per_year = 252 / self.test_period
        annual_return = mean_return * periods_per_year
        annual_std = std_return * np.sqrt(periods_per_year)

        return annual_return / annual_std if annual_std > 0 else 0.0

    def _calculate_param_stability(
        self,
        all_params: List[Dict],
        param_grid: Dict[str, List]
    ) -> Dict[str, float]:
        """Calculate standard deviation of parameters across windows."""
        stability = {}

        for param_name in param_grid.keys():
            values = [p.get(param_name) for p in all_params if p]
            if values and all(isinstance(v, (int, float)) for v in values):
                # Normalize by parameter range
                param_range = max(param_grid[param_name]) - min(param_grid[param_name])
                if param_range > 0:
                    stability[param_name] = np.std(values) / param_range
                else:
                    stability[param_name] = 0.0

        return stability


class RollingOptimizer:
    """
    Rolling window optimization.

    Re-optimizes parameters at regular intervals using recent data.
    Useful for adapting to changing market conditions.
    """

    def __init__(
        self,
        lookback: int = 252,
        reoptimize_frequency: int = 21  # Monthly
    ):
        """
        Initialize rolling optimizer.

        Args:
            lookback: Days of history for optimization
            reoptimize_frequency: Days between re-optimization
        """
        self.lookback = lookback
        self.reoptimize_frequency = reoptimize_frequency

    def run(
        self,
        data: pd.DataFrame,
        param_grid: Dict[str, List],
        strategy_func: Callable,
        metric: str = 'sharpe_ratio'
    ) -> pd.DataFrame:
        """
        Run rolling optimization.

        Args:
            data: Full price DataFrame
            param_grid: Parameter grid
            strategy_func: Strategy function
            metric: Optimization metric

        Returns:
            DataFrame with dates and optimal parameters
        """
        from itertools import product

        results = []
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        combinations = list(product(*param_values))

        n_samples = len(data)
        current_idx = self.lookback

        while current_idx < n_samples:
            # Get lookback window
            train_data = data.iloc[current_idx - self.lookback:current_idx]
            current_date = data.index[current_idx]

            # Find best params
            best_params = None
            best_metric = -np.inf

            for combo in combinations:
                params = dict(zip(param_names, combo))
                try:
                    result = strategy_func(train_data, **params)
                    metric_value = getattr(result, metric, None)
                    if metric_value and metric_value > best_metric:
                        best_metric = metric_value
                        best_params = params.copy()
                except:
                    continue

            if best_params:
                result_row = {'date': current_date, 'metric': best_metric}
                result_row.update(best_params)
                results.append(result_row)

            current_idx += self.reoptimize_frequency

        return pd.DataFrame(results)


def walk_forward_analyze(
    prices: pd.DataFrame,
    strategy_func: Callable,
    param_grid: Dict[str, List],
    train_period: int = 252,
    test_period: int = 63,
    metric: str = 'sharpe_ratio'
) -> WalkForwardResult:
    """
    Convenience function for walk-forward analysis.

    Args:
        prices: Price DataFrame
        strategy_func: Strategy function(prices, **params) -> result
        param_grid: Parameter grid to optimize
        train_period: Training period days
        test_period: Test period days
        metric: Optimization metric

    Returns:
        WalkForwardResult
    """
    optimizer = WalkForwardOptimizer(
        train_period=train_period,
        test_period=test_period
    )

    return optimizer.run(prices, param_grid, strategy_func, metric)
