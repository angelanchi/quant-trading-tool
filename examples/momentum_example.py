# -*- coding: utf-8 -*-
"""
Momentum strategy examples for quantitative trading tool.

Demonstrates:
- Classic momentum strategy
- Trend following with ADX
- Dual momentum (absolute + relative)
- Breakout trading

Usage:
    python examples/momentum_example.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np


def fetch_momentum_data():
    """Fetch data for momentum strategies."""
    from core import DataManager

    dm = DataManager()
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN']

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

    if len(prices) < 2:
        print("Using synthetic data for demonstration")
        from scripts.generate_sample_data import generate_correlated_assets

        prices_df = generate_correlated_assets(symbols, n_days=504, seed=42)
        dates = pd.date_range(start='2022-01-01', periods=504, freq='B')
        prices_df.index = dates
        return prices_df

    prices_df = pd.DataFrame(prices)
    return prices_df.dropna()


def example_classic_momentum(prices_df):
    """Example: Classic momentum strategy."""
    print("\n" + "=" * 60)
    print("Example 1: Classic Momentum Strategy")
    print("=" * 60)

    from strategies import MomentumStrategy

    strategy = MomentumStrategy(
        lookback=20,
        ma_period=50,
        min_momentum=0.0
    )

    print(f"\nParameters:")
    print(f"  Lookback: {strategy.lookback} days")
    print(f"  MA Period: {strategy.ma_period} days")
    print(f"  Min Momentum: {strategy.min_momentum}")

    # Generate signals
    signals = strategy.generate_signals(prices_df)

    # Analyze signals
    print(f"\n--- Signal Analysis ---")
    signal_counts = signals['signal'].value_counts()
    total = len(signals['signal'].dropna())

    for sig, count in sorted(signal_counts.items()):
        if sig == 1:
            label = "Long"
        elif sig == -1:
            label = "Short"
        else:
            label = "Neutral"
        print(f"  {label}: {count} ({count/total*100:.1f}%)")

    # Current signal
    current = signals['signal'].iloc[-1]
    current_momentum = signals['momentum'].iloc[-1]
    print(f"\nCurrent Signal: {current} (Momentum: {current_momentum:.2%})")


def example_trend_following(prices_df):
    """Example: Trend following with ADX."""
    print("\n" + "=" * 60)
    print("Example 2: Trend Following Strategy")
    print("=" * 60)

    from strategies import TrendFollowingStrategy

    strategy = TrendFollowingStrategy(
        fast_ma=20,
        slow_ma=50,
        adx_period=14,
        adx_threshold=25.0
    )

    print(f"\nParameters:")
    print(f"  Fast MA: {strategy.fast_ma} days")
    print(f"  Slow MA: {strategy.slow_ma} days")
    print(f"  ADX Period: {strategy.adx_period} days")
    print(f"  ADX Threshold: {strategy.adx_threshold}")

    # Use first column for single-asset analysis
    price_series = prices_df.iloc[:, 0].to_frame()

    signals = strategy.generate_signals(price_series)

    print(f"\n--- Recent Signals ---")
    recent = signals.tail(10)[['signal', 'fast_ma', 'slow_ma', 'adx']]
    recent = recent.round(2)
    print(recent.to_string())

    # Trend strength
    current_adx = signals['adx'].iloc[-1]
    print(f"\nCurrent ADX: {current_adx:.2f}")
    if current_adx > 40:
        print("Interpretation: Very strong trend")
    elif current_adx > 25:
        print("Interpretation: Strong trend")
    elif current_adx > 20:
        print("Interpretation: Developing trend")
    else:
        print("Interpretation: Weak/no trend - avoid trading")


def example_dual_momentum(prices_df):
    """Example: Dual momentum strategy."""
    print("\n" + "=" * 60)
    print("Example 3: Dual Momentum Strategy")
    print("=" * 60)

    from strategies import DualMomentumStrategy

    strategy = DualMomentumStrategy(
        lookback=60,  # ~3 months
        risk_free_rate=0.02
    )

    print(f"\nParameters:")
    print(f"  Lookback: {strategy.lookback} days")
    print(f"  Risk-Free Rate: {strategy.risk_free_rate:.1%}")

    signals = strategy.generate_signals(prices_df)

    # Calculate momentum for each asset
    print(f"\n--- Asset Momentum (Latest) ---")
    returns = prices_df.pct_change(strategy.lookback).iloc[-1]

    for symbol in prices_df.columns:
        momentum = returns[symbol]
        signal = signals[symbol].iloc[-1] if symbol in signals.columns else 0

        status = "Selected" if signal == 1 else "Not selected"
        print(f"  {symbol}: {momentum:.2%} momentum - {status}")

    print(f"\nPortfolio Signal: {signals['signal'].iloc[-1]:.2f}")


def example_breakout(prices_df):
    """Example: Breakout strategy."""
    print("\n" + "=" * 60)
    print("Example 4: Breakout Strategy")
    print("=" * 60)

    from strategies import BreakoutStrategy

    strategy = BreakoutStrategy(
        entry_period=20,  # 20-day high for entry
        exit_period=10,   # 10-day low for exit
        atr_multiplier=2.0
    )

    print(f"\nParameters:")
    print(f"  Entry Period: {strategy.entry_period} days")
    print(f"  Exit Period: {strategy.exit_period} days")
    print(f"  ATR Multiplier: {strategy.atr_multiplier}")

    # Use first asset
    price_series = prices_df.iloc[:, 0].to_frame()
    price_series.columns = ['close']

    signals = strategy.generate_signals(price_series)

    # Current levels
    current_price = price_series['close'].iloc[-1]
    upper_channel = signals['upper_channel'].iloc[-1]
    lower_channel = signals['lower_channel'].iloc[-1]
    current_signal = signals['signal'].iloc[-1]

    print(f"\n--- Current Levels ---")
    print(f"  Price: ${current_price:.2f}")
    print(f"  Upper Channel ({strategy.entry_period}-day high): ${upper_channel:.2f}")
    print(f"  Lower Channel ({strategy.exit_period}-day low): ${lower_channel:.2f}")

    print(f"\nCurrent Position: ", end="")
    if current_signal == 1:
        print("LONG (breakout above channel)")
    elif current_signal == -1:
        print("SHORT (breakdown below channel)")
    else:
        print("FLAT (within channel)")

    # Count breakouts
    signal_changes = signals['signal'].diff().abs()
    n_breakouts = (signal_changes > 0).sum()
    print(f"\nTotal Breakout Signals: {n_breakouts}")


def example_strategy_comparison(prices_df):
    """Example: Compare momentum strategies."""
    print("\n" + "=" * 60)
    print("Example 5: Strategy Comparison")
    print("=" * 60)

    from strategies import (
        MomentumStrategy,
        TrendFollowingStrategy,
        BreakoutStrategy
    )

    # Use single asset for comparison
    price_series = prices_df.iloc[:, 0].to_frame()
    price_series.columns = ['close']

    strategies = {
        'Momentum': MomentumStrategy(lookback=20, ma_period=50),
        'Trend Following': TrendFollowingStrategy(fast_ma=20, slow_ma=50),
        'Breakout': BreakoutStrategy(entry_period=20, exit_period=10),
    }

    print("\nComparing strategy signals...")

    results = []
    for name, strategy in strategies.items():
        signals = strategy.generate_signals(price_series)

        # Count trades (signal changes)
        signal_changes = signals['signal'].diff().fillna(0)
        n_trades = (signal_changes != 0).sum()

        # Time in market
        time_long = (signals['signal'] == 1).sum() / len(signals) * 100
        time_short = (signals['signal'] == -1).sum() / len(signals) * 100

        results.append({
            'Strategy': name,
            'Trades': n_trades,
            'Long %': time_long,
            'Short %': time_short,
            'Current': signals['signal'].iloc[-1]
        })

    results_df = pd.DataFrame(results)
    print("\n" + results_df.to_string(index=False))


def main():
    """Run all momentum strategy examples."""
    print("\n" + "#" * 60)
    print("# Quantitative Trading Tool - Momentum Strategy Examples")
    print("#" * 60)

    # Fetch data
    prices_df = fetch_momentum_data()
    print(f"\nData shape: {prices_df.shape}")
    print(f"Assets: {list(prices_df.columns)}")

    # Example 1: Classic Momentum
    example_classic_momentum(prices_df)

    # Example 2: Trend Following
    example_trend_following(prices_df)

    # Example 3: Dual Momentum
    example_dual_momentum(prices_df)

    # Example 4: Breakout
    example_breakout(prices_df)

    # Example 5: Comparison
    example_strategy_comparison(prices_df)

    print("\n" + "#" * 60)
    print("# Momentum strategy examples completed!")
    print("#" * 60)


if __name__ == "__main__":
    main()
