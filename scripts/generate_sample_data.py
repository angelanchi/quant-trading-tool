# -*- coding: utf-8 -*-
"""
Sample data generator for offline testing.

Generates realistic synthetic stock price data when API access
is unavailable or for testing purposes.

Usage:
    python scripts/generate_sample_data.py --symbols AAPL,MSFT,GOOGL --days 500
    python scripts/generate_sample_data.py --output data/sample_prices.csv
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np


def generate_gbm_prices(
    n_days: int = 252,
    initial_price: float = 100.0,
    annual_return: float = 0.10,
    annual_volatility: float = 0.20,
    seed: int = None
) -> pd.Series:
    """
    Generate prices using Geometric Brownian Motion.

    GBM is the standard model for stock price simulation:
    dS = mu * S * dt + sigma * S * dW

    Args:
        n_days: Number of trading days
        initial_price: Starting price
        annual_return: Expected annual return (drift)
        annual_volatility: Annual volatility
        seed: Random seed for reproducibility

    Returns:
        Series of simulated prices
    """
    if seed is not None:
        np.random.seed(seed)

    # Daily parameters
    dt = 1 / 252
    daily_return = annual_return * dt
    daily_vol = annual_volatility * np.sqrt(dt)

    # Generate random returns
    random_returns = np.random.normal(daily_return, daily_vol, n_days)

    # Calculate prices
    prices = initial_price * np.exp(np.cumsum(random_returns))

    return prices


def generate_ohlcv(
    n_days: int = 252,
    initial_price: float = 100.0,
    annual_return: float = 0.10,
    annual_volatility: float = 0.20,
    avg_volume: int = 1000000,
    seed: int = None
) -> pd.DataFrame:
    """
    Generate OHLCV (Open, High, Low, Close, Volume) data.

    Args:
        n_days: Number of trading days
        initial_price: Starting price
        annual_return: Expected annual return
        annual_volatility: Annual volatility
        avg_volume: Average daily volume
        seed: Random seed

    Returns:
        DataFrame with OHLCV columns
    """
    if seed is not None:
        np.random.seed(seed)

    # Generate close prices
    close_prices = generate_gbm_prices(
        n_days, initial_price, annual_return, annual_volatility, seed
    )

    # Generate intraday range
    daily_range = annual_volatility / np.sqrt(252) * close_prices

    # Generate OHLC
    data = {
        'open': close_prices * (1 + np.random.uniform(-0.01, 0.01, n_days)),
        'high': close_prices + np.abs(np.random.normal(0, daily_range)),
        'low': close_prices - np.abs(np.random.normal(0, daily_range)),
        'close': close_prices,
        'volume': np.random.lognormal(np.log(avg_volume), 0.5, n_days).astype(int)
    }

    df = pd.DataFrame(data)

    # Ensure high >= max(open, close) and low <= min(open, close)
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)

    return df


def generate_correlated_assets(
    symbols: list,
    n_days: int = 252,
    correlation_matrix: np.ndarray = None,
    seed: int = None
) -> pd.DataFrame:
    """
    Generate correlated asset prices.

    Args:
        symbols: List of asset symbols
        n_days: Number of trading days
        correlation_matrix: Correlation matrix (if None, uses default)
        seed: Random seed

    Returns:
        DataFrame with prices for each symbol
    """
    if seed is not None:
        np.random.seed(seed)

    n_assets = len(symbols)

    # Default correlation matrix (moderate positive correlations)
    if correlation_matrix is None:
        correlation_matrix = np.eye(n_assets)
        for i in range(n_assets):
            for j in range(i + 1, n_assets):
                corr = np.random.uniform(0.3, 0.7)
                correlation_matrix[i, j] = corr
                correlation_matrix[j, i] = corr

    # Cholesky decomposition
    L = np.linalg.cholesky(correlation_matrix)

    # Generate correlated random numbers
    uncorrelated = np.random.normal(0, 1, (n_days, n_assets))
    correlated = uncorrelated @ L.T

    # Asset-specific parameters
    asset_params = {
        'AAPL': {'initial': 150, 'return': 0.15, 'vol': 0.25},
        'MSFT': {'initial': 300, 'return': 0.12, 'vol': 0.22},
        'GOOGL': {'initial': 120, 'return': 0.10, 'vol': 0.28},
        'AMZN': {'initial': 130, 'return': 0.08, 'vol': 0.30},
        'META': {'initial': 250, 'return': 0.18, 'vol': 0.35},
        'NVDA': {'initial': 400, 'return': 0.25, 'vol': 0.40},
        'TSLA': {'initial': 200, 'return': 0.20, 'vol': 0.50},
        '2330': {'initial': 500, 'return': 0.12, 'vol': 0.25},  # TSMC
        '2317': {'initial': 100, 'return': 0.08, 'vol': 0.22},  # Hon Hai
    }

    # Default parameters
    default_params = {'initial': 100, 'return': 0.10, 'vol': 0.25}

    prices = {}

    for i, symbol in enumerate(symbols):
        params = asset_params.get(symbol, default_params)

        dt = 1 / 252
        daily_return = params['return'] * dt
        daily_vol = params['vol'] * np.sqrt(dt)

        returns = daily_return + daily_vol * correlated[:, i]
        price = params['initial'] * np.exp(np.cumsum(returns))

        prices[symbol] = price

    return pd.DataFrame(prices)


def generate_sample_dataset(
    symbols: list = None,
    start_date: str = None,
    n_days: int = 504,
    include_ohlcv: bool = True,
    seed: int = 42
) -> dict:
    """
    Generate a complete sample dataset.

    Args:
        symbols: List of symbols (default: tech stocks)
        start_date: Start date string (default: 2 years ago)
        n_days: Number of trading days
        include_ohlcv: Include OHLCV data for each symbol
        seed: Random seed

    Returns:
        Dictionary with price data for each symbol
    """
    if symbols is None:
        symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']

    if start_date is None:
        start_date = (datetime.now() - timedelta(days=n_days * 1.5)).strftime('%Y-%m-%d')

    # Generate date index
    dates = pd.date_range(start=start_date, periods=n_days, freq='B')

    # Generate correlated close prices
    close_prices = generate_correlated_assets(symbols, n_days, seed=seed)
    close_prices.index = dates

    result = {'close': close_prices}

    if include_ohlcv:
        for symbol in symbols:
            ohlcv = generate_ohlcv(
                n_days=n_days,
                initial_price=close_prices[symbol].iloc[0],
                seed=seed + hash(symbol) % 1000
            )
            ohlcv.index = dates

            # Adjust to match correlated close
            ratio = close_prices[symbol] / ohlcv['close']
            for col in ['open', 'high', 'low', 'close']:
                ohlcv[col] = ohlcv[col] * ratio

            result[symbol] = ohlcv

    return result


def main():
    """Generate sample data from command line."""
    parser = argparse.ArgumentParser(
        description='Generate sample stock price data'
    )
    parser.add_argument(
        '--symbols', '-s',
        type=str,
        default='AAPL,MSFT,GOOGL',
        help='Comma-separated list of symbols'
    )
    parser.add_argument(
        '--days', '-d',
        type=int,
        default=504,
        help='Number of trading days (default: 504 = ~2 years)'
    )
    parser.add_argument(
        '--start',
        type=str,
        help='Start date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output directory for CSV files'
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='Random seed for reproducibility'
    )

    args = parser.parse_args()

    print("=" * 50)
    print("Sample Data Generator")
    print("=" * 50)

    symbols = [s.strip().upper() for s in args.symbols.split(',')]

    print(f"\nSymbols: {', '.join(symbols)}")
    print(f"Days: {args.days}")
    print(f"Seed: {args.seed}")

    # Generate data
    print("\nGenerating data...")
    data = generate_sample_dataset(
        symbols=symbols,
        start_date=args.start,
        n_days=args.days,
        include_ohlcv=True,
        seed=args.seed
    )

    # Output
    if args.output:
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save close prices
        close_path = output_dir / 'close_prices.csv'
        data['close'].to_csv(close_path)
        print(f"\nSaved: {close_path}")

        # Save individual OHLCV files
        for symbol in symbols:
            if symbol in data:
                ohlcv_path = output_dir / f'{symbol}_ohlcv.csv'
                data[symbol].to_csv(ohlcv_path)
                print(f"Saved: {ohlcv_path}")

    else:
        # Print summary
        print("\n--- Generated Data Summary ---")
        print(f"Date range: {data['close'].index[0]} to {data['close'].index[-1]}")
        print(f"\nClose prices shape: {data['close'].shape}")
        print("\nSample close prices (first 5 rows):")
        print(data['close'].head())

        print("\nTo save files, use --output flag")

    print("\n" + "=" * 50)
    print("Data generation complete!")
    print("=" * 50)


if __name__ == "__main__":
    main()
