# -*- coding: utf-8 -*-
"""
Command-line backtest runner.

Run backtests from the command line without the Streamlit interface.

Usage:
    python scripts/run_backtest.py --strategy mean_reversion --symbols AAPL,MSFT --start 2022-01-01
    python scripts/run_backtest.py --strategy ma_crossover --symbols 2330 --fast 10 --slow 30
"""

import argparse
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Run backtest from command line'
    )

    # Required arguments
    parser.add_argument(
        '--strategy', '-st',
        type=str,
        required=True,
        choices=['mean_reversion', 'ma_crossover', 'rsi', 'bollinger'],
        help='Strategy to backtest'
    )
    parser.add_argument(
        '--symbols', '-s',
        type=str,
        required=True,
        help='Comma-separated list of symbols'
    )

    # Date range
    parser.add_argument(
        '--start',
        type=str,
        default=(datetime.now() - timedelta(days=365*2)).strftime('%Y-%m-%d'),
        help='Start date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end',
        type=str,
        default=datetime.now().strftime('%Y-%m-%d'),
        help='End date (YYYY-MM-DD)'
    )

    # Capital and costs
    parser.add_argument(
        '--capital',
        type=float,
        default=100000,
        help='Initial capital (default: 100000)'
    )
    parser.add_argument(
        '--commission',
        type=float,
        default=0.001,
        help='Commission rate (default: 0.001 = 0.1%%)'
    )
    parser.add_argument(
        '--slippage',
        type=float,
        default=0.0005,
        help='Slippage rate (default: 0.0005 = 0.05%%)'
    )

    # Strategy-specific parameters
    # Mean Reversion
    parser.add_argument('--lookback', type=int, default=20,
                        help='Lookback period for mean reversion')
    parser.add_argument('--entry-z', type=float, default=2.0,
                        help='Entry Z-score threshold')
    parser.add_argument('--exit-z', type=float, default=0.5,
                        help='Exit Z-score threshold')

    # MA Crossover
    parser.add_argument('--fast', type=int, default=10,
                        help='Fast MA period')
    parser.add_argument('--slow', type=int, default=30,
                        help='Slow MA period')

    # RSI
    parser.add_argument('--rsi-period', type=int, default=14,
                        help='RSI period')
    parser.add_argument('--oversold', type=int, default=30,
                        help='RSI oversold level')
    parser.add_argument('--overbought', type=int, default=70,
                        help='RSI overbought level')

    # Bollinger
    parser.add_argument('--bb-period', type=int, default=20,
                        help='Bollinger Bands period')
    parser.add_argument('--bb-std', type=float, default=2.0,
                        help='Bollinger Bands standard deviations')

    # Output
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output file for results (JSON)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )

    return parser.parse_args()


