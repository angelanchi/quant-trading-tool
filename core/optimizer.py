# -*- coding: utf-8 -*-
"""
Portfolio optimization module.

This module provides portfolio optimization using PyPortfolioOpt with support for:
- Maximum Sharpe Ratio optimization
- Minimum Volatility optimization
- Risk Parity (Hierarchical Risk Parity)
- Black-Litterman model
- Efficient Frontier visualization

Classes:
    OptimizationResult: Results from optimization
    PortfolioOptimizer: Main optimization class

Usage:
    from core.optimizer import PortfolioOptimizer

    optimizer = PortfolioOptimizer(prices)
    result = optimizer.optimize('max_sharpe')
    print(result.weights)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import logging

import pandas as pd
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """
    Portfolio optimization results.

    Attributes:
        method: Optimization method used
        weights: Asset weights dictionary
        expected_return: Expected annual return
        expected_volatility: Expected annual volatility
        sharpe_ratio: Expected Sharpe ratio
        allocation: Discrete share allocation (optional)
        leftover: Leftover cash after discrete allocation
    """
    method: str
    weights: Dict[str, float]
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    allocation: Optional[Dict[str, int]] = None
    leftover: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'method': self.method,
            'weights': self.weights,
            'expected_return': self.expected_return,
            'expected_volatility': self.expected_volatility,
            'sharpe_ratio': self.sharpe_ratio,
            'allocation': self.allocation,
            'leftover': self.leftover,
        }

    def summary(self) -> str:
        """Generate text summary."""
        lines = [
            f"Portfolio Optimization Results",
            f"{'='*50}",
            f"Method: {self.method}",
            f"",
            f"Expected Performance:",
            f"  Return: {self.expected_return*100:.2f}%",
            f"  Volatility: {self.expected_volatility*100:.2f}%",
            f"  Sharpe Ratio: {self.sharpe_ratio:.2f}",
            f"",
            f"Weights:",
        ]

        for asset, weight in sorted(self.weights.items(), key=lambda x: -x[1]):
            if weight > 0.001:  # Only show weights > 0.1%
                lines.append(f"  {asset}: {weight*100:.2f}%")

        return '\n'.join(lines)


class PortfolioOptimizer:
    """
    Portfolio optimizer using PyPortfolioOpt.

    Supports multiple optimization methods:
    - max_sharpe: Maximize Sharpe ratio
    - min_volatility: Minimize portfolio volatility
    - efficient_risk: Maximize return for given risk
    - efficient_return: Minimize risk for given return
    - risk_parity: Equal risk contribution (HRP)
    - black_litterman: Black-Litterman model with views

    Attributes:
        prices: Historical price data
        risk_free_rate: Annual risk-free rate
        expected_returns: Calculated expected returns
        cov_matrix: Covariance matrix

    Example:
        optimizer = PortfolioOptimizer(prices)

        # Maximum Sharpe ratio
        result = optimizer.optimize('max_sharpe')

        # Minimum volatility with constraints
        result = optimizer.optimize(
            'min_volatility',
            weight_bounds=(0.05, 0.30)
        )
    """

    def __init__(
        self,
        prices: pd.DataFrame,
        risk_free_rate: float = 0.02
    ):
        """
        Initialize portfolio optimizer.

        Args:
            prices: Historical price data (columns = assets, index = dates)
            risk_free_rate: Annual risk-free rate (default 2%)
        """
        self.prices = prices
        self.risk_free_rate = risk_free_rate
        self.returns = prices.pct_change().dropna()

        # Calculate expected returns and covariance
        self._pypfopt_available = self._check_pypfopt()

        if self._pypfopt_available:
            self._calculate_inputs_pypfopt()
        else:
            self._calculate_inputs_fallback()

    def _check_pypfopt(self) -> bool:
        """Check if PyPortfolioOpt is available."""
        try:
            from pypfopt import expected_returns, risk_models
            return True
        except ImportError:
            logger.warning("PyPortfolioOpt not installed. Using fallback implementation.")
            return False

    def _calculate_inputs_pypfopt(self):
        """Calculate inputs using PyPortfolioOpt."""
        from pypfopt import expected_returns, risk_models

        # Mean historical return
        self.expected_returns = expected_returns.mean_historical_return(self.prices)

        # Ledoit-Wolf shrinkage covariance
        self.cov_matrix = risk_models.CovarianceShrinkage(self.prices).ledoit_wolf()

    def _calculate_inputs_fallback(self):
        """Calculate inputs using basic methods."""
        # Simple mean return (annualized)
        self.expected_returns = self.returns.mean() * 252

        # Sample covariance (annualized)
        self.cov_matrix = self.returns.cov() * 252

    def optimize(
        self,
        method: str = 'max_sharpe',
        target_return: Optional[float] = None,
        target_volatility: Optional[float] = None,
        weight_bounds: Tuple[float, float] = (0, 1),
        sector_mapper: Optional[Dict[str, str]] = None,
        sector_lower: Optional[Dict[str, float]] = None,
        sector_upper: Optional[Dict[str, float]] = None
    ) -> OptimizationResult:
        """
        Optimize portfolio weights.

        Args:
            method: Optimization method
                - 'max_sharpe': Maximum Sharpe ratio
                - 'min_volatility': Minimum volatility
                - 'efficient_risk': Max return for given volatility
                - 'efficient_return': Min volatility for given return
                - 'risk_parity': Hierarchical Risk Parity
            target_return: Target return for efficient_return
            target_volatility: Target volatility for efficient_risk
            weight_bounds: (min, max) weight bounds per asset
            sector_mapper: Asset to sector mapping
            sector_lower: Minimum weight per sector
            sector_upper: Maximum weight per sector

        Returns:
            OptimizationResult with weights and performance
        """
        if method == 'risk_parity':
            return self._optimize_risk_parity()

        if not self._pypfopt_available:
            return self._optimize_fallback(method, weight_bounds)

        return self._optimize_pypfopt(
            method,
            target_return,
            target_volatility,
            weight_bounds,
            sector_mapper,
            sector_lower,
            sector_upper
        )

    def _optimize_pypfopt(
        self,
        method: str,
        target_return: Optional[float],
        target_volatility: Optional[float],
        weight_bounds: Tuple[float, float],
        sector_mapper: Optional[Dict[str, str]],
        sector_lower: Optional[Dict[str, float]],
        sector_upper: Optional[Dict[str, float]]
    ) -> OptimizationResult:
        """Optimize using PyPortfolioOpt."""
        from pypfopt import EfficientFrontier

        # Create efficient frontier
        ef = EfficientFrontier(
            self.expected_returns,
            self.cov_matrix,
            weight_bounds=weight_bounds
        )

        # Add sector constraints if provided
        if sector_mapper and (sector_lower or sector_upper):
            ef.add_sector_constraints(
                sector_mapper,
                sector_lower or {},
                sector_upper or {}
            )

        # Optimize based on method
        if method == 'max_sharpe':
            weights = ef.max_sharpe(risk_free_rate=self.risk_free_rate)
        elif method == 'min_volatility':
            weights = ef.min_volatility()
        elif method == 'efficient_risk':
            if target_volatility is None:
                raise ValueError("target_volatility required for efficient_risk")
            weights = ef.efficient_risk(target_volatility)
        elif method == 'efficient_return':
            if target_return is None:
                raise ValueError("target_return required for efficient_return")
            weights = ef.efficient_return(target_return)
        else:
            raise ValueError(f"Unknown optimization method: {method}")

        # Clean weights
        cleaned_weights = ef.clean_weights()

        # Get performance
        expected_return, volatility, sharpe = ef.portfolio_performance(
            risk_free_rate=self.risk_free_rate
        )

        return OptimizationResult(
            method=method,
            weights=dict(cleaned_weights),
            expected_return=expected_return,
            expected_volatility=volatility,
            sharpe_ratio=sharpe
        )

    def _optimize_fallback(
        self,
        method: str,
        weight_bounds: Tuple[float, float]
    ) -> OptimizationResult:
        """Fallback optimization without PyPortfolioOpt."""
        from scipy.optimize import minimize

        n_assets = len(self.expected_returns)
        init_weights = np.ones(n_assets) / n_assets

        # Portfolio return
        def portfolio_return(weights):
            return np.dot(weights, self.expected_returns)

        # Portfolio volatility
        def portfolio_volatility(weights):
            return np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix.values, weights)))

        # Sharpe ratio (negative for minimization)
        def neg_sharpe(weights):
            ret = portfolio_return(weights)
            vol = portfolio_volatility(weights)
            return -(ret - self.risk_free_rate) / vol

        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}  # Weights sum to 1
        ]

        # Bounds
        bounds = tuple((weight_bounds[0], weight_bounds[1]) for _ in range(n_assets))

        # Optimize
        if method == 'max_sharpe':
            result = minimize(neg_sharpe, init_weights, method='SLSQP',
                            bounds=bounds, constraints=constraints)
        elif method == 'min_volatility':
            result = minimize(portfolio_volatility, init_weights, method='SLSQP',
                            bounds=bounds, constraints=constraints)
        else:
            # Default to max sharpe
            result = minimize(neg_sharpe, init_weights, method='SLSQP',
                            bounds=bounds, constraints=constraints)

        weights = result.x
        weights = np.maximum(weights, 0)  # Ensure non-negative
        weights = weights / weights.sum()  # Normalize

        # Calculate performance
        ret = portfolio_return(weights)
        vol = portfolio_volatility(weights)
        sharpe = (ret - self.risk_free_rate) / vol

        weights_dict = dict(zip(self.expected_returns.index, weights))

        return OptimizationResult(
            method=method,
            weights=weights_dict,
            expected_return=ret,
            expected_volatility=vol,
            sharpe_ratio=sharpe
        )

    def _optimize_risk_parity(self) -> OptimizationResult:
        """
        Hierarchical Risk Parity optimization.

        Uses hierarchical clustering to build a diversified portfolio
        with equal risk contribution.
        """
        if self._pypfopt_available:
            try:
                from pypfopt import HRPOpt

                hrp = HRPOpt(self.returns)
                weights = hrp.optimize()
                cleaned_weights = hrp.clean_weights()

                # Calculate performance
                perf = hrp.portfolio_performance(
                    risk_free_rate=self.risk_free_rate
                )

                return OptimizationResult(
                    method='risk_parity',
                    weights=dict(cleaned_weights),
                    expected_return=perf[0],
                    expected_volatility=perf[1],
                    sharpe_ratio=perf[2]
                )
            except Exception as e:
                logger.warning(f"HRP failed, using fallback: {e}")

        # Fallback: inverse volatility weighting
        return self._risk_parity_fallback()

    def _risk_parity_fallback(self) -> OptimizationResult:
        """Simple risk parity using inverse volatility."""
        # Calculate individual volatilities
        volatilities = self.returns.std() * np.sqrt(252)

        # Inverse volatility weights
        inv_vol = 1 / volatilities
        weights = inv_vol / inv_vol.sum()

        weights_dict = dict(zip(self.returns.columns, weights))

        # Calculate portfolio performance
        ret = np.dot(weights, self.expected_returns)
        vol = np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix.values, weights)))
        sharpe = (ret - self.risk_free_rate) / vol

        return OptimizationResult(
            method='risk_parity',
            weights=weights_dict,
            expected_return=ret,
            expected_volatility=vol,
            sharpe_ratio=sharpe
        )

    def optimize_black_litterman(
        self,
        market_caps: Dict[str, float],
        views: Dict[str, float],
        view_confidences: Optional[List[float]] = None,
        delta: float = 2.5,
        tau: float = 0.025
    ) -> OptimizationResult:
        """
        Black-Litterman optimization with investor views.

        Combines market equilibrium returns with subjective views
        using Bayesian inference.

        Args:
            market_caps: Market capitalization for each asset
            views: Absolute views on expected returns {'AAPL': 0.15, ...}
            view_confidences: Confidence in each view (0-1)
            delta: Risk aversion coefficient
            tau: Uncertainty scaling factor

        Returns:
            OptimizationResult with Black-Litterman weights

        Example:
            market_caps = {'AAPL': 3e12, 'MSFT': 2.5e12, 'GOOGL': 1.8e12}
            views = {'AAPL': 0.15, 'MSFT': 0.10}  # Expected 15% and 10% return
            result = optimizer.optimize_black_litterman(market_caps, views)
        """
        if not self._pypfopt_available:
            logger.warning("Black-Litterman requires PyPortfolioOpt")
            return self.optimize('max_sharpe')

        from pypfopt import black_litterman, BlackLittermanModel, EfficientFrontier

        # Calculate market-implied prior returns
        prior = black_litterman.market_implied_prior_returns(
            market_caps,
            delta,
            self.cov_matrix
        )

        # Create Black-Litterman model
        bl = BlackLittermanModel(
            self.cov_matrix,
            pi=prior,
            absolute_views=views,
            omega='idzorek' if view_confidences else 'default',
            view_confidences=view_confidences
        )

        # Get posterior estimates
        posterior_returns = bl.bl_returns()
        posterior_cov = bl.bl_cov()

        # Optimize with posterior estimates
        ef = EfficientFrontier(posterior_returns, posterior_cov)
        weights = ef.max_sharpe(risk_free_rate=self.risk_free_rate)
        cleaned_weights = ef.clean_weights()

        expected_return, volatility, sharpe = ef.portfolio_performance(
            risk_free_rate=self.risk_free_rate
        )

        return OptimizationResult(
            method='black_litterman',
            weights=dict(cleaned_weights),
            expected_return=expected_return,
            expected_volatility=volatility,
            sharpe_ratio=sharpe
        )

    def get_discrete_allocation(
        self,
        weights: Dict[str, float],
        total_value: float
    ) -> Tuple[Dict[str, int], float]:
        """
        Convert weights to discrete share allocation.

        Args:
            weights: Asset weights
            total_value: Total portfolio value

        Returns:
            Tuple of (share allocation dict, leftover cash)
        """
        if self._pypfopt_available:
            from pypfopt.discrete_allocation import DiscreteAllocation

            latest_prices = self.prices.iloc[-1]
            da = DiscreteAllocation(weights, latest_prices, total_portfolio_value=total_value)
            allocation, leftover = da.greedy_portfolio()
            return allocation, leftover

        # Fallback
        latest_prices = self.prices.iloc[-1]
        allocation = {}
        remaining = total_value

        for asset, weight in sorted(weights.items(), key=lambda x: -x[1]):
            if weight < 0.001:
                continue
            target_value = total_value * weight
            price = latest_prices[asset]
            shares = int(target_value / price)
            if shares > 0:
                allocation[asset] = shares
                remaining -= shares * price

        return allocation, remaining

    def get_efficient_frontier(
        self,
        n_points: int = 100
    ) -> pd.DataFrame:
        """
        Calculate points on the efficient frontier.

        Args:
            n_points: Number of points to calculate

        Returns:
            DataFrame with columns: return, volatility, sharpe
        """
        if not self._pypfopt_available:
            return self._efficient_frontier_fallback(n_points)

        from pypfopt import EfficientFrontier

        # Get min and max returns
        ef_min = EfficientFrontier(self.expected_returns, self.cov_matrix)
        ef_min.min_volatility()
        min_ret, min_vol, _ = ef_min.portfolio_performance()

        ef_max = EfficientFrontier(self.expected_returns, self.cov_matrix)
        ef_max.max_sharpe()
        max_ret, _, _ = ef_max.portfolio_performance()

        # Generate frontier points
        target_returns = np.linspace(min_ret, max_ret * 1.1, n_points)
        frontier_points = []

        for target in target_returns:
            try:
                ef = EfficientFrontier(self.expected_returns, self.cov_matrix)
                ef.efficient_return(target)
                ret, vol, sharpe = ef.portfolio_performance(
                    risk_free_rate=self.risk_free_rate
                )
                frontier_points.append({
                    'return': ret,
                    'volatility': vol,
                    'sharpe': sharpe
                })
            except:
                continue

        return pd.DataFrame(frontier_points)

    def _efficient_frontier_fallback(self, n_points: int) -> pd.DataFrame:
        """Calculate efficient frontier without PyPortfolioOpt."""
        from scipy.optimize import minimize

        n_assets = len(self.expected_returns)

        # Get return range.
        # The efficient frontier starts at the minimum-variance portfolio,
        # not at the lowest single-asset return (points below it are dominated).
        cov = self.cov_matrix.values
        mv = minimize(
            lambda w: float(np.sqrt(w @ cov @ w)),
            np.ones(n_assets) / n_assets,
            method='SLSQP',
            bounds=tuple((0, 1) for _ in range(n_assets)),
            constraints=[{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}],
        )
        min_ret = float(np.dot(mv.x, self.expected_returns)) if mv.success else self.expected_returns.min()
        max_ret = self.expected_returns.max()
        target_returns = np.linspace(min_ret, max_ret, n_points)

        def portfolio_volatility(weights):
            return np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix.values, weights)))

        frontier_points = []
        init_weights = np.ones(n_assets) / n_assets

        for target in target_returns:
            constraints = [
                {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
                {'type': 'eq', 'fun': lambda x: np.dot(x, self.expected_returns) - target}
            ]
            bounds = tuple((0, 1) for _ in range(n_assets))

            try:
                result = minimize(
                    portfolio_volatility,
                    init_weights,
                    method='SLSQP',
                    bounds=bounds,
                    constraints=constraints
                )
                if result.success:
                    vol = result.fun
                    sharpe = (target - self.risk_free_rate) / vol
                    frontier_points.append({
                        'return': target,
                        'volatility': vol,
                        'sharpe': sharpe
                    })
            except:
                continue

        return pd.DataFrame(frontier_points)

    def get_asset_stats(self) -> pd.DataFrame:
        """
        Get statistics for each asset.

        Returns:
            DataFrame with expected return, volatility, and Sharpe for each asset
        """
        volatilities = self.returns.std() * np.sqrt(252)
        sharpes = (self.expected_returns - self.risk_free_rate) / volatilities

        return pd.DataFrame({
            'expected_return': self.expected_returns,
            'volatility': volatilities,
            'sharpe': sharpes
        })

    def get_correlation_matrix(self) -> pd.DataFrame:
        """Get correlation matrix of asset returns."""
        return self.returns.corr()


# =============================================================================
# Convenience Functions
# =============================================================================

def optimize_portfolio(
    prices: pd.DataFrame,
    method: str = 'max_sharpe',
    risk_free_rate: float = 0.02,
    **kwargs
) -> OptimizationResult:
    """
    Convenience function for portfolio optimization.

    Args:
        prices: Historical price data
        method: Optimization method
        risk_free_rate: Risk-free rate
        **kwargs: Additional arguments for optimize()

    Returns:
        OptimizationResult
    """
    optimizer = PortfolioOptimizer(prices, risk_free_rate)
    return optimizer.optimize(method, **kwargs)


def equal_weight_portfolio(symbols: List[str]) -> Dict[str, float]:
    """
    Generate equal weight portfolio.

    Args:
        symbols: List of asset symbols

    Returns:
        Equal weights dictionary
    """
    weight = 1.0 / len(symbols)
    return {symbol: weight for symbol in symbols}
