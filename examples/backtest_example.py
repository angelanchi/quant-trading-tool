# -*- coding: utf-8 -*-
"""
Backtesting example for quantitative trading tool.

Demonstrates:
- Running mean reversion strategy
- Running MA crossover strategy
- Comparing multiple strategies
- Analyzing backtest results

Usage:
    python examples/backtest_example.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np


def fetch_sample_data():
    """Fetch sample data for backtesting."""
    from core import DataManager

    dm = DataManager()
    symbols = ['AAPL', 'MSFT']

    print("Fetching price data...")
    prices = {}

    for symbol in symbols:
        try:
            df = dm.fetch_ohlcv(symbol, '2022-01-01', '2023-12-31')
            if df is not None and not df.empty:
                prices[symbol] = df['close']
                print(f"  {symbol}: {len(df)} records")
        except Exception as e:
            print(f"  {symbol}: Error - {e}")

    if not prices:
        print("No data available, using synthetic data for demonstration")
        # Generate synthetic data
        np.random.seed(42)
        dates = pd.date_range(start='2022-01-01', end='2023-12-31', freq='B')
        for symbol in symbols:
            returns = np.random.normal(0.0005, 0.02, len(dates))
            price = 100 * np.exp(np.cumsum(returns))
            prices[symbol] = pd.Series(price, index=dates, name=symbol)

    prices_df = pd.DataFrame(prices)
    return prices_df.dropna()


def example_mean_reversion(prices_df):
    """Example: Mean reversion strategy backtest."""
    print("\n" + "=" * 60)
    print("Example 1: Mean Reversion Strategy")
    print("=" * 60)

    from core import BacktestEngine

    engine = BacktestEngine()

    # Strategy parameters
    params = {
        'lookback': 20,
        'entry_zscore': 2.0,
        'exit_zscore': 0.5,
        'initial_capital': 100000,
        'commission_pct': 0.001,
        'slippage_pct': 0.0005
    }

    print(f"\nParameters:")
    for key, value in params.items():
        print(f"  {key}: {value}")

    # Run backtest
    print("\nRunning backtest...")
    try:
        result = engine.run_mean_reversion(
            prices_df,
            lookback=params['lookback'],
            entry_zscore=params['entry_zscore'],
            exit_zscore=params['exit_zscore'],
            initial_capital=params['initial_capital'],
            commission_pct=params['commission_pct'],
            slippage_pct=params['slippage_pct']
        )

        print("\n--- Results ---")
        print(f"Total Return:   {result.total_return:>10.2%}")
        print(f"CAGR:           {result.cagr:>10.2%}")
        print(f"Sharpe Ratio:   {result.sharpe_ratio:>10.2f}")
        print(f"Sortino Ratio:  {result.sortino_ratio:>10.2f}")
        print(f"Max Drawdown:   {result.max_drawdown:>10.2%}")
        print(f"Total Trades:   {result.total_trades:>10}")
        print(f"Win Rate:       {result.win_rate:>10.2%}")
        print(f"Profit Factor:  {result.profit_factor:>10.2f}")

        return result

    except Exception as e:
        print(f"Error: {e}")
        return None


def example_ma_crossover(prices_df):
    """Example: Moving average crossover strategy backtest."""
    print("\n" + "=" * 60)
    print("Example 2: MA Crossover Strategy")
    print("=" * 60)

    from core import BacktestEngine

    engine = BacktestEngine()

    # Strategy parameters
    params = {
        'fast_period': 10,
        'slow_period': 30,
        'initial_capital': 100000,
        'commission_pct': 0.001,
        'slippage_pct': 0.0005
    }

    print(f"\nParameters:")
    for key, value in params.items():
        print(f"  {key}: {value}")

    # Run backtest
    print("\nRunning backtest...")
    try:
        result = engine.run_ma_crossover(
            prices_df,
            fast_period=params['fast_period'],
            slow_period=params['slow_period'],
            initial_capital=params['initial_capital'],
            commission_pct=params['commission_pct'],
            slippage_pct=params['slippage_pct']
        )

        print("\n--- Results ---")
        print(f"Total Return:   {result.total_return:>10.2%}")
        print(f"CAGR:           {result.cagr:>10.2%}")
        print(f"Sharpe Ratio:   {result.sharpe_ratio:>10.2f}")
        print(f"Sortino Ratio:  {result.sortino_ratio:>10.2f}")
        print(f"Max Drawdown:   {result.max_drawdown:>10.2%}")
        print(f"Total Trades:   {result.total_trades:>10}")
        print(f"Win Rate:       {result.win_rate:>10.2%}")
        print(f"Profit Factor:  {result.profit_factor:>10.2f}")

        return result

    except Exception as e:
        print(f"Error: {e}")
        return None


def example_strategy_comparison(prices_df):
    """Example: Compare multiple strategies."""
    print("\n" + "=" * 60)
    print("Example 3: Strategy Comparison")
    print("=" * 60)

    from core import BacktestEngine

    engine = BacktestEngine()

    strategies = {
        'Mean Reversion (20,2.0)': lambda: engine.run_mean_reversion(
            prices_df, lookback=20, entry_zscore=2.0, exit_zscore=0.5,
            initial_capital=100000
        ),
        'Mean Reversion (30,1.5)': lambda: engine.run_mean_reversion(
            prices_df, lookback=30, entry_zscore=1.5, exit_zscore=0.5,
            initial_capital=100000
        ),
        'MA Crossover (10,30)': lambda: engine.run_ma_crossover(
            prices_df, fast_period=10, slow_period=30,
            initial_capital=100000
        ),
        'MA Crossover (5,20)': lambda: engine.run_ma_crossover(
            prices_df, fast_period=5, slow_period=20,
            initial_capital=100000
        ),
    }

    results = []

    print("\nRunning all strategies...")
    for name, strategy_func in strategies.items():
        try:
            result = strategy_func()
            results.append({
                'Strategy': name,
                'Return': result.total_return,
                'CAGR': result.cagr,
                'Sharpe': result.sharpe_ratio,
                'Max DD': result.max_drawdown,
                'Trades': result.total_trades,
                'Win Rate': result.win_rate
            })
            print(f"  {name}: Return={result.total_return:.2%}, Sharpe={result.sharpe_ratio:.2f}")
        except Exception as e:
            print(f"  {name}: Error - {e}")

    if results:
        print("\n--- Strategy Comparison ---")
        comparison_df = pd.DataFrame(results)
        comparison_df = comparison_df.set_index('Strategy')

        # Format for display
        formatted = comparison_df.copy()
        formatted['Return'] = formatted['Return'].apply(lambda x: f"{x:.2%}")
        formatted['CAGR'] = formatted['CAGR'].apply(lambda x: f"{x:.2%}")
        formatted['Sharpe'] = formatted['Sharpe'].apply(lambda x: f"{x:.2f}")
        formatted['Max DD'] = formatted['Max DD'].apply(lambda x: f"{x:.2%}")
        formatted['Win Rate'] = formatted['Win Rate'].apply(lambda x: f"{x:.2%}")

        print(formatted.to_string())

        # Find best strategy by Sharpe ratio
        best_idx = comparison_df['Sharpe'].idxmax()
        print(f"\nBest Strategy (by Sharpe): {best_idx}")


def example_parameter_sensitivity(prices_df):
    """Example: Parameter sensitivity analysis."""
    print("\n" + "=" * 60)
    print("Example 4: Parameter Sensitivity Analysis")
    print("=" * 60)

    from core import BacktestEngine

    engine = BacktestEngine()

    # Test different lookback periods
    lookbacks = [10, 15, 20, 25, 30]

    print("\nTesting Mean Reversion with different lookback periods...")
    print(f"{'Lookback':<10} {'Return':<12} {'Sharpe':<10} {'Max DD':<12}")
    print("-" * 44)

    for lookback in lookbacks:
        try:
            result = engine.run_mean_reversion(
                prices_df,
                lookback=lookback,
                entry_zscore=2.0,
                exit_zscore=0.5,
                initial_capital=100000
            )
            print(f"{lookback:<10} {result.total_return:<12.2%} {result.sharpe_ratio:<10.2f} {result.max_drawdown:<12.2%}")
        except Exception as e:
            print(f"{lookback:<10} Error: {e}")


def main():
    """Run all backtest examples."""
    print("\n" + "#" * 60)
    print("# Quantitative Trading Tool - Backtest Examples")
    print("#" * 60)

    # Fetch data
    prices_df = fetch_sample_data()
    print(f"\nData shape: {prices_df.shape}")
    print(f"Date range: {prices_df.index[0]} to {prices_df.index[-1]}")

    # Example 1: Mean reversion
    example_mean_reversion(prices_df)

    # Example 2: MA crossover
    example_ma_crossover(prices_df)

    # Example 3: Strategy comparison
    example_strategy_comparison(prices_df)

    # Example 4: Parameter sensitivity
    example_parameter_sensitivity(prices_df)

    print("\n" + "#" * 60)
    print("# Backtest examples completed!")
    print("#" * 60)


if __name__ == "__main__":
    main()
