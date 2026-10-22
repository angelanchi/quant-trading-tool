# -*- coding: utf-8 -*-
"""
Risk calculation module.

This module provides comprehensive risk metrics calculation including:
- Value at Risk (VaR) - Historical, Parametric, Monte Carlo
- Conditional VaR (CVaR / Expected Shortfall)
- Sharpe, Sortino, Calmar ratios
- Maximum drawdown analysis
- Portfolio risk decomposition

Classes:
    RiskMetrics: Container for risk metrics
    RiskCalculator: Main risk calculation class
    PortfolioRiskDecomposition: Risk contribution analysis

Usage:
    from core.risk import RiskCalculator

    calc = RiskCalculator(returns)
    metrics = calc.calculate_all()
    print(f"VaR 95%: {metrics.var_95_historical:.2%}")
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Union, Tuple
import logging

import pandas as pd
import numpy as np
from scipy import stats

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class RiskMetrics:
    """
    Container for all risk metrics.

    Attributes grouped by category:
    - Return metrics: total_return, cagr
    - Volatility metrics: volatility, downside_deviation
    - Risk-adjusted returns: sharpe_ratio, sortino_ratio, calmar_ratio
    - Drawdown metrics: max_drawdown, avg_drawdown, max_drawdown_duration
    - VaR metrics: var_95_historical, var_99_historical, var_95_parametric, cvar_95
    - Distribution: skewness, kurtosis, positive_days_ratio
    """
    # Return metrics
    total_return: float
    cagr: float

    # Volatility metrics
    volatility: float
    downside_deviation: float

    # Risk-adjusted returns
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float

    # Drawdown metrics
    max_drawdown: float
    avg_drawdown: float
    max_drawdown_duration: int  # Days

    # VaR metrics
    var_95_historical: float
    var_99_historical: float
    var_95_parametric: float
    cvar_95: float

    # Distribution
    skewness: float
    kurtosis: float
    positive_days_ratio: float

    # Optional metrics (有預設值的欄位必須放最後，Python 3.13 要求)
    information_ratio: Optional[float] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'total_return': self.total_return,
            'cagr': self.cagr,
            'volatility': self.volatility,
            'downside_deviation': self.downside_deviation,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'calmar_ratio': self.calmar_ratio,
            'information_ratio': self.information_ratio,
            'max_drawdown': self.max_drawdown,
            'avg_drawdown': self.avg_drawdown,
            'max_drawdown_duration': self.max_drawdown_duration,
            'var_95_historical': self.var_95_historical,
            'var_99_historical': self.var_99_historical,
            'var_95_parametric': self.var_95_parametric,
            'cvar_95': self.cvar_95,
            'skewness': self.skewness,
            'kurtosis': self.kurtosis,
            'positive_days_ratio': self.positive_days_ratio,
        }

    def summary(self) -> str:
        """Generate text summary."""
        return f"""
Risk Metrics Summary
{'='*50}

Returns:
  Total Return: {self.total_return*100:.2f}%
  CAGR: {self.cagr*100:.2f}%

Risk:
  Volatility: {self.volatility*100:.2f}%
  Downside Deviation: {self.downside_deviation*100:.2f}%
  Max Drawdown: {self.max_drawdown*100:.2f}%
  Avg Drawdown: {self.avg_drawdown*100:.2f}%
  Max DD Duration: {self.max_drawdown_duration} days

Risk-Adjusted Returns:
  Sharpe Ratio: {self.sharpe_ratio:.2f}
  Sortino Ratio: {self.sortino_ratio:.2f}
  Calmar Ratio: {self.calmar_ratio:.2f}

Value at Risk:
  VaR 95% (Historical): {self.var_95_historical*100:.2f}%
  VaR 99% (Historical): {self.var_99_historical*100:.2f}%
  VaR 95% (Parametric): {self.var_95_parametric*100:.2f}%
  CVaR 95%: {self.cvar_95*100:.2f}%

