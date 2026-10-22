# -*- coding: utf-8 -*-
"""
Portfolio optimization example for quantitative trading tool.

Demonstrates:
- Maximum Sharpe ratio optimization
- Minimum volatility optimization
- Risk parity (Hierarchical Risk Parity)
- Black-Litterman model with investor views
- Efficient frontier visualization

Usage:
    python examples/optimization_example.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np


def fetch_portfolio_data():
    """Fetch data for portfolio optimization."""
    from core import DataManager

    dm = DataManager()
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']

    print("Fetching price data for portfolio...")
    prices = {}

    for symbol in symbols:
        try:
            df = dm.fetch_ohlcv(symbol, '2022-01-01', '2023-12-31')
            if df is not None and not df.empty:
                prices[symbol] = df['close']
                print(f"  {symbol}: {len(df)} records")
        except Exception as e:
            print(f"  {symbol}: Error - {e}")

    if len(prices) < 3:
        print("Not enough data, using synthetic data for demonstration")
        np.random.seed(42)
        dates = pd.date_range(start='2022-01-01', end='2023-12-31', freq='B')

        # Generate correlated returns
        n_assets = len(symbols)
        n_days = len(dates)

        # Correlation matrix
        corr = np.array([
            [1.0, 0.7, 0.6, 0.5, 0.6],
            [0.7, 1.0, 0.7, 0.5, 0.6],
            [0.6, 0.7, 1.0, 0.6, 0.7],
            [0.5, 0.5, 0.6, 1.0, 0.5],
            [0.6, 0.6, 0.7, 0.5, 1.0]
        ])

        # Cholesky decomposition for correlated returns
        L = np.linalg.cholesky(corr)

        # Expected returns and volatilities
        expected_returns = [0.15, 0.12, 0.18, 0.10, 0.14]
        volatilities = [0.25, 0.20, 0.30, 0.22, 0.28]

        for i, symbol in enumerate(symbols):
            uncorrelated = np.random.normal(0, 1, n_days)
            correlated = L[i, :i+1] @ np.random.normal(0, 1, (i+1, n_days))
            daily_vol = volatilities[i] / np.sqrt(252)
            daily_return = expected_returns[i] / 252
            returns = daily_return + daily_vol * correlated
            price = 100 * np.exp(np.cumsum(returns))
            prices[symbol] = pd.Series(price, index=dates, name=symbol)

    prices_df = pd.DataFrame(prices)
    return prices_df.dropna()


def example_max_sharpe(prices_df):
    """Example: Maximum Sharpe ratio optimization."""
    print("\n" + "=" * 60)
    print("Example 1: Maximum Sharpe Ratio Optimization")
    print("=" * 60)

    from core import PortfolioOptimizer

    optimizer = PortfolioOptimizer()

    print("\nOptimizing for maximum Sharpe ratio...")
    try:
        result = optimizer.max_sharpe(prices_df, risk_free_rate=0.02)

        print("\n--- Optimal Weights ---")
        for symbol, weight in result.weights.items():
            if weight > 0.001:  # Only show non-trivial allocations
                print(f"  {symbol}: {weight:>8.2%}")

        print("\n--- Expected Performance ---")
        print(f"  Expected Return:  {result.expected_return:>8.2%}")
        print(f"  Volatility:       {result.volatility:>8.2%}")
        print(f"  Sharpe Ratio:     {result.sharpe_ratio:>8.2f}")

        return result

    except Exception as e:
        print(f"Error: {e}")
        return None


def example_min_volatility(prices_df):
    """Example: Minimum volatility optimization."""
    print("\n" + "=" * 60)
    print("Example 2: Minimum Volatility Optimization")
    print("=" * 60)

    from core import PortfolioOptimizer

    optimizer = PortfolioOptimizer()

    print("\nOptimizing for minimum volatility...")
    try:
        result = optimizer.min_volatility(prices_df)

        print("\n--- Optimal Weights ---")
        for symbol, weight in result.weights.items():
            if weight > 0.001:
                print(f"  {symbol}: {weight:>8.2%}")

        print("\n--- Expected Performance ---")
        print(f"  Expected Return:  {result.expected_return:>8.2%}")
        print(f"  Volatility:       {result.volatility:>8.2%}")
        print(f"  Sharpe Ratio:     {result.sharpe_ratio:>8.2f}")

        return result

    except Exception as e:
        print(f"Error: {e}")
        return None


def example_risk_parity(prices_df):
    """Example: Risk parity (HRP) optimization."""
    print("\n" + "=" * 60)
    print("Example 3: Risk Parity (Hierarchical Risk Parity)")
    print("=" * 60)

    from core import PortfolioOptimizer

    optimizer = PortfolioOptimizer()

    print("\nOptimizing for risk parity...")
    try:
        result = optimizer.risk_parity(prices_df)

        print("\n--- Optimal Weights ---")
        for symbol, weight in result.weights.items():
            if weight > 0.001:
                print(f"  {symbol}: {weight:>8.2%}")

        print("\n--- Expected Performance ---")
        print(f"  Expected Return:  {result.expected_return:>8.2%}")
        print(f"  Volatility:       {result.volatility:>8.2%}")
        print(f"  Sharpe Ratio:     {result.sharpe_ratio:>8.2f}")

        return result

    except Exception as e:
        print(f"Error: {e}")
        return None


def example_black_litterman(prices_df):
    """Example: Black-Litterman optimization with investor views."""
    print("\n" + "=" * 60)
    print("Example 4: Black-Litterman Model")
    print("=" * 60)

    from core import PortfolioOptimizer

    optimizer = PortfolioOptimizer()

    # Define investor views
    # View 1: AAPL will return 15% annually
    # View 2: GOOGL will outperform MSFT by 5%
    views = {
        'AAPL': 0.15,   # Absolute view: AAPL returns 15%
        'GOOGL': 0.12,  # Absolute view: GOOGL returns 12%
    }

    print("\nInvestor Views:")
    for symbol, expected_return in views.items():
        print(f"  {symbol}: {expected_return:.0%} expected return")

    print("\nOptimizing with Black-Litterman model...")
    try:
        result = optimizer.black_litterman(
            prices_df,
            views=views,
            risk_free_rate=0.02
        )

        print("\n--- Optimal Weights ---")
        for symbol, weight in result.weights.items():
            if weight > 0.001:
                print(f"  {symbol}: {weight:>8.2%}")

        print("\n--- Expected Performance ---")
        print(f"  Expected Return:  {result.expected_return:>8.2%}")
        print(f"  Volatility:       {result.volatility:>8.2%}")
        print(f"  Sharpe Ratio:     {result.sharpe_ratio:>8.2f}")

        return result

    except Exception as e:
        print(f"Error: {e}")
        return None


def example_efficient_frontier(prices_df):
    """Example: Generate efficient frontier."""
    print("\n" + "=" * 60)
    print("Example 5: Efficient Frontier")
    print("=" * 60)

    from core import PortfolioOptimizer

    optimizer = PortfolioOptimizer()

    print("\nGenerating efficient frontier...")
    try:
        frontier = optimizer.efficient_frontier(prices_df, n_points=10)

        print("\n--- Efficient Frontier Points ---")
        print(f"{'Return':<12} {'Volatility':<12} {'Sharpe':<10}")
        print("-" * 34)

        for point in frontier:
            print(f"{point['return']:<12.2%} {point['volatility']:<12.2%} {point['sharpe']:<10.2f}")

        return frontier

    except Exception as e:
        print(f"Error: {e}")
        return None


def example_discrete_allocation(prices_df):
    """Example: Convert weights to discrete share allocation."""
    print("\n" + "=" * 60)
    print("Example 6: Discrete Share Allocation")
    print("=" * 60)

    from core import PortfolioOptimizer

    optimizer = PortfolioOptimizer()
    total_capital = 100000

    print(f"\nTotal Capital: ${total_capital:,.2f}")
    print("\nStep 1: Get optimal weights...")

    try:
        result = optimizer.max_sharpe(prices_df, risk_free_rate=0.02)

        print("\nOptimal Weights:")
        for symbol, weight in result.weights.items():
            if weight > 0.001:
                print(f"  {symbol}: {weight:.2%}")

        print(f"\nStep 2: Convert to discrete allocation...")

        allocation = optimizer.discrete_allocation(
            result.weights,
            prices_df,
            total_capital
        )

        print("\n--- Discrete Allocation ---")
        print(f"{'Symbol':<8} {'Shares':<10} {'Value':<15} {'Weight':<10}")
        print("-" * 43)

        total_allocated = 0
        latest_prices = prices_df.iloc[-1]

        for symbol, shares in allocation.items():
            if shares > 0:
                value = shares * latest_prices[symbol]
                weight = value / total_capital
                total_allocated += value
                print(f"{symbol:<8} {shares:<10} ${value:<14,.2f} {weight:<10.2%}")

        remaining = total_capital - total_allocated
        print("-" * 43)
        print(f"{'Total':<8} {'':<10} ${total_allocated:<14,.2f}")
        print(f"{'Cash':<8} {'':<10} ${remaining:<14,.2f}")

        return allocation

    except Exception as e:
        print(f"Error: {e}")
        return None


def example_compare_methods(prices_df):
    """Example: Compare all optimization methods."""
    print("\n" + "=" * 60)
    print("Example 7: Compare Optimization Methods")
    print("=" * 60)

    from core import PortfolioOptimizer

    optimizer = PortfolioOptimizer()

    methods = {
        'Max Sharpe': lambda: optimizer.max_sharpe(prices_df, risk_free_rate=0.02),
        'Min Volatility': lambda: optimizer.min_volatility(prices_df),
        'Risk Parity': lambda: optimizer.risk_parity(prices_df),
        'Equal Weight': lambda: optimizer.equal_weight(prices_df),
    }

    results = []

    print("\nRunning all optimization methods...")
    for name, method_func in methods.items():
        try:
            result = method_func()
            results.append({
                'Method': name,
                'Return': result.expected_return,
                'Volatility': result.volatility,
                'Sharpe': result.sharpe_ratio
            })
            print(f"  {name}: Sharpe={result.sharpe_ratio:.2f}")
        except Exception as e:
            print(f"  {name}: Error - {e}")

    if results:
        print("\n--- Method Comparison ---")
        comparison_df = pd.DataFrame(results)
        comparison_df = comparison_df.set_index('Method')

        formatted = comparison_df.copy()
        formatted['Return'] = formatted['Return'].apply(lambda x: f"{x:.2%}")
        formatted['Volatility'] = formatted['Volatility'].apply(lambda x: f"{x:.2%}")
        formatted['Sharpe'] = formatted['Sharpe'].apply(lambda x: f"{x:.2f}")

        print(formatted.to_string())


def main():
    """Run all optimization examples."""
    print("\n" + "#" * 60)
    print("# Quantitative Trading Tool - Portfolio Optimization Examples")
    print("#" * 60)

    # Fetch data
    prices_df = fetch_portfolio_data()
    print(f"\nData shape: {prices_df.shape}")
    print(f"Assets: {list(prices_df.columns)}")
    print(f"Date range: {prices_df.index[0]} to {prices_df.index[-1]}")

    # Example 1: Max Sharpe
    example_max_sharpe(prices_df)

    # Example 2: Min Volatility
    example_min_volatility(prices_df)

    # Example 3: Risk Parity
    example_risk_parity(prices_df)

    # Example 4: Black-Litterman
    example_black_litterman(prices_df)

    # Example 5: Efficient Frontier
    example_efficient_frontier(prices_df)

    # Example 6: Discrete Allocation
    example_discrete_allocation(prices_df)

    # Example 7: Compare Methods
    example_compare_methods(prices_df)

    print("\n" + "#" * 60)
    print("# Portfolio optimization examples completed!")
    print("#" * 60)


if __name__ == "__main__":
    main()
