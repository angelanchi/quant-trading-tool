# -*- coding: utf-8 -*-
"""
Pytest configuration and fixtures.

This module provides shared fixtures for all test modules.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def sample_prices():
    """Generate sample price data for testing."""
    np.random.seed(42)
    dates = pd.date_range(start='2022-01-01', periods=252, freq='B')

    # Generate random walk prices
    returns = np.random.normal(0.0005, 0.02, len(dates))
    prices = 100 * np.exp(np.cumsum(returns))

    return pd.Series(prices, index=dates, name='close')


@pytest.fixture
def sample_ohlcv():
    """Generate sample OHLCV data for testing."""
    np.random.seed(42)
    dates = pd.date_range(start='2022-01-01', periods=252, freq='B')

    # Generate random walk prices
    returns = np.random.normal(0.0005, 0.02, len(dates))
    close = 100 * np.exp(np.cumsum(returns))

    # Generate OHLCV
    high = close * (1 + np.abs(np.random.normal(0, 0.01, len(dates))))
    low = close * (1 - np.abs(np.random.normal(0, 0.01, len(dates))))
    open_price = low + (high - low) * np.random.random(len(dates))
    volume = np.random.randint(100000, 1000000, len(dates))

    return pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)


@pytest.fixture
def sample_returns():
    """Generate sample return data for testing."""
    np.random.seed(42)
    dates = pd.date_range(start='2022-01-01', periods=252, freq='B')
    returns = np.random.normal(0.0005, 0.02, len(dates))
    return pd.Series(returns, index=dates, name='returns')


@pytest.fixture
def sample_multi_asset_prices():
    """Generate sample multi-asset price data for testing."""
    np.random.seed(42)
    dates = pd.date_range(start='2022-01-01', periods=252, freq='B')

    # Generate correlated returns for 5 assets
    n_assets = 5
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']

    # Correlation matrix
    corr = np.array([
        [1.0, 0.7, 0.5, 0.4, 0.6],
        [0.7, 1.0, 0.6, 0.5, 0.5],
        [0.5, 0.6, 1.0, 0.4, 0.4],
        [0.4, 0.5, 0.4, 1.0, 0.3],
        [0.6, 0.5, 0.4, 0.3, 1.0]
    ])

    # Generate correlated returns using Cholesky decomposition
    L = np.linalg.cholesky(corr)
    uncorrelated = np.random.normal(0.0005, 0.02, (len(dates), n_assets))
    correlated_returns = uncorrelated @ L.T

    # Convert to prices
    prices_dict = {}
    for i, symbol in enumerate(symbols):
        prices_dict[symbol] = 100 * np.exp(np.cumsum(correlated_returns[:, i]))

    return pd.DataFrame(prices_dict, index=dates)


@pytest.fixture
def sample_portfolio_weights():
    """Generate sample portfolio weights."""
    return {
        'AAPL': 0.25,
        'MSFT': 0.25,
        'GOOGL': 0.20,
        'AMZN': 0.15,
        'META': 0.15
    }


@pytest.fixture
def sample_cointegrated_pair():
    """Generate sample cointegrated price pair for pairs trading tests."""
    np.random.seed(42)
    dates = pd.date_range(start='2022-01-01', periods=252, freq='B')

    # Generate cointegrated pair
    # X follows random walk
    x_returns = np.random.normal(0.0003, 0.015, len(dates))
    x = 100 * np.exp(np.cumsum(x_returns))

    # Y = beta * X + stationary noise (cointegrated with X)
    beta = 1.2
    stationary_noise = np.zeros(len(dates))
    for i in range(1, len(dates)):
        # Mean-reverting process
        stationary_noise[i] = 0.9 * stationary_noise[i-1] + np.random.normal(0, 2)

    y = beta * x + stationary_noise + 20  # Add offset

    return pd.DataFrame({
        'X': x,
        'Y': y
    }, index=dates)
