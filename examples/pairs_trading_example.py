# -*- coding: utf-8 -*-
"""
Pairs trading example for quantitative trading tool.

Demonstrates:
- Finding cointegrated pairs
- Calculating hedge ratios
- Z-score based trading signals
- Half-life of mean reversion
- Backtesting pairs trading strategy

Usage:
    python examples/pairs_trading_example.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np


def fetch_pairs_data():
    """Fetch data for pairs trading."""
    from core import DataManager

    dm = DataManager()

    # Tech stocks that might be cointegrated
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'META']

    print("Fetching price data for pairs analysis...")
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
        print("Not enough data, using synthetic cointegrated data")
        np.random.seed(42)
        dates = pd.date_range(start='2022-01-01', end='2023-12-31', freq='B')
        n = len(dates)

        # Create cointegrated pair
        # Y = beta * X + stationary_spread
        x = 100 + np.cumsum(np.random.normal(0, 1, n))  # Random walk
        spread = np.zeros(n)
        for i in range(1, n):
            spread[i] = 0.9 * spread[i-1] + np.random.normal(0, 2)  # Mean reverting

        beta = 1.5
        y = beta * x + spread + 50

        prices = {
            'AAPL': pd.Series(y, index=dates),
            'MSFT': pd.Series(x, index=dates),
            'GOOGL': pd.Series(100 + np.cumsum(np.random.normal(0, 1, n)), index=dates),
            'META': pd.Series(80 + np.cumsum(np.random.normal(0, 1.2, n)), index=dates),
        }

    prices_df = pd.DataFrame(prices)
    return prices_df.dropna()


def example_cointegration_test(prices_df):
    """Example: Test for cointegration between pairs."""
    print("\n" + "=" * 60)
    print("Example 1: Cointegration Testing")
    print("=" * 60)

    from strategies import PairsTradingStrategy

    strategy = PairsTradingStrategy()
    symbols = list(prices_df.columns)

    print("\nTesting all pairs for cointegration...")
    print(f"{'Pair':<20} {'Cointegrated':<15} {'Hedge Ratio':<12} {'P-Value'}")
    print("-" * 60)

    cointegrated_pairs = []

    for i in range(len(symbols)):
        for j in range(i + 1, len(symbols)):
            sym1, sym2 = symbols[i], symbols[j]

            try:
                is_coint, hedge_ratio, p_value = strategy.test_cointegration(
                    prices_df[sym1],
                    prices_df[sym2]
                )

                status = "Yes" if is_coint else "No"
                print(f"{sym1}/{sym2:<15} {status:<15} {hedge_ratio:<12.4f} {p_value:.4f}")

                if is_coint:
                    cointegrated_pairs.append((sym1, sym2, hedge_ratio, p_value))

            except Exception as e:
                print(f"{sym1}/{sym2:<15} Error: {e}")

    if cointegrated_pairs:
        print(f"\nFound {len(cointegrated_pairs)} cointegrated pair(s)")
        return cointegrated_pairs[0]  # Return best pair
    else:
        print("\nNo cointegrated pairs found")
        # Return first pair for demonstration
        return (symbols[0], symbols[1], 1.0, 0.1)


def example_spread_analysis(prices_df, pair_info):
    """Example: Analyze the spread between a cointegrated pair."""
    print("\n" + "=" * 60)
    print("Example 2: Spread Analysis")
    print("=" * 60)

    sym1, sym2, hedge_ratio, _ = pair_info

    print(f"\nAnalyzing spread for {sym1}/{sym2}")
    print(f"Hedge Ratio: {hedge_ratio:.4f}")

    # Calculate spread
    spread = prices_df[sym1] - hedge_ratio * prices_df[sym2]

    print(f"\n--- Spread Statistics ---")
    print(f"Mean:        {spread.mean():.4f}")
    print(f"Std Dev:     {spread.std():.4f}")
    print(f"Min:         {spread.min():.4f}")
    print(f"Max:         {spread.max():.4f}")

    # Calculate Z-score
    lookback = 20
    spread_mean = spread.rolling(lookback).mean()
    spread_std = spread.rolling(lookback).std()
    zscore = (spread - spread_mean) / spread_std

    print(f"\n--- Z-Score Statistics (lookback={lookback}) ---")
    zscore_clean = zscore.dropna()
    print(f"Current Z-Score: {zscore_clean.iloc[-1]:.2f}")
    print(f"Mean Z-Score:    {zscore_clean.mean():.2f}")
    print(f"Max Z-Score:     {zscore_clean.max():.2f}")
    print(f"Min Z-Score:     {zscore_clean.min():.2f}")

    # Trading signal interpretation
    current_z = zscore_clean.iloc[-1]
    print(f"\n--- Current Trading Signal ---")
    if current_z > 2:
        print(f"Z-Score = {current_z:.2f}: SELL spread (short {sym1}, long {sym2})")
    elif current_z < -2:
        print(f"Z-Score = {current_z:.2f}: BUY spread (long {sym1}, short {sym2})")
    elif abs(current_z) < 0.5:
        print(f"Z-Score = {current_z:.2f}: EXIT position (spread near mean)")
    else:
        print(f"Z-Score = {current_z:.2f}: HOLD current position")

    return spread, zscore


def example_half_life(spread):
    """Example: Calculate half-life of mean reversion."""
    print("\n" + "=" * 60)
    print("Example 3: Half-Life of Mean Reversion")
    print("=" * 60)

    from strategies import PairsTradingStrategy

    strategy = PairsTradingStrategy()

    half_life = strategy.calculate_half_life(spread)

    print(f"\nHalf-Life: {half_life:.1f} days")

    print("\n--- Interpretation ---")
    if half_life < 5:
        print("Very fast mean reversion - suitable for high-frequency trading")
    elif half_life < 20:
        print("Fast mean reversion - suitable for short-term swing trading")
    elif half_life < 60:
        print("Moderate mean reversion - suitable for medium-term positions")
    elif half_life < 120:
        print("Slow mean reversion - requires patience, longer holding periods")
    else:
        print("Very slow mean reversion - may not be practical for trading")

    print(f"\nExpected time to revert 50%: {half_life:.1f} days")
    print(f"Expected time to revert 75%: {half_life * 2:.1f} days")
    print(f"Expected time to revert 90%: {half_life * 3.32:.1f} days")


def example_pairs_trading_signals(prices_df, pair_info):
    """Example: Generate trading signals for pairs trading."""
    print("\n" + "=" * 60)
    print("Example 4: Trading Signals Generation")
    print("=" * 60)

    from strategies import PairsTradingStrategy

    sym1, sym2, hedge_ratio, _ = pair_info

    strategy = PairsTradingStrategy(
        lookback=20,
        entry_zscore=2.0,
        exit_zscore=0.5,
        hedge_ratio=hedge_ratio
    )

    print(f"\nStrategy Parameters:")
    print(f"  Lookback Period: {strategy.lookback}")
    print(f"  Entry Z-Score:   +/- {strategy.entry_zscore}")
    print(f"  Exit Z-Score:    +/- {strategy.exit_zscore}")
    print(f"  Hedge Ratio:     {strategy.hedge_ratio:.4f}")

    # Generate signals
    pair_prices = prices_df[[sym1, sym2]].copy()
    signals = strategy.generate_signals(pair_prices)

    # Count signals
    print(f"\n--- Signal Summary ---")
    signal_counts = signals['signal'].value_counts()
    for signal_type, count in signal_counts.items():
        if signal_type == 1:
            print(f"  Long Spread (Buy {sym1}, Sell {sym2}):  {count}")
        elif signal_type == -1:
            print(f"  Short Spread (Sell {sym1}, Buy {sym2}): {count}")
        else:
            print(f"  No Position: {count}")

    # Show recent signals
    print(f"\n--- Recent Trading Signals ---")
    recent = signals.tail(10)
    print(f"{'Date':<12} {'Z-Score':<10} {'Signal':<15}")
    print("-" * 37)

    for date, row in recent.iterrows():
        z = row['zscore']
        sig = row['signal']
        if sig == 1:
            signal_str = "Long Spread"
        elif sig == -1:
            signal_str = "Short Spread"
        else:
            signal_str = "No Position"
        print(f"{date.strftime('%Y-%m-%d'):<12} {z:<10.2f} {signal_str:<15}")

    return signals


def example_pairs_backtest(prices_df, pair_info):
    """Example: Backtest pairs trading strategy."""
    print("\n" + "=" * 60)
    print("Example 5: Pairs Trading Backtest")
    print("=" * 60)

    from strategies import PairsTradingStrategy

    sym1, sym2, hedge_ratio, _ = pair_info

    strategy = PairsTradingStrategy(
        lookback=20,
        entry_zscore=2.0,
        exit_zscore=0.5,
        hedge_ratio=hedge_ratio
    )

    pair_prices = prices_df[[sym1, sym2]].copy()

    print(f"\nBacktesting {sym1}/{sym2} pairs trading...")

    try:
        result = strategy.backtest(
            pair_prices,
            initial_capital=100000,
            commission=0.001
        )

        print("\n--- Backtest Results ---")
        print(f"Total Return:    {result.total_return:>10.2%}")
        print(f"Sharpe Ratio:    {result.sharpe_ratio:>10.2f}")
        print(f"Max Drawdown:    {result.max_drawdown:>10.2%}")
        print(f"Total Trades:    {result.total_trades:>10}")
        print(f"Win Rate:        {result.win_rate:>10.2%}")

        return result

    except Exception as e:
        print(f"Backtest error: {e}")

        # Manual backtest calculation
        print("\nPerforming simplified backtest...")

        signals = strategy.generate_signals(pair_prices)

        # Calculate spread returns
        spread = pair_prices[sym1] - hedge_ratio * pair_prices[sym2]
        spread_returns = spread.pct_change()

        # Apply signals
        strategy_returns = signals['signal'].shift(1) * spread_returns
        strategy_returns = strategy_returns.dropna()

        # Calculate metrics
        total_return = (1 + strategy_returns).prod() - 1
        sharpe = strategy_returns.mean() / strategy_returns.std() * np.sqrt(252)

        cumulative = (1 + strategy_returns).cumprod()
        max_dd = (cumulative / cumulative.cummax() - 1).min()

        print(f"\n--- Simplified Backtest Results ---")
        print(f"Total Return:    {total_return:>10.2%}")
        print(f"Sharpe Ratio:    {sharpe:>10.2f}")
        print(f"Max Drawdown:    {max_dd:>10.2%}")

        return None


def example_pair_selection(prices_df):
    """Example: Systematic pair selection process."""
    print("\n" + "=" * 60)
    print("Example 6: Systematic Pair Selection")
    print("=" * 60)

    from strategies import PairsTradingStrategy

    strategy = PairsTradingStrategy()
    symbols = list(prices_df.columns)

    print("\nStep 1: Test all pairs for cointegration")
    print("-" * 40)

    pair_metrics = []

    for i in range(len(symbols)):
        for j in range(i + 1, len(symbols)):
            sym1, sym2 = symbols[i], symbols[j]

            try:
                # Test cointegration
                is_coint, hedge_ratio, p_value = strategy.test_cointegration(
                    prices_df[sym1],
                    prices_df[sym2]
                )

                if is_coint:
                    # Calculate spread and half-life
                    spread = prices_df[sym1] - hedge_ratio * prices_df[sym2]
                    half_life = strategy.calculate_half_life(spread)

                    # Calculate spread volatility
                    spread_vol = spread.std()

                    pair_metrics.append({
                        'Pair': f"{sym1}/{sym2}",
                        'P-Value': p_value,
                        'Hedge Ratio': hedge_ratio,
                        'Half-Life': half_life,
                        'Spread Vol': spread_vol
                    })

                    print(f"  {sym1}/{sym2}: p={p_value:.4f}, HL={half_life:.1f} days")

            except Exception as e:
                continue

    if not pair_metrics:
        print("No cointegrated pairs found")
        return

    print(f"\nStep 2: Rank pairs by tradability")
    print("-" * 40)

    # Create DataFrame and rank
    df = pd.DataFrame(pair_metrics)

    # Score: prefer low p-value, moderate half-life (5-30 days)
    df['HL_Score'] = df['Half-Life'].apply(
        lambda x: 1.0 if 5 <= x <= 30 else 0.5 if 30 < x <= 60 else 0.2
    )
    df['P_Score'] = 1 - df['P-Value']
    df['Total_Score'] = df['HL_Score'] * df['P_Score']

    df = df.sort_values('Total_Score', ascending=False)

    print(f"\n{'Pair':<15} {'P-Value':<10} {'Half-Life':<12} {'Score'}")
    print("-" * 47)
    for _, row in df.iterrows():
        print(f"{row['Pair']:<15} {row['P-Value']:<10.4f} {row['Half-Life']:<12.1f} {row['Total_Score']:.2f}")

    if len(df) > 0:
        best_pair = df.iloc[0]['Pair']
        print(f"\nRecommended Pair: {best_pair}")


def main():
    """Run all pairs trading examples."""
    print("\n" + "#" * 60)
    print("# Quantitative Trading Tool - Pairs Trading Examples")
    print("#" * 60)

    # Fetch data
    prices_df = fetch_pairs_data()
    print(f"\nData shape: {prices_df.shape}")
    print(f"Assets: {list(prices_df.columns)}")

    # Example 1: Cointegration testing
    pair_info = example_cointegration_test(prices_df)

    # Example 2: Spread analysis
    spread, zscore = example_spread_analysis(prices_df, pair_info)

    # Example 3: Half-life
    example_half_life(spread)

    # Example 4: Trading signals
    example_pairs_trading_signals(prices_df, pair_info)

    # Example 5: Backtest
    example_pairs_backtest(prices_df, pair_info)

    # Example 6: Pair selection
    example_pair_selection(prices_df)

    print("\n" + "#" * 60)
    print("# Pairs trading examples completed!")
    print("#" * 60)


if __name__ == "__main__":
    main()
