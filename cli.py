# -*- coding: utf-8 -*-
"""
Command-line interface for quantitative trading tool.

Provides a unified CLI for all common operations.

Usage:
    python cli.py --help
    python cli.py data fetch AAPL --start 2023-01-01
    python cli.py backtest run --strategy mean_reversion --symbols AAPL,MSFT
    python cli.py portfolio optimize --method max_sharpe --symbols AAPL,MSFT,GOOGL
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import argparse
from datetime import datetime, timedelta
import json


def cmd_data_fetch(args):
    """Fetch stock data."""
    from core import DataManager

    dm = DataManager()

    print(f"Fetching {args.symbol} from {args.start} to {args.end}...")

    df = dm.fetch_ohlcv(args.symbol, args.start, args.end)

    if df is not None and not df.empty:
        print(f"Retrieved {len(df)} records")
        print(f"\nLatest data:")
        print(df.tail())

        if args.output:
            df.to_csv(args.output)
            print(f"\nSaved to: {args.output}")
    else:
        print("No data retrieved")


def cmd_data_quote(args):
    """Get real-time quote."""
    from core import DataManager

    dm = DataManager()

    print(f"Fetching quote for {args.symbol}...")

    quote = dm.fetch_quote(args.symbol)

    if quote:
        print(f"\n{args.symbol} Quote:")
        for key, value in quote.items():
            print(f"  {key}: {value}")
    else:
        print("No quote available")


def cmd_backtest_run(args):
    """Run a backtest."""
    from core import DataManager, BacktestEngine
    import pandas as pd

    dm = DataManager()
    engine = BacktestEngine()

    symbols = [s.strip().upper() for s in args.symbols.split(',')]

    print(f"Fetching data for: {', '.join(symbols)}")

    prices = {}
    for symbol in symbols:
        df = dm.fetch_ohlcv(symbol, args.start, args.end)
        if df is not None and not df.empty:
            prices[symbol] = df['close']
            print(f"  {symbol}: {len(df)} records")

    if not prices:
        print("No data available")
        return

    prices_df = pd.DataFrame(prices).dropna()
    print(f"\nRunning {args.strategy} backtest...")

    if args.strategy == 'mean_reversion':
        result = engine.run_mean_reversion(
            prices_df,
            lookback=args.lookback,
            entry_zscore=args.entry_z,
            exit_zscore=args.exit_z,
            initial_capital=args.capital
        )
    elif args.strategy == 'ma_crossover':
        result = engine.run_ma_crossover(
            prices_df,
            fast_period=args.fast,
            slow_period=args.slow,
            initial_capital=args.capital
        )
    else:
        print(f"Unknown strategy: {args.strategy}")
        return

    print(f"\n{'='*50}")
    print("BACKTEST RESULTS")
    print(f"{'='*50}")
    print(f"Total Return:   {result.total_return:>10.2%}")
    print(f"CAGR:           {result.cagr:>10.2%}")
    print(f"Sharpe Ratio:   {result.sharpe_ratio:>10.2f}")
    print(f"Max Drawdown:   {result.max_drawdown:>10.2%}")
    print(f"Win Rate:       {result.win_rate:>10.2%}")
    print(f"Total Trades:   {result.total_trades:>10}")

    if args.output:
        output_data = {
            'strategy': args.strategy,
            'symbols': symbols,
            'total_return': result.total_return,
            'sharpe_ratio': result.sharpe_ratio,
            'max_drawdown': result.max_drawdown
        }
        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"\nResults saved to: {args.output}")


def cmd_backtest_compare(args):
    """Compare multiple strategies."""
    from core import DataManager, BacktestEngine
    from strategies import StrategyRunner
    import pandas as pd

    dm = DataManager()
    symbols = [s.strip().upper() for s in args.symbols.split(',')]

    print(f"Fetching data for: {', '.join(symbols)}")

    prices = {}
    for symbol in symbols:
        df = dm.fetch_ohlcv(symbol, args.start, args.end)
        if df is not None and not df.empty:
            prices[symbol] = df['close']

    if not prices:
        print("No data available")
        return

    prices_df = pd.DataFrame(prices).dropna()

    engine = BacktestEngine()

    strategies = {
        'Mean Reversion': lambda: engine.run_mean_reversion(prices_df, initial_capital=args.capital),
        'MA Crossover': lambda: engine.run_ma_crossover(prices_df, initial_capital=args.capital),
    }

    print(f"\nComparing strategies...")
    print(f"\n{'Strategy':<20} {'Return':<12} {'Sharpe':<10} {'Max DD':<12}")
    print("-" * 54)

    for name, func in strategies.items():
        try:
            result = func()
            print(f"{name:<20} {result.total_return:<12.2%} {result.sharpe_ratio:<10.2f} {result.max_drawdown:<12.2%}")
        except Exception as e:
            print(f"{name:<20} Error: {e}")


def cmd_portfolio_optimize(args):
    """Optimize portfolio allocation."""
    from core import DataManager, PortfolioOptimizer
    import pandas as pd

    dm = DataManager()
    optimizer = PortfolioOptimizer()

    symbols = [s.strip().upper() for s in args.symbols.split(',')]

    print(f"Fetching data for: {', '.join(symbols)}")

    prices = {}
    for symbol in symbols:
        df = dm.fetch_ohlcv(symbol, args.start, args.end)
        if df is not None and not df.empty:
            prices[symbol] = df['close']
            print(f"  {symbol}: {len(df)} records")

    if len(prices) < 2:
        print("Need at least 2 assets for optimization")
        return

    prices_df = pd.DataFrame(prices).dropna()

    print(f"\nOptimizing with {args.method} method...")

    if args.method == 'max_sharpe':
        result = optimizer.max_sharpe(prices_df, risk_free_rate=args.rf)
    elif args.method == 'min_volatility':
        result = optimizer.min_volatility(prices_df)
    elif args.method == 'risk_parity':
        result = optimizer.risk_parity(prices_df)
    elif args.method == 'equal_weight':
        result = optimizer.equal_weight(prices_df)
    else:
        print(f"Unknown method: {args.method}")
        return

    print(f"\n{'='*50}")
    print("OPTIMIZATION RESULTS")
    print(f"{'='*50}")
    print(f"\nOptimal Weights:")
    for symbol, weight in result.weights.items():
        if weight > 0.01:
            print(f"  {symbol}: {weight:>8.2%}")

    print(f"\nExpected Performance:")
    print(f"  Expected Return:  {result.expected_return:>8.2%}")
    print(f"  Volatility:       {result.volatility:>8.2%}")
    print(f"  Sharpe Ratio:     {result.sharpe_ratio:>8.2f}")

    if args.capital:
        print(f"\nDiscrete Allocation (${args.capital:,.0f}):")
        allocation = optimizer.discrete_allocation(result.weights, prices_df, args.capital)
        for symbol, shares in allocation.items():
            if shares > 0:
                value = shares * prices_df[symbol].iloc[-1]
                print(f"  {symbol}: {shares} shares (${value:,.2f})")


def cmd_risk_analyze(args):
    """Analyze risk metrics."""
    from core import DataManager, RiskCalculator
    import pandas as pd

    dm = DataManager()

    symbols = [s.strip().upper() for s in args.symbols.split(',')]

    print(f"Fetching data for: {', '.join(symbols)}")

    prices = {}
    for symbol in symbols:
        df = dm.fetch_ohlcv(symbol, args.start, args.end)
        if df is not None and not df.empty:
            prices[symbol] = df['close']

    if not prices:
        print("No data available")
        return

    prices_df = pd.DataFrame(prices).dropna()
    returns = prices_df.pct_change().dropna()

    # Calculate portfolio returns (equal weight)
    portfolio_returns = returns.mean(axis=1)

    calc = RiskCalculator(portfolio_returns, risk_free_rate=args.rf)
    metrics = calc.calculate_all()

    print(f"\n{'='*50}")
    print("RISK ANALYSIS")
    print(f"{'='*50}")
    print(metrics.summary())


def cmd_report_generate(args):
    """Generate analysis report."""
    from core import DataManager, BacktestEngine, PortfolioOptimizer, RiskCalculator
    from core import ReportGenerator
    import pandas as pd

    dm = DataManager()
    symbols = [s.strip().upper() for s in args.symbols.split(',')]

    print(f"Fetching data...")

    prices = {}
    for symbol in symbols:
        df = dm.fetch_ohlcv(symbol, args.start, args.end)
        if df is not None and not df.empty:
            prices[symbol] = df['close']

    if not prices:
        print("No data available")
        return

    prices_df = pd.DataFrame(prices).dropna()

    print("Running analysis...")

    # Backtest
    engine = BacktestEngine()
    backtest_result = engine.run_mean_reversion(prices_df, initial_capital=100000)

    # Optimization
    optimizer = PortfolioOptimizer()
    opt_result = optimizer.max_sharpe(prices_df)

    # Risk
    returns = prices_df.pct_change().dropna().mean(axis=1)
    calc = RiskCalculator(returns)
    risk_metrics = calc.calculate_all()

    # Generate report
    print("Generating report...")

    report = ReportGenerator("Quantitative Analysis Report")
    report.generate_backtest_report(backtest_result, "Mean Reversion", symbols)
    report.generate_portfolio_report(opt_result)
    report.generate_risk_report(risk_metrics, returns)

    output_path = args.output or 'report.html'
    report.save(output_path)

    print(f"\nReport saved to: {output_path}")


def cmd_health_check(args):
    """Run system health check."""
    import subprocess
    subprocess.run([sys.executable, 'scripts/health_check.py'])


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Quantitative Trading Tool CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py data fetch AAPL --start 2023-01-01
  python cli.py backtest run --strategy mean_reversion --symbols AAPL,MSFT
  python cli.py portfolio optimize --method max_sharpe --symbols AAPL,MSFT,GOOGL
  python cli.py risk analyze --symbols AAPL,MSFT
  python cli.py report generate --symbols AAPL,MSFT,GOOGL -o report.html
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Default dates
    default_start = (datetime.now() - timedelta(days=365*2)).strftime('%Y-%m-%d')
    default_end = datetime.now().strftime('%Y-%m-%d')

    # Data commands
    data_parser = subparsers.add_parser('data', help='Data operations')
    data_sub = data_parser.add_subparsers(dest='data_cmd')

    # data fetch
    fetch_parser = data_sub.add_parser('fetch', help='Fetch stock data')
    fetch_parser.add_argument('symbol', help='Stock symbol')
    fetch_parser.add_argument('--start', '-s', default=default_start, help='Start date')
    fetch_parser.add_argument('--end', '-e', default=default_end, help='End date')
    fetch_parser.add_argument('--output', '-o', help='Output CSV file')

    # data quote
    quote_parser = data_sub.add_parser('quote', help='Get real-time quote')
    quote_parser.add_argument('symbol', help='Stock symbol')

    # Backtest commands
    bt_parser = subparsers.add_parser('backtest', help='Backtesting operations')
    bt_sub = bt_parser.add_subparsers(dest='bt_cmd')

    # backtest run
    run_parser = bt_sub.add_parser('run', help='Run backtest')
    run_parser.add_argument('--strategy', '-st', required=True,
                           choices=['mean_reversion', 'ma_crossover'],
                           help='Strategy to backtest')
    run_parser.add_argument('--symbols', '-s', required=True, help='Comma-separated symbols')
    run_parser.add_argument('--start', default=default_start, help='Start date')
    run_parser.add_argument('--end', default=default_end, help='End date')
    run_parser.add_argument('--capital', type=float, default=100000, help='Initial capital')
    run_parser.add_argument('--lookback', type=int, default=20, help='Lookback period')
    run_parser.add_argument('--entry-z', type=float, default=2.0, help='Entry Z-score')
    run_parser.add_argument('--exit-z', type=float, default=0.5, help='Exit Z-score')
    run_parser.add_argument('--fast', type=int, default=10, help='Fast MA period')
    run_parser.add_argument('--slow', type=int, default=30, help='Slow MA period')
    run_parser.add_argument('--output', '-o', help='Output JSON file')

    # backtest compare
    compare_parser = bt_sub.add_parser('compare', help='Compare strategies')
    compare_parser.add_argument('--symbols', '-s', required=True, help='Comma-separated symbols')
    compare_parser.add_argument('--start', default=default_start, help='Start date')
    compare_parser.add_argument('--end', default=default_end, help='End date')
    compare_parser.add_argument('--capital', type=float, default=100000, help='Initial capital')

    # Portfolio commands
    pf_parser = subparsers.add_parser('portfolio', help='Portfolio operations')
    pf_sub = pf_parser.add_subparsers(dest='pf_cmd')

    # portfolio optimize
    opt_parser = pf_sub.add_parser('optimize', help='Optimize portfolio')
    opt_parser.add_argument('--method', '-m', default='max_sharpe',
                           choices=['max_sharpe', 'min_volatility', 'risk_parity', 'equal_weight'],
                           help='Optimization method')
    opt_parser.add_argument('--symbols', '-s', required=True, help='Comma-separated symbols')
    opt_parser.add_argument('--start', default=default_start, help='Start date')
    opt_parser.add_argument('--end', default=default_end, help='End date')
    opt_parser.add_argument('--rf', type=float, default=0.02, help='Risk-free rate')
    opt_parser.add_argument('--capital', type=float, help='Capital for discrete allocation')

    # Risk commands
    risk_parser = subparsers.add_parser('risk', help='Risk analysis')
    risk_sub = risk_parser.add_subparsers(dest='risk_cmd')

    # risk analyze
    analyze_parser = risk_sub.add_parser('analyze', help='Analyze risk metrics')
    analyze_parser.add_argument('--symbols', '-s', required=True, help='Comma-separated symbols')
    analyze_parser.add_argument('--start', default=default_start, help='Start date')
    analyze_parser.add_argument('--end', default=default_end, help='End date')
    analyze_parser.add_argument('--rf', type=float, default=0.02, help='Risk-free rate')

    # Report commands
    report_parser = subparsers.add_parser('report', help='Report generation')
    report_sub = report_parser.add_subparsers(dest='report_cmd')

    # report generate
    gen_parser = report_sub.add_parser('generate', help='Generate report')
    gen_parser.add_argument('--symbols', '-s', required=True, help='Comma-separated symbols')
    gen_parser.add_argument('--start', default=default_start, help='Start date')
    gen_parser.add_argument('--end', default=default_end, help='End date')
    gen_parser.add_argument('--output', '-o', default='report.html', help='Output file')

    # Health check
    health_parser = subparsers.add_parser('health', help='System health check')

    # Parse args
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    # Route to handlers
    if args.command == 'data':
        if args.data_cmd == 'fetch':
            cmd_data_fetch(args)
        elif args.data_cmd == 'quote':
            cmd_data_quote(args)
        else:
            data_parser.print_help()

    elif args.command == 'backtest':
        if args.bt_cmd == 'run':
            cmd_backtest_run(args)
        elif args.bt_cmd == 'compare':
            cmd_backtest_compare(args)
        else:
            bt_parser.print_help()

    elif args.command == 'portfolio':
        if args.pf_cmd == 'optimize':
            cmd_portfolio_optimize(args)
        else:
            pf_parser.print_help()

    elif args.command == 'risk':
        if args.risk_cmd == 'analyze':
            cmd_risk_analyze(args)
        else:
            risk_parser.print_help()

    elif args.command == 'report':
        if args.report_cmd == 'generate':
            cmd_report_generate(args)
        else:
            report_parser.print_help()

    elif args.command == 'health':
        cmd_health_check(args)


if __name__ == '__main__':
    main()