Distribution:
  Skewness: {self.skewness:.2f}
  Kurtosis: {self.kurtosis:.2f}
  Positive Days: {self.positive_days_ratio*100:.1f}%
"""


class RiskCalculator:
    """
    Comprehensive risk metrics calculator.

    Calculates various risk metrics from a return series including
    VaR, CVaR, Sharpe ratio, and drawdown analysis.

    Attributes:
        returns: Return series
        risk_free_rate: Annual risk-free rate
        periods: Periods per year (252 for daily)

    Example:
        returns = prices.pct_change().dropna()
        calc = RiskCalculator(returns)
        metrics = calc.calculate_all()
    """

    def __init__(
        self,
        returns: pd.Series,
        risk_free_rate: float = 0.02,
        periods_per_year: int = 252
    ):
        """
        Initialize risk calculator.

        Args:
            returns: Return series (daily returns)
            risk_free_rate: Annual risk-free rate
            periods_per_year: Trading periods per year (252 for daily)
        """
        self.returns = returns.dropna()
        self.risk_free_rate = risk_free_rate
        self.periods = periods_per_year

    def calculate_all(self) -> RiskMetrics:
        """
        Calculate all risk metrics.

        Returns:
            RiskMetrics dataclass with all metrics
        """
        return RiskMetrics(
            total_return=self.total_return(),
            cagr=self.cagr(),
            volatility=self.volatility(),
            downside_deviation=self.downside_deviation(),
            sharpe_ratio=self.sharpe_ratio(),
            sortino_ratio=self.sortino_ratio(),
            calmar_ratio=self.calmar_ratio(),
            max_drawdown=self.max_drawdown(),
            avg_drawdown=self.average_drawdown(),
            max_drawdown_duration=self.max_drawdown_duration(),
            var_95_historical=self.var_historical(0.95),
            var_99_historical=self.var_historical(0.99),
            var_95_parametric=self.var_parametric(0.95),
            cvar_95=self.cvar(0.95),
            skewness=self.skewness(),
            kurtosis=self.kurtosis(),
            positive_days_ratio=self.positive_days_ratio()
        )

    # =========================================================================
    # Return Metrics
    # =========================================================================

    def total_return(self) -> float:
        """
        Calculate total cumulative return.

        Formula: (1 + r1) * (1 + r2) * ... * (1 + rn) - 1
        """
        return (1 + self.returns).prod() - 1

    def cagr(self) -> float:
        """
        Calculate Compound Annual Growth Rate.

        Formula: (1 + total_return)^(1/years) - 1
        """
        total_return = self.total_return()
        n_years = len(self.returns) / self.periods

        if n_years <= 0 or total_return <= -1:
            return 0.0

        return (1 + total_return) ** (1 / n_years) - 1

    # =========================================================================
    # Volatility Metrics
    # =========================================================================

    def volatility(self) -> float:
        """
        Calculate annualized volatility.

        Formula: std(returns) * sqrt(periods_per_year)
        """
        return self.returns.std() * np.sqrt(self.periods)

    def downside_deviation(self, mar: float = 0) -> float:
        """
        Calculate downside deviation (semi-deviation).

        Only considers returns below the minimum acceptable return (MAR).

        Args:
            mar: Minimum acceptable return (default 0)

        Formula: sqrt(mean((returns - mar)^2)) for returns < mar
        """
        # Semi-deviation around MAR over ALL periods (Sortino & van der Meer).
        # Old version used std() of negative returns only, which de-means the
        # tail and understates downside risk.
        shortfall = np.minimum(self.returns - mar, 0.0)
        if len(shortfall) == 0:
            return 0.0
        return float(np.sqrt(np.mean(shortfall ** 2)) * np.sqrt(self.periods))

    # =========================================================================
    # Risk-Adjusted Return Metrics
    # =========================================================================

    def sharpe_ratio(self) -> float:
        """
        Calculate Sharpe Ratio.

        Formula: (mean(r) * periods - rf) / volatility

        Interpretation:
        - > 1: Good
        - > 2: Very good
        - > 3: Excellent
        """
        vol = self.volatility()
        if vol == 0:
            return 0.0

        # Standard (CQF / Sharpe 1994) definition: annualised arithmetic mean
        # excess return divided by annualised volatility.
        excess_mean = self.returns.mean() * self.periods - self.risk_free_rate
        return float(excess_mean / vol)

    def sortino_ratio(self) -> float:
        """
        Calculate Sortino Ratio.

        Like Sharpe but only penalizes downside volatility.

        Formula: (mean(r) * periods - rf) / downside_deviation
        """
        downside = self.downside_deviation()
        if downside == 0:
            return 0.0

        return float((self.returns.mean() * self.periods - self.risk_free_rate) / downside)

    def calmar_ratio(self) -> float:
        """
        Calculate Calmar Ratio.

        Measures return relative to maximum drawdown.

        Formula: CAGR / |max_drawdown|
        """
        max_dd = abs(self.max_drawdown())
        if max_dd == 0:
            return 0.0

        return self.cagr() / max_dd

    def information_ratio(self, benchmark_returns: pd.Series) -> float:
        """
        Calculate Information Ratio.

        Measures excess return per unit of tracking error.

        Args:
            benchmark_returns: Benchmark return series

        Formula: mean(active_returns) / std(active_returns)
        """
        # Align indices
        common_idx = self.returns.index.intersection(benchmark_returns.index)
        active_returns = self.returns[common_idx] - benchmark_returns[common_idx]

        tracking_error = active_returns.std() * np.sqrt(self.periods)
        active_return = active_returns.mean() * self.periods

        if tracking_error == 0:
            return 0.0

        return active_return / tracking_error

    # =========================================================================
    # Drawdown Metrics
    # =========================================================================

    def drawdown_series(self) -> pd.Series:
        """
        Calculate drawdown series.

        Returns:
            Series of drawdowns (negative values)
        """
        cumulative = (1 + self.returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        return drawdown

    def max_drawdown(self) -> float:
        """
        Calculate maximum drawdown.

        The largest peak-to-trough decline.
        """
        return self.drawdown_series().min()

    def average_drawdown(self) -> float:
        """Calculate average drawdown (when in drawdown)."""
        dd = self.drawdown_series()
        dd_periods = dd[dd < 0]

        if len(dd_periods) == 0:
            return 0.0

        return dd_periods.mean()

    def max_drawdown_duration(self) -> int:
        """
        Calculate maximum drawdown duration in periods.

        The longest time spent in a drawdown.
        """
        dd = self.drawdown_series()
        is_in_drawdown = dd < 0

        if not is_in_drawdown.any():
            return 0

        # Find consecutive drawdown periods
        durations = []
        current_duration = 0

        for in_dd in is_in_drawdown:
            if in_dd:
                current_duration += 1
            else:
                if current_duration > 0:
                    durations.append(current_duration)
                current_duration = 0

        if current_duration > 0:
            durations.append(current_duration)

        return max(durations) if durations else 0

    def underwater_periods(self) -> pd.DataFrame:
        """
        Get detailed underwater (drawdown) periods.

        Returns:
            DataFrame with start, end, duration, and depth of each drawdown
        """
        dd = self.drawdown_series()
        is_in_drawdown = dd < 0

        periods = []
        start = None
        min_dd = 0

        for i, (idx, in_dd) in enumerate(is_in_drawdown.items()):
            if in_dd and start is None:
                start = idx
                min_dd = dd[idx]
            elif in_dd:
                min_dd = min(min_dd, dd[idx])
            elif start is not None:
                periods.append({
                    'start': start,
                    'end': idx,
                    'duration': i - list(is_in_drawdown.index).index(start),
                    'depth': min_dd
                })
                start = None
                min_dd = 0

        return pd.DataFrame(periods)

    # =========================================================================
    # Value at Risk (VaR)
    # =========================================================================

    def var_historical(self, confidence: float = 0.95) -> float:
        """
        Calculate VaR using historical simulation.

        Args:
            confidence: Confidence level (e.g., 0.95 for 95%)

        Returns:
            VaR value (negative = loss)

        Formula: percentile(returns, (1-confidence)*100)
        """
        return np.percentile(self.returns, (1 - confidence) * 100)

    def var_parametric(self, confidence: float = 0.95) -> float:
        """
        Calculate VaR using parametric method (assuming normal distribution).

        Args:
            confidence: Confidence level

        Returns:
            VaR value

        Formula: mean - z * std
        Where z is the standard normal quantile
        """
        mu = self.returns.mean()
        sigma = self.returns.std()
        return stats.norm.ppf(1 - confidence, mu, sigma)

    def var_monte_carlo(
        self,
        confidence: float = 0.95,
        n_simulations: int = 10000,
        holding_period: int = 1
    ) -> float:
        """
        Calculate VaR using Monte Carlo simulation.

        Args:
            confidence: Confidence level
            n_simulations: Number of simulations
            holding_period: Holding period in days

        Returns:
            VaR value
        """
        mu = self.returns.mean()
        sigma = self.returns.std()

        # Simulate returns
        simulated = np.random.normal(
            mu * holding_period,
            sigma * np.sqrt(holding_period),
            n_simulations
        )

        return np.percentile(simulated, (1 - confidence) * 100)

    def cvar(self, confidence: float = 0.95) -> float:
        """
        Calculate Conditional VaR (Expected Shortfall).

        The expected loss given that the loss exceeds VaR.

        Args:
            confidence: Confidence level

        Returns:
            CVaR value (expected loss in tail)

        Formula: E[Loss | Loss > VaR]
        """
        var = self.var_historical(confidence)
        tail_losses = self.returns[self.returns <= var]

        if len(tail_losses) == 0:
            return var

        return tail_losses.mean()

    # =========================================================================
    # Distribution Metrics
    # =========================================================================

    def skewness(self) -> float:
        """
        Calculate return distribution skewness.

        Negative skew = left tail (large losses more likely)
        Positive skew = right tail (large gains more likely)
        """
        return stats.skew(self.returns)

    def kurtosis(self) -> float:
        """
        Calculate return distribution kurtosis (excess).

        High kurtosis = fat tails (extreme events more likely)
        Normal distribution has excess kurtosis of 0
        """
        return stats.kurtosis(self.returns)

    def positive_days_ratio(self) -> float:
        """Calculate ratio of positive return days."""
        return (self.returns > 0).sum() / len(self.returns)

    def return_distribution(self, bins: int = 50) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get return distribution histogram data.

        Args:
            bins: Number of histogram bins

        Returns:
            Tuple of (counts, bin_edges)
        """
        return np.histogram(self.returns, bins=bins)


