# -*- coding: utf-8 -*-
"""
Report generation example for quantitative trading tool.

Demonstrates:
- Generating backtest reports
- Generating risk reports
- Generating portfolio reports
- Creating comprehensive analysis reports

Usage:
    python examples/report_example.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np


def generate_sample_data():
    """Generate sample data for reports."""
    from scripts.generate_sample_data import generate_correlated_assets

    symbols = ['AAPL', 'MSFT', 'GOOGL']
    prices_df = generate_correlated_assets(symbols, n_days=252, seed=42)
    dates = pd.date_range(start='2023-01-01', periods=252, freq='B')
    prices_df.index = dates

    return prices_df


def example_backtest_report():
    """Example: Generate backtest report."""
    print("\n" + "=" * 60)
    print("Example 1: Backtest Report")
    print("=" * 60)

    from core import BacktestEngine, ReportGenerator

    # Generate data and run backtest
    prices_df = generate_sample_data()

    engine = BacktestEngine()
    result = engine.run_mean_reversion(
        prices_df,
        lookback=20,
        entry_zscore=2.0,
        exit_zscore=0.5,
        initial_capital=100000
    )

    # Generate report
    print("\nGenerating backtest report...")

    report = ReportGenerator("Mean Reversion Backtest Report")
    report.generate_backtest_report(
        result,
        strategy_name="Mean Reversion",
        symbols=['AAPL', 'MSFT', 'GOOGL'],
        parameters={'lookback': 20, 'entry_zscore': 2.0, 'exit_zscore': 0.5}
    )

    # Save report
    output_path = project_root / 'reports' / 'backtest_report.html'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report.save(str(output_path))

    print(f"\nReport saved to: {output_path}")
    print(f"\nKey metrics:")
    print(f"  Total Return: {result.total_return:.2%}")
    print(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}")
    print(f"  Max Drawdown: {result.max_drawdown:.2%}")


def example_risk_report():
    """Example: Generate risk analysis report."""
    print("\n" + "=" * 60)
    print("Example 2: Risk Analysis Report")
    print("=" * 60)

    from core import RiskCalculator, ReportGenerator

    # Generate data
    prices_df = generate_sample_data()
    returns = prices_df.pct_change().dropna().mean(axis=1)

    # Calculate risk metrics
    calc = RiskCalculator(returns, risk_free_rate=0.02)
    metrics = calc.calculate_all()

    # Generate report
    print("\nGenerating risk report...")

    report = ReportGenerator("Portfolio Risk Analysis Report")
    report.generate_risk_report(metrics, returns)

    # Save report
    output_path = project_root / 'reports' / 'risk_report.html'
    report.save(str(output_path))

    print(f"\nReport saved to: {output_path}")
    print(f"\nKey risk metrics:")
    print(f"  VaR (95%): {metrics.var_95_historical:.2%}")
    print(f"  CVaR (95%): {metrics.cvar_95:.2%}")
    print(f"  Sharpe Ratio: {metrics.sharpe_ratio:.2f}")


def example_portfolio_report():
    """Example: Generate portfolio optimization report."""
    print("\n" + "=" * 60)
    print("Example 3: Portfolio Optimization Report")
    print("=" * 60)

    from core import PortfolioOptimizer, ReportGenerator

    # Generate data
    prices_df = generate_sample_data()

    # Optimize portfolio
    optimizer = PortfolioOptimizer()
    result = optimizer.max_sharpe(prices_df, risk_free_rate=0.02)

    # Generate report
    print("\nGenerating portfolio report...")

    report = ReportGenerator("Portfolio Optimization Report")
    report.generate_portfolio_report(result, method="Maximum Sharpe Ratio")

    # Save report
    output_path = project_root / 'reports' / 'portfolio_report.html'
    report.save(str(output_path))

    print(f"\nReport saved to: {output_path}")
    print(f"\nOptimal weights:")
    for symbol, weight in result.weights.items():
        if weight > 0.01:
            print(f"  {symbol}: {weight:.2%}")


def example_comprehensive_report():
    """Example: Generate comprehensive analysis report."""
    print("\n" + "=" * 60)
    print("Example 4: Comprehensive Analysis Report")
    print("=" * 60)

    from core import (
        BacktestEngine,
        PortfolioOptimizer,
        RiskCalculator,
        ReportGenerator,
        generate_full_report
    )

    # Generate data
    prices_df = generate_sample_data()

    # Run backtest
    print("\nRunning backtest...")
    engine = BacktestEngine()
    backtest_result = engine.run_mean_reversion(
        prices_df,
        lookback=20,
        initial_capital=100000
    )

    # Optimize portfolio
    print("Optimizing portfolio...")
    optimizer = PortfolioOptimizer()
    portfolio_result = optimizer.max_sharpe(prices_df)

    # Calculate risk
    print("Calculating risk metrics...")
    returns = prices_df.pct_change().dropna().mean(axis=1)
    calc = RiskCalculator(returns, risk_free_rate=0.02)
    risk_metrics = calc.calculate_all()

    # Generate comprehensive report
    print("\nGenerating comprehensive report...")

    report = ReportGenerator("Comprehensive Quantitative Analysis")

    # Add executive summary
    summary_html = f"""
    <div class="summary-box">
        <h3>Executive Summary</h3>
        <p>This report provides a comprehensive analysis of the portfolio including:</p>
        <ul>
            <li>Backtest performance of Mean Reversion strategy</li>
            <li>Optimal portfolio allocation using Maximum Sharpe method</li>
            <li>Risk metrics including VaR, CVaR, and performance ratios</li>
        </ul>
        <p><strong>Analysis Period:</strong> {prices_df.index[0].strftime('%Y-%m-%d')} to {prices_df.index[-1].strftime('%Y-%m-%d')}</p>
        <p><strong>Assets Analyzed:</strong> {', '.join(prices_df.columns)}</p>
    </div>
    """
    report.add_section("Executive Summary", summary_html)

    # Add individual sections
    report.generate_backtest_report(
        backtest_result,
        strategy_name="Mean Reversion",
        symbols=list(prices_df.columns)
    )
    report.generate_portfolio_report(portfolio_result)
    report.generate_risk_report(risk_metrics, returns)

    # Save report
    output_path = project_root / 'reports' / 'comprehensive_report.html'
    report.save(str(output_path))

    print(f"\nComprehensive report saved to: {output_path}")


def example_strategy_comparison_report():
    """Example: Generate strategy comparison report."""
    print("\n" + "=" * 60)
    print("Example 5: Strategy Comparison Report")
    print("=" * 60)

    from core import BacktestEngine, ReportGenerator

    # Generate data
    prices_df = generate_sample_data()
    engine = BacktestEngine()

    # Run multiple strategies
    strategies = [
        ('Mean Reversion', lambda: engine.run_mean_reversion(prices_df, lookback=20)),
        ('MA Crossover', lambda: engine.run_ma_crossover(prices_df, fast_period=10, slow_period=30)),
    ]

    results = {}
    for name, func in strategies:
        print(f"\nRunning {name}...")
        results[name] = func()

    # Generate comparison report
    print("\nGenerating comparison report...")

    report = ReportGenerator("Strategy Comparison Report")

    # Comparison table
    comparison_html = """
    <table>
        <tr>
            <th>Strategy</th>
            <th>Total Return</th>
            <th>Sharpe Ratio</th>
            <th>Max Drawdown</th>
            <th>Win Rate</th>
        </tr>
    """

    for name, result in results.items():
        comparison_html += f"""
        <tr>
            <td>{name}</td>
            <td>{result.total_return:.2%}</td>
            <td>{result.sharpe_ratio:.2f}</td>
            <td>{result.max_drawdown:.2%}</td>
            <td>{result.win_rate:.2%}</td>
        </tr>
        """

    comparison_html += "</table>"

    report.add_section("Strategy Comparison", comparison_html)

    # Add individual strategy details
    for name, result in results.items():
        report.generate_backtest_report(result, strategy_name=name)

    # Save report
    output_path = project_root / 'reports' / 'strategy_comparison.html'
    report.save(str(output_path))

    print(f"\nComparison report saved to: {output_path}")

    # Print summary
    print("\n--- Strategy Comparison ---")
    for name, result in results.items():
        print(f"{name}: Return={result.total_return:.2%}, Sharpe={result.sharpe_ratio:.2f}")


def main():
    """Run all report examples."""
    print("\n" + "#" * 60)
    print("# Quantitative Trading Tool - Report Generation Examples")
    print("#" * 60)

    # Example 1: Backtest report
    example_backtest_report()

    # Example 2: Risk report
    example_risk_report()

    # Example 3: Portfolio report
    example_portfolio_report()

    # Example 4: Comprehensive report
    example_comprehensive_report()

    # Example 5: Strategy comparison
    example_strategy_comparison_report()

    print("\n" + "#" * 60)
    print("# Report generation examples completed!")
    print("#" * 60)
    print(f"\nAll reports saved to: {project_root / 'reports'}")


if __name__ == "__main__":
    main()
