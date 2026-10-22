# -*- coding: utf-8 -*-
"""
Basic usage example for quantitative trading tool.

Demonstrates:
- Fetching stock data from Taiwan and US markets
- Basic data manipulation
- Simple price analysis

Usage:
    python examples/basic_usage.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np


def example_data_fetching():
    """Example: Fetching stock data."""
    print("=" * 60)
    print("Example 1: Data Fetching")
    print("=" * 60)

    from core import DataManager

    dm = DataManager()

    # Fetch US stock data (Apple)
    print("\n[1] Fetching US stock data (AAPL)...")
    try:
        aapl = dm.fetch_ohlcv('AAPL', '2023-01-01', '2023-12-31')
        if aapl is not None and not aapl.empty:
            print(f"    Records: {len(aapl)}")
            print(f"    Date range: {aapl.index[0]} to {aapl.index[-1]}")
            print(f"    Columns: {list(aapl.columns)}")
            print(f"\n    First 5 rows:")
            print(aapl.head())
        else:
            print("    No data returned")
    except Exception as e:
        print(f"    Error: {e}")

    # Fetch Taiwan stock data (TSMC)
    print("\n[2] Fetching Taiwan stock data (2330)...")
    try:
        tsmc = dm.fetch_ohlcv('2330', '2023-01-01', '2023-12-31')
        if tsmc is not None and not tsmc.empty:
            print(f"    Records: {len(tsmc)}")
            print(f"    Date range: {tsmc.index[0]} to {tsmc.index[-1]}")
            print(f"\n    First 5 rows:")
            print(tsmc.head())
        else:
            print("    No data returned")
    except Exception as e:
        print(f"    Error: {e}")

    return aapl if 'aapl' in dir() and aapl is not None else None


def example_basic_analysis(prices_df):
    """Example: Basic price analysis."""
    print("\n" + "=" * 60)
    print("Example 2: Basic Price Analysis")
    print("=" * 60)

    if prices_df is None or prices_df.empty:
        print("No price data available for analysis")
        return

    close = prices_df['close']

    # Calculate returns
    daily_returns = close.pct_change().dropna()

    print(f"\n[1] Daily Returns Statistics:")
    print(f"    Mean:   {daily_returns.mean():.4%}")
    print(f"    Std:    {daily_returns.std():.4%}")
    print(f"    Min:    {daily_returns.min():.4%}")
    print(f"    Max:    {daily_returns.max():.4%}")
    print(f"    Skew:   {daily_returns.skew():.4f}")
    print(f"    Kurt:   {daily_returns.kurtosis():.4f}")

    # Calculate annualized metrics
    annual_return = (1 + daily_returns).prod() ** (252 / len(daily_returns)) - 1
    annual_volatility = daily_returns.std() * np.sqrt(252)

    print(f"\n[2] Annualized Metrics:")
    print(f"    Return:     {annual_return:.2%}")
    print(f"    Volatility: {annual_volatility:.2%}")

    # Calculate simple moving averages
    print(f"\n[3] Moving Averages (latest values):")
    sma_20 = close.rolling(20).mean().iloc[-1]
    sma_50 = close.rolling(50).mean().iloc[-1]
    current_price = close.iloc[-1]

    print(f"    Current Price: ${current_price:.2f}")
    print(f"    SMA(20):       ${sma_20:.2f}")
    print(f"    SMA(50):       ${sma_50:.2f}")

    # Price vs MA signals
    if current_price > sma_20 > sma_50:
        signal = "Bullish (Price > SMA20 > SMA50)"
    elif current_price < sma_20 < sma_50:
        signal = "Bearish (Price < SMA20 < SMA50)"
    else:
        signal = "Neutral"
    print(f"    Signal:        {signal}")


def example_correlation_analysis():
    """Example: Multi-asset correlation analysis."""
    print("\n" + "=" * 60)
    print("Example 3: Multi-Asset Correlation")
    print("=" * 60)

    from core import DataManager

    dm = DataManager()
    symbols = ['AAPL', 'MSFT', 'GOOGL']

    print(f"\nFetching data for: {', '.join(symbols)}")

    prices = {}
    for symbol in symbols:
        try:
            df = dm.fetch_ohlcv(symbol, '2023-01-01', '2023-12-31')
            if df is not None and not df.empty:
                prices[symbol] = df['close']
                print(f"  {symbol}: {len(df)} records")
        except Exception as e:
            print(f"  {symbol}: Error - {e}")

    if len(prices) < 2:
        print("Not enough data for correlation analysis")
        return

    # Create price DataFrame
    prices_df = pd.DataFrame(prices)
    prices_df = prices_df.dropna()

    # Calculate returns
    returns_df = prices_df.pct_change().dropna()

    # Correlation matrix
    print(f"\n[1] Correlation Matrix:")
    corr_matrix = returns_df.corr()
    print(corr_matrix.round(4))

    # Covariance matrix
    print(f"\n[2] Annualized Covariance Matrix:")
    cov_matrix = returns_df.cov() * 252
    print(cov_matrix.round(6))


def main():
    """Run all examples."""
    print("\n" + "#" * 60)
    print("# Quantitative Trading Tool - Basic Usage Examples")
    print("#" * 60)

    # Example 1: Data fetching
    prices = example_data_fetching()

    # Example 2: Basic analysis
    example_basic_analysis(prices)

    # Example 3: Correlation analysis
    example_correlation_analysis()

    print("\n" + "#" * 60)
    print("# Examples completed!")
    print("#" * 60)


if __name__ == "__main__":
    main()