class PortfolioRiskDecomposition:
    """
    Portfolio risk decomposition analysis.

    Decomposes portfolio risk into contributions from each asset.

    Attributes:
        returns: Asset returns DataFrame
        weights: Portfolio weights

    Example:
        decomp = PortfolioRiskDecomposition(returns, weights)
        contrib = decomp.percent_risk_contribution()
    """

    def __init__(
        self,
        returns: pd.DataFrame,
        weights: Dict[str, float]
    ):
        """
        Initialize risk decomposition.

        Args:
            returns: Asset returns DataFrame (columns = assets)
            weights: Portfolio weights dictionary
        """
        self.returns = returns
        self.weights = pd.Series(weights)
        self.cov_matrix = returns.cov() * 252  # Annualized

    def portfolio_variance(self) -> float:
        """Calculate portfolio variance."""
        w = self.weights.values
        cov = self.cov_matrix.values
        return np.dot(w.T, np.dot(cov, w))

    def portfolio_volatility(self) -> float:
        """Calculate portfolio volatility (standard deviation)."""
        return np.sqrt(self.portfolio_variance())

    def marginal_risk_contribution(self) -> pd.Series:
        """
        Calculate Marginal Risk Contribution (MRC).

        The change in portfolio risk from a small change in weight.

        Formula: (Cov * w) / portfolio_vol
        """
        w = self.weights.values
        cov = self.cov_matrix.values
        port_vol = self.portfolio_volatility()

        mrc = np.dot(cov, w) / port_vol
        return pd.Series(mrc, index=self.weights.index, name='MRC')

    def component_risk_contribution(self) -> pd.Series:
        """
        Calculate Component Risk Contribution (CRC).

        The absolute risk contribution of each asset.

        Formula: weight * MRC
        """
        mrc = self.marginal_risk_contribution()
        crc = self.weights * mrc
        return crc.rename('CRC')

    def percent_risk_contribution(self) -> pd.Series:
        """
        Calculate Percent Risk Contribution (PRC).

        The percentage of total risk from each asset.

        Formula: CRC / sum(CRC) * 100
        """
        crc = self.component_risk_contribution()
        return (crc / crc.sum() * 100).rename('PRC%')

    def diversification_ratio(self) -> float:
        """
        Calculate diversification ratio.

        Ratio of weighted average volatility to portfolio volatility.
        Higher = more diversified.

        Formula: sum(w * vol) / portfolio_vol
        """
        individual_vols = np.sqrt(np.diag(self.cov_matrix.values))
        weighted_avg_vol = np.dot(self.weights.values, individual_vols)
        return weighted_avg_vol / self.portfolio_volatility()

    def correlation_contribution(self) -> pd.DataFrame:
        """
        Calculate correlation contribution matrix.

        Shows how correlation between assets contributes to portfolio risk.
        """
        corr_matrix = self.returns.corr()
        vol = np.sqrt(np.diag(self.cov_matrix.values))

        contrib = pd.DataFrame(
            index=self.weights.index,
            columns=self.weights.index,
            dtype=float
        )

        for i, asset_i in enumerate(self.weights.index):
            for j, asset_j in enumerate(self.weights.index):
                contrib.loc[asset_i, asset_j] = (
                    self.weights[asset_i] *
                    self.weights[asset_j] *
                    vol[i] * vol[j] *
                    corr_matrix.loc[asset_i, asset_j]
                )

        return contrib

    def risk_budget_optimization_target(self, target_contrib: Dict[str, float]) -> float:
        """
        Calculate how far current allocation is from target risk budget.

        Args:
            target_contrib: Target risk contribution per asset (should sum to 1)

        Returns:
            Sum of squared deviations from target
        """
        actual = self.percent_risk_contribution() / 100
        target = pd.Series(target_contrib)

        return ((actual - target) ** 2).sum()


