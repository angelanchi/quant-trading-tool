# -*- coding: utf-8 -*-
"""
Walk-forward optimization example.

Demonstrates:
- Walk-forward analysis for robust parameter optimization
- Rolling optimization for adaptive strategies
- Avoiding overfitting through out-of-sample testing

Usage:
    python examples/walk_forward_example.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np


def generate_sample_data():
    """Generate sample data for walk-forward analysis."""
    from scripts.generate_sample_data import generate_correlated_assets

    symbols = ['AAPL', 'MSFT']
    prices_df = generate_correlated_assets(symbols, n_days=756, seed=42)  # 3 years
    dates = pd.date_range(start='2021-01-01', periods=756, freq='B')
    prices_df.index = dates

    return prices_df


def example_basic_walk_forward():
    """Example: Basic walk-forward optimization."""
    print("\n" + "=" * 60)
    print("Example 1: Basic Walk-Forward Optimization")
    print("=" * 60)

    from core import BacktestEngine, WalkForwardOptimizer

    # Generate data
    prices_df = generate_sample_data()
    print(f"\nData: {len(prices_df)} days from {prices_df.index[0].date()} to {prices_df.index[-1].date()}")

    # Create strategy function
    engine = BacktestEngine()

    def strategy_func(data, lookback=20, entry_zscore=2.0):
        return engine.run_mean_reversion(
            data,
            lookback=lookback,
            entry_zscore=entry_zscore,
            exit_zscore=0.5,
            initial_capital=100000
        )

    # Define parameter grid
    param_grid = {
        'lookback': [10, 15, 20, 25, 30],
        'entry_zscore': [1.5, 2.0, 2.5]
    }

    print(f"\nParameter Grid:")
    for param, values in param_grid.items():
        print(f"  {param}: {values}")

    # Run walk-forward optimization
    print("\nRunning walk-forward optimization...")

    optimizer = WalkForwardOptimizer(
        train_period=252,  # 1 year training
        test_period=63,    # 3 months testing
        step_size=63       # Move forward 3 months each time
    )

    result = optimizer.run(
        prices_df,
        param_grid,
        strategy_func,
        metric='sharpe_ratio'
    )

    # Print results
    print(f"\n{'='*50}")
    print("WALK-FORWARD RESULTS")
    print(f"{'='*50}")
    print(f"\nNumber of Windows: {len(result.windows)}")
    print(f"Combined Test Return: {result.combined_test_return:.2%}")
    print(f"Combined Test Sharpe: {result.combined_test_sharpe:.2f}")
    print(f"Overfitting Ratio: {result.overfitting_ratio:.2f}")
    print("  (Closer to 1.0 = less overfitting)")

    print(f"\n--- Window Details ---")
    print(f"{'Window':<8} {'Train Sharpe':<14} {'Test Sharpe':<12} {'Test Return':<12} {'Best Lookback'}")
    print("-" * 65)

    for w in result.windows:
        lookback = w.best_params.get('lookback', 'N/A') if w.best_params else 'N/A'
        print(f"{w.window_id:<8} {w.train_metric:<14.2f} {w.test_metric:<12.2f} {w.test_return:<12.2%} {lookback}")

    print(f"\n--- Parameter Stability ---")
    for param, stability in result.parameter_stability.items():
        print(f"  {param}: {stability:.4f} (lower = more stable)")


def example_rolling_optimization():
    """Example: Rolling window optimization."""
    print("\n" + "=" * 60)
    print("Example 2: Rolling Optimization")
    print("=" * 60)

    from core import BacktestEngine, RollingOptimizer

    # Generate data
    prices_df = generate_sample_data()

    engine = BacktestEngine()

    def strategy_func(data, lookback=20):
        return engine.run_mean_reversion(
            data,
            lookback=lookback,
            entry_zscore=2.0,
            initial_capital=100000
        )

    param_grid = {
        'lookback': [10, 15, 20, 25, 30, 35, 40]
    }

    print("\nRunning rolling optimization...")
    print("(Re-optimizing every 21 days using past 252 days)")

    optimizer = RollingOptimizer(
        lookback=252,           # Use 1 year of history
        reoptimize_frequency=21 # Re-optimize monthly
    )

    results = optimizer.run(
        prices_df,
        param_grid,
        strategy_func,
        metric='sharpe_ratio'
    )

    print(f"\n--- Rolling Optimization Results ---")
    print(f"Total optimization points: {len(results)}")

    if len(results) > 0:
        print(f"\nOptimal lookback over time:")
        print(results[['date', 'lookback', 'metric']].to_string(index=False))

        # Analyze parameter changes
        lookback_values = results['lookback'].values
        print(f"\n--- Parameter Analysis ---")
        print(f"  Most common lookback: {pd.Series(lookback_values).mode().iloc[0]}")
        print(f"  Lookback std dev: {np.std(lookback_values):.2f}")
        print(f"  Number of changes: {(np.diff(lookback_values) != 0).sum()}")


def example_compare_optimization():
    """Example: Compare standard vs walk-forward optimization."""
    print("\n" + "=" * 60)
    print("Example 3: Standard vs Walk-Forward Comparison")
    print("=" * 60)

    from core import BacktestEngine, WalkForwardOptimizer

    prices_df = generate_sample_data()
    engine = BacktestEngine()

    # Split data
    train_end = int(len(prices_df) * 0.7)
    train_data = prices_df.iloc[:train_end]
    test_data = prices_df.iloc[train_end:]

    print(f"\nData split:")
    print(f"  Training: {len(train_data)} days")
    print(f"  Testing: {len(test_data)} days")

    def strategy_func(data, lookback=20, entry_zscore=2.0):
        return engine.run_mean_reversion(
            data,
            lookback=lookback,
            entry_zscore=entry_zscore,
            initial_capital=100000
        )

    param_grid = {
        'lookback': [10, 15, 20, 25, 30],
        'entry_zscore': [1.5, 2.0, 2.5]
    }

    # Method 1: Standard optimization (optimize on all training data)
    print("\n--- Method 1: Standard Optimization ---")
    print("(Optimize once on training data, test on holdout)")

    from itertools import product
    best_params = None
    best_sharpe = -np.inf

    for lookback in param_grid['lookback']:
        for entry_z in param_grid['entry_zscore']:
            result = strategy_func(train_data, lookback, entry_z)
            if result.sharpe_ratio > best_sharpe:
                best_sharpe = result.sharpe_ratio
                best_params = {'lookback': lookback, 'entry_zscore': entry_z}

    print(f"  Best params: {best_params}")
    print(f"  Train Sharpe: {best_sharpe:.2f}")

    # Test on holdout
    test_result = strategy_func(test_data, **best_params)
    print(f"  Test Sharpe: {test_result.sharpe_ratio:.2f}")
    print(f"  Test Return: {test_result.total_return:.2%}")

    standard_test_sharpe = test_result.sharpe_ratio
    standard_test_return = test_result.total_return

    # Method 2: Walk-forward optimization
    print("\n--- Method 2: Walk-Forward Optimization ---")
    print("(Multiple train/test windows)")

    optimizer = WalkForwardOptimizer(
        train_period=252,
        test_period=63,
        step_size=63
    )

    wf_result = optimizer.run(prices_df, param_grid, strategy_func, 'sharpe_ratio')

    print(f"  Combined Test Sharpe: {wf_result.combined_test_sharpe:.2f}")
    print(f"  Combined Test Return: {wf_result.combined_test_return:.2%}")
    print(f"  Overfitting Ratio: {wf_result.overfitting_ratio:.2f}")

    # Comparison
    print("\n--- Comparison Summary ---")
    print(f"{'Method':<25} {'Test Sharpe':<15} {'Test Return':<15}")
    print("-" * 55)
    print(f"{'Standard Optimization':<25} {standard_test_sharpe:<15.2f} {standard_test_return:<15.2%}")
    print(f"{'Walk-Forward':<25} {wf_result.combined_test_sharpe:<15.2f} {wf_result.combined_test_return:<15.2%}")

    if wf_result.overfitting_ratio < 0.7:
        print("\nWarning: Low overfitting ratio suggests potential overfit in training.")
    elif wf_result.overfitting_ratio > 0.9:
        print("\nGood: High overfitting ratio suggests robust parameters.")


def example_parameter_stability():
    """Example: Analyze parameter stability."""
    print("\n" + "=" * 60)
    print("Example 4: Parameter Stability Analysis")
    print("=" * 60)

    from core import BacktestEngine, WalkForwardOptimizer

    prices_df = generate_sample_data()
    engine = BacktestEngine()

    def strategy_func(data, lookback=20, entry_zscore=2.0, exit_zscore=0.5):
        return engine.run_mean_reversion(
            data,
            lookback=lookback,
            entry_zscore=entry_zscore,
            exit_zscore=exit_zscore,
            initial_capital=100000
        )

    param_grid = {
        'lookback': [10, 15, 20, 25, 30],
        'entry_zscore': [1.5, 2.0, 2.5, 3.0],
        'exit_zscore': [0.0, 0.25, 0.5, 0.75]
    }

    print("\nRunning walk-forward with multiple parameters...")

    optimizer = WalkForwardOptimizer(
        train_period=252,
        test_period=63,
        step_size=63
    )

    result = optimizer.run(prices_df, param_grid, strategy_func, 'sharpe_ratio')

    print(f"\n--- Parameter Stability Analysis ---")
    print("(Lower stability value = more consistent across windows)")

    for param, stability in sorted(result.parameter_stability.items(), key=lambda x: x[1]):
        bar = "*" * int(stability * 50)
        print(f"  {param:<15} {stability:.4f} {bar}")

    # Show best params per window
    print(f"\n--- Best Parameters Per Window ---")
    for w in result.windows:
        if w.best_params:
            params_str = ", ".join(f"{k}={v}" for k, v in w.best_params.items())
            print(f"  Window {w.window_id}: {params_str}")


def main():
    """Run all walk-forward examples."""
    print("\n" + "#" * 60)
    print("# Quantitative Trading Tool - Walk-Forward Optimization")
    print("#" * 60)

    # Example 1: Basic walk-forward
    example_basic_walk_forward()

    # Example 2: Rolling optimization
    example_rolling_optimization()

    # Example 3: Compare methods
    example_compare_optimization()

    # Example 4: Parameter stability
    example_parameter_stability()

    print("\n" + "#" * 60)
    print("# Walk-forward examples completed!")
    print("#" * 60)


if __name__ == "__main__":
    main()
