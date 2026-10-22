# -*- coding: utf-8 -*-
"""
Risk analysis example for quantitative trading tool.

Demonstrates:
- VaR calculation (Historical, Parametric, Monte Carlo)
- CVaR / Expected Shortfall
- Performance ratios (Sharpe, Sortino, Calmar)
- Drawdown analysis
- Risk decomposition

Usage:
    python examples/risk_analysis_example.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np


def fetch_returns_data():
    """Fetch data and calculate returns."""
    from core import DataManager

    dm = DataManager()

    print("Fetching price data...")
    try:
        df = dm.fetch_ohlcv('AAPL', '2022-01-01', '2023-12-31')
        if df is not None and not df.empty:
            returns = df['close'].pct_change().dropna()
            print(f"  AAPL: {len(returns)} daily returns")
            return returns
    except Exception as e:
        print(f"  Error: {e}")

    print("Using synthetic data for demonstration")
    np.random.seed(42)
    dates = pd.date_range(start='2022-01-01', end='2023-12-31', freq='B')
    returns = pd.Series(
        np.random.normal(0.0005, 0.02, len(dates)),
        index=dates,
        name='returns'
    )
    return returns


def example_var_calculation(returns):
    """Example: VaR calculation methods."""
    print("\n" + "=" * 60)
    print("Example 1: Value at Risk (VaR)")
    print("=" * 60)

    from core import RiskCalculator

    calc = RiskCalculator(returns, risk_free_rate=0.02)

    confidence_levels = [0.90, 0.95, 0.99]

    print("\n--- Historical VaR ---")
    print("(Based on historical return distribution)")
    print(f"{'Confidence':<12} {'VaR':<12} {'Interpretation'}")
    print("-" * 60)

    for conf in confidence_levels:
        var = calc.var_historical(confidence=conf)
        print(f"{conf:.0%}          {var:>10.2%}    {100-conf*100:.0f}% chance of losing more than {abs(var):.2%}")

    print("\n--- Parametric VaR ---")
    print("(Assumes normal distribution)")
    print(f"{'Confidence':<12} {'VaR':<12}")
    print("-" * 24)

    for conf in confidence_levels:
        var = calc.var_parametric(confidence=conf)
        print(f"{conf:.0%}          {var:>10.2%}")

    print("\n--- Monte Carlo VaR ---")
    print("(Simulated from fitted distribution)")
    print(f"{'Confidence':<12} {'VaR':<12}")
    print("-" * 24)

    for conf in confidence_levels:
        var = calc.var_monte_carlo(confidence=conf, n_simulations=10000)
        print(f"{conf:.0%}          {var:>10.2%}")


def example_cvar_calculation(returns):
    """Example: CVaR / Expected Shortfall calculation."""
    print("\n" + "=" * 60)
    print("Example 2: CVaR (Expected Shortfall)")
    print("=" * 60)

    from core import RiskCalculator

    calc = RiskCalculator(returns, risk_free_rate=0.02)

    print("\nCVaR represents the expected loss when losses exceed VaR")
    print("\n--- VaR vs CVaR Comparison ---")
    print(f"{'Confidence':<12} {'VaR':<12} {'CVaR':<12} {'Difference'}")
    print("-" * 48)

    for conf in [0.90, 0.95, 0.99]:
        var = calc.var_historical(confidence=conf)
        cvar = calc.cvar(confidence=conf)
        diff = cvar - var
        print(f"{conf:.0%}          {var:>10.2%} {cvar:>10.2%} {diff:>10.2%}")

    print("\nInterpretation:")
    var_95 = calc.var_historical(confidence=0.95)
    cvar_95 = calc.cvar(confidence=0.95)
    print(f"  At 95% confidence:")
    print(f"  - VaR: {abs(var_95):.2%} = Maximum loss in 95% of cases")
    print(f"  - CVaR: {abs(cvar_95):.2%} = Average loss in worst 5% of cases")


def example_performance_ratios(returns):
    """Example: Performance ratio calculation."""
    print("\n" + "=" * 60)
    print("Example 3: Performance Ratios")
    print("=" * 60)

    from core import RiskCalculator

    calc = RiskCalculator(returns, risk_free_rate=0.02)

    print("\n--- Risk-Adjusted Return Ratios ---")

    # Sharpe Ratio
    sharpe = calc.sharpe_ratio()
    print(f"\nSharpe Ratio: {sharpe:.2f}")
    print("  Formula: (Return - Risk-Free Rate) / Volatility")
    print("  Interpretation:")
    if sharpe > 2:
        print("  - Excellent risk-adjusted returns")
    elif sharpe > 1:
        print("  - Good risk-adjusted returns")
    elif sharpe > 0:
        print("  - Positive but modest risk-adjusted returns")
    else:
        print("  - Poor risk-adjusted returns (below risk-free rate)")

    # Sortino Ratio
    sortino = calc.sortino_ratio()
    print(f"\nSortino Ratio: {sortino:.2f}")
    print("  Formula: (Return - MAR) / Downside Volatility")
    print("  Only penalizes downside volatility, not upside")

    # Calmar Ratio
    calmar = calc.calmar_ratio()
    print(f"\nCalmar Ratio: {calmar:.2f}")
    print("  Formula: CAGR / Maximum Drawdown")
    print("  Measures return relative to worst drawdown")


def example_drawdown_analysis(returns):
    """Example: Drawdown analysis."""
    print("\n" + "=" * 60)
    print("Example 4: Drawdown Analysis")
    print("=" * 60)

    from core import RiskCalculator

    calc = RiskCalculator(returns, risk_free_rate=0.02)

    # Calculate cumulative returns and drawdowns
    cumulative = (1 + returns).cumprod()
    peak = cumulative.cummax()
    drawdown = (cumulative - peak) / peak

    # Maximum Drawdown
    max_dd = calc.max_drawdown()
    max_dd_idx = drawdown.idxmin()

    print(f"\n--- Drawdown Statistics ---")
    print(f"Maximum Drawdown: {max_dd:.2%}")
    print(f"Date of Max DD:   {max_dd_idx.strftime('%Y-%m-%d')}")

    # Average Drawdown
    avg_dd = drawdown[drawdown < 0].mean()
    print(f"Average Drawdown: {avg_dd:.2%}")

    # Drawdown Duration
    in_drawdown = drawdown < 0
    drawdown_periods = []
    current_length = 0

    for is_dd in in_drawdown:
        if is_dd:
            current_length += 1
        else:
            if current_length > 0:
                drawdown_periods.append(current_length)
            current_length = 0

    if drawdown_periods:
        avg_duration = np.mean(drawdown_periods)
        max_duration = max(drawdown_periods)
        print(f"Avg DD Duration:  {avg_duration:.1f} days")
        print(f"Max DD Duration:  {max_duration} days")

    # Top 5 Drawdowns
    print("\n--- Top 5 Worst Drawdowns ---")
    worst_days = drawdown.nsmallest(5)
    for i, (date, dd) in enumerate(worst_days.items(), 1):
        print(f"  {i}. {date.strftime('%Y-%m-%d')}: {dd:.2%}")


def example_distribution_analysis(returns):
    """Example: Return distribution analysis."""
    print("\n" + "=" * 60)
    print("Example 5: Distribution Analysis")
    print("=" * 60)

    from core import RiskCalculator

    calc = RiskCalculator(returns, risk_free_rate=0.02)

    print("\n--- Basic Statistics ---")
    print(f"Mean Daily Return:   {returns.mean():.4%}")
    print(f"Median Daily Return: {returns.median():.4%}")
    print(f"Std Deviation:       {returns.std():.4%}")

    print("\n--- Higher Moments ---")
    skew = returns.skew()
    kurt = returns.kurtosis()

    print(f"Skewness:  {skew:.4f}")
    if skew > 0:
        print("  (Positive skew: longer right tail, more extreme gains)")
    elif skew < 0:
        print("  (Negative skew: longer left tail, more extreme losses)")
    else:
        print("  (Symmetric distribution)")

    print(f"\nKurtosis:  {kurt:.4f}")
    if kurt > 0:
        print("  (Leptokurtic: fat tails, more extreme events than normal)")
    elif kurt < 0:
        print("  (Platykurtic: thin tails, fewer extreme events than normal)")
    else:
        print("  (Mesokurtic: similar to normal distribution)")

    # Normality test
    from scipy import stats
    stat, p_value = stats.jarque_bera(returns)

    print(f"\n--- Normality Test (Jarque-Bera) ---")
    print(f"Test Statistic: {stat:.4f}")
    print(f"P-Value:        {p_value:.4f}")
    if p_value < 0.05:
        print("Result: Reject normality (returns are NOT normally distributed)")
    else:
        print("Result: Cannot reject normality")


def example_all_metrics(returns):
    """Example: Calculate all risk metrics at once."""
    print("\n" + "=" * 60)
    print("Example 6: Complete Risk Report")
    print("=" * 60)

    from core import RiskCalculator

    calc = RiskCalculator(returns, risk_free_rate=0.02)

    print("\nCalculating all risk metrics...")
    metrics = calc.calculate_all()

    print("\n" + "=" * 40)
    print("RISK ANALYSIS REPORT")
    print("=" * 40)
    print(metrics.summary())


def example_portfolio_risk(returns):
    """Example: Portfolio risk decomposition."""
    print("\n" + "=" * 60)
    print("Example 7: Portfolio Risk Decomposition")
    print("=" * 60)

    # Create multi-asset returns
    np.random.seed(42)

    # Generate correlated returns for demonstration
    n_days = len(returns)
    dates = returns.index

    portfolio_returns = pd.DataFrame({
        'AAPL': returns.values,
        'MSFT': np.random.normal(0.0004, 0.018, n_days),
        'GOOGL': np.random.normal(0.0006, 0.022, n_days),
    }, index=dates)

    weights = {'AAPL': 0.4, 'MSFT': 0.35, 'GOOGL': 0.25}

    print(f"\nPortfolio Weights:")
    for asset, weight in weights.items():
        print(f"  {asset}: {weight:.0%}")

    # Calculate portfolio return
    portfolio_return = sum(
        portfolio_returns[asset] * weight
        for asset, weight in weights.items()
    )

    from core import RiskCalculator

    calc = RiskCalculator(portfolio_return, risk_free_rate=0.02)

    print(f"\n--- Portfolio Risk Metrics ---")
    print(f"Portfolio Volatility (Ann): {portfolio_return.std() * np.sqrt(252):.2%}")
    print(f"Portfolio VaR (95%):        {calc.var_historical(0.95):.2%}")
    print(f"Portfolio CVaR (95%):       {calc.cvar(0.95):.2%}")
    print(f"Portfolio Sharpe:           {calc.sharpe_ratio():.2f}")

    # Individual asset contributions
    print(f"\n--- Individual Asset Risk ---")
    print(f"{'Asset':<10} {'Vol (Ann)':<12} {'Weight':<10} {'Contribution'}")
    print("-" * 42)

    for asset, weight in weights.items():
        vol = portfolio_returns[asset].std() * np.sqrt(252)
        contrib = vol * weight
        print(f"{asset:<10} {vol:<12.2%} {weight:<10.0%} {contrib:<12.2%}")


def main():
    """Run all risk analysis examples."""
    print("\n" + "#" * 60)
    print("# Quantitative Trading Tool - Risk Analysis Examples")
    print("#" * 60)

    # Fetch data
    returns = fetch_returns_data()
    print(f"\nData: {len(returns)} daily returns")
    print(f"Date range: {returns.index[0]} to {returns.index[-1]}")

    # Example 1: VaR
    example_var_calculation(returns)

    # Example 2: CVaR
    example_cvar_calculation(returns)

    # Example 3: Performance ratios
    example_performance_ratios(returns)

    # Example 4: Drawdown
    example_drawdown_analysis(returns)

    # Example 5: Distribution
    example_distribution_analysis(returns)

    # Example 6: All metrics
    example_all_metrics(returns)

    # Example 7: Portfolio risk
    example_portfolio_risk(returns)

    print("\n" + "#" * 60)
    print("# Risk analysis examples completed!")
    print("#" * 60)


if __name__ == "__main__":
    main()