def main():
    """Main function."""
    args = parse_args()

    print("=" * 60)
    print("Quantitative Trading Tool - Command Line Backtest")
    print("=" * 60)

    # Parse symbols
    symbols = [s.strip().upper() for s in args.symbols.split(',')]

    print(f"\nStrategy: {args.strategy}")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Date Range: {args.start} to {args.end}")
    print(f"Initial Capital: ${args.capital:,.2f}")

    # Initialize components
    try:
        from core import DataManager, BacktestEngine
        import pandas as pd

        dm = DataManager()
        engine = BacktestEngine()

    except Exception as e:
        print(f"\nError initializing: {e}")
        return False

    # Fetch data
    print("\nFetching price data...")
    price_data = {}

    for symbol in symbols:
        try:
            df = dm.fetch_ohlcv(symbol, args.start, args.end)
            if df is not None and not df.empty:
                price_data[symbol] = df['close']
                print(f"  {symbol}: {len(df)} records")
            else:
                print(f"  {symbol}: No data")
        except Exception as e:
            print(f"  {symbol}: Error - {e}")

    if not price_data:
        print("\nError: No price data available")
        return False

    # Combine prices
    prices_df = pd.DataFrame(price_data)
    prices_df = prices_df.dropna()

    print(f"\nTotal: {len(prices_df)} overlapping trading days")

    # Run backtest
    print("\nRunning backtest...")
    print("-" * 60)

    try:
        if args.strategy == 'mean_reversion':
            result = engine.run_mean_reversion(
                prices_df,
                lookback=args.lookback,
                entry_zscore=args.entry_z,
                exit_zscore=args.exit_z,
                initial_capital=args.capital,
                commission_pct=args.commission,
                slippage_pct=args.slippage
            )
            params = f"lookback={args.lookback}, entry_z={args.entry_z}, exit_z={args.exit_z}"

        elif args.strategy == 'ma_crossover':
            result = engine.run_ma_crossover(
                prices_df,
                fast_period=args.fast,
                slow_period=args.slow,
                initial_capital=args.capital,
                commission_pct=args.commission,
                slippage_pct=args.slippage
            )
            params = f"fast={args.fast}, slow={args.slow}"

        elif args.strategy == 'rsi':
            result = engine.run_rsi_strategy(
                prices_df,
                period=args.rsi_period,
                oversold=args.oversold,
                overbought=args.overbought,
                initial_capital=args.capital,
                commission_pct=args.commission,
                slippage_pct=args.slippage
            )
            params = f"period={args.rsi_period}, oversold={args.oversold}, overbought={args.overbought}"

        elif args.strategy == 'bollinger':
            result = engine.run_bollinger_bands(
                prices_df,
                period=args.bb_period,
                num_std=args.bb_std,
                initial_capital=args.capital,
                commission_pct=args.commission,
                slippage_pct=args.slippage
            )
            params = f"period={args.bb_period}, std={args.bb_std}"

    except Exception as e:
        print(f"Backtest error: {e}")
        import traceback
        if args.verbose:
            traceback.print_exc()
        return False

    # Print results
    print("\n" + "=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)

    print(f"\nStrategy: {args.strategy} ({params})")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Period: {args.start} to {args.end}")

    print("\n--- Performance Metrics ---")
    print(f"Total Return:     {result.total_return:>10.2%}")
    print(f"CAGR:             {result.cagr:>10.2%}")
    print(f"Sharpe Ratio:     {result.sharpe_ratio:>10.2f}")
    print(f"Sortino Ratio:    {result.sortino_ratio:>10.2f}")
    print(f"Calmar Ratio:     {result.calmar_ratio:>10.2f}")

    print("\n--- Risk Metrics ---")
    print(f"Max Drawdown:     {result.max_drawdown:>10.2%}")
    print(f"Volatility (Ann): {result.equity_curve.pct_change().std() * (252**0.5):>10.2%}" if result.equity_curve is not None else "N/A")

    print("\n--- Trade Statistics ---")
    print(f"Total Trades:     {result.total_trades:>10}")
    print(f"Win Rate:         {result.win_rate:>10.2%}")
    print(f"Profit Factor:    {result.profit_factor:>10.2f}")

    # Final equity
    if result.equity_curve is not None:
        final_equity = result.equity_curve.iloc[-1]
        print(f"\nFinal Portfolio:  ${final_equity:>10,.2f}")

    # Save results if output specified
    if args.output:
        output_data = {
            'strategy': args.strategy,
            'parameters': params,
            'symbols': symbols,
            'start_date': args.start,
            'end_date': args.end,
            'initial_capital': args.capital,
            'results': {
                'total_return': result.total_return,
                'cagr': result.cagr,
                'sharpe_ratio': result.sharpe_ratio,
                'sortino_ratio': result.sortino_ratio,
                'calmar_ratio': result.calmar_ratio,
                'max_drawdown': result.max_drawdown,
                'win_rate': result.win_rate,
                'profit_factor': result.profit_factor,
                'total_trades': result.total_trades
            }
        }

        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)

        print(f"\nResults saved to: {args.output}")

    print("\n" + "=" * 60)

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