# =============================================================================
# Convenience Functions
# =============================================================================

def calculate_var(
    returns: pd.Series,
    confidence: float = 0.95,
    method: str = 'historical'
) -> float:
    """
    Calculate Value at Risk.

    Args:
        returns: Return series
        confidence: Confidence level
        method: 'historical', 'parametric', or 'monte_carlo'

    Returns:
        VaR value
    """
    calc = RiskCalculator(returns)

    if method == 'historical':
        return calc.var_historical(confidence)
    elif method == 'parametric':
        return calc.var_parametric(confidence)
    elif method == 'monte_carlo':
        return calc.var_monte_carlo(confidence)
    else:
        raise ValueError(f"Unknown VaR method: {method}")


def calculate_sharpe(
    returns: pd.Series,
    risk_free_rate: float = 0.02
) -> float:
    """
    Calculate Sharpe ratio.

    Args:
        returns: Return series
        risk_free_rate: Annual risk-free rate

    Returns:
        Sharpe ratio
    """
    calc = RiskCalculator(returns, risk_free_rate)
    return calc.sharpe_ratio()


def calculate_max_drawdown(returns: pd.Series) -> float:
    """
    Calculate maximum drawdown.

    Args:
        returns: Return series

    Returns:
        Maximum drawdown (negative value)
    """
    calc = RiskCalculator(returns)
    return calc.max_drawdown()
