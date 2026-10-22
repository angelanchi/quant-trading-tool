# -*- coding: utf-8 -*-
"""
Batch data download script.

Downloads historical price data for multiple symbols and stores in database.

Usage:
    python scripts/download_data.py --symbols AAPL,MSFT,GOOGL --start 2020-01-01 --end 2023-12-31
    python scripts/download_data.py --file symbols.txt --start 2020-01-01
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Download historical stock data'
    )
    parser.add_argument(
        '--symbols', '-s',
        type=str,
        help='Comma-separated list of symbols (e.g., AAPL,MSFT,GOOGL)'
    )
    parser.add_argument(
        '--file', '-f',
        type=str,
        help='File containing symbols (one per line)'
    )
    parser.add_argument(
        '--start',
        type=str,
        default=(datetime.now() - timedelta(days=365*2)).strftime('%Y-%m-%d'),
        help='Start date (YYYY-MM-DD), default: 2 years ago'
    )
    parser.add_argument(
        '--end',
        type=str,
        default=datetime.now().strftime('%Y-%m-%d'),
        help='End date (YYYY-MM-DD), default: today'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output directory for CSV files (optional)'
    )
    parser.add_argument(
        '--no-db',
        action='store_true',
        help='Do not store in database'
    )

    return parser.parse_args()


def load_symbols(args):
    """Load symbols from arguments."""
    symbols = []

    if args.symbols:
        symbols.extend([s.strip().upper() for s in args.symbols.split(',')])

    if args.file:
        file_path = Path(args.file)
        if file_path.exists():
            with open(file_path, 'r') as f:
                for line in f:
                    symbol = line.strip().upper()
                    if symbol and not symbol.startswith('#'):
                        symbols.append(symbol)
        else:
            print(f"Warning: File not found: {args.file}")

    return list(set(symbols))  # Remove duplicates


def main():
    """Main function."""
    args = parse_args()

    print("=" * 50)
    print("Quantitative Trading Tool - Data Download")
    print("=" * 50)

    # Load symbols
    symbols = load_symbols(args)

    if not symbols:
        print("\nError: No symbols specified.")
        print("Use --symbols or --file to specify symbols.")
        return False

    print(f"\nSymbols to download: {len(symbols)}")
    print(f"Date range: {args.start} to {args.end}")

    # Initialize data manager
    try:
        from core import DataManager
        dm = DataManager()
    except Exception as e:
        print(f"\nError initializing DataManager: {e}")
        return False

    # Create output directory if specified
    output_dir = None
    if args.output:
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"Output directory: {output_dir}")

    # Download data
    print("\nDownloading data...")
    print("-" * 50)

    success_count = 0
    fail_count = 0

    for i, symbol in enumerate(symbols, 1):
        try:
            print(f"[{i}/{len(symbols)}] {symbol}...", end=" ")

            df = dm.fetch_ohlcv(
                symbol,
                args.start,
                args.end,
                save_to_db=not args.no_db
            )

            if df is not None and not df.empty:
                print(f"OK ({len(df)} records)")
                success_count += 1

                # Save to CSV if output directory specified
                if output_dir:
                    csv_path = output_dir / f"{symbol}_{args.start}_{args.end}.csv"
                    df.to_csv(csv_path)

            else:
                print("No data")
                fail_count += 1

        except Exception as e:
            print(f"Error: {e}")
            fail_count += 1

    # Summary
    print("-" * 50)
    print(f"\nSummary:")
    print(f"  Successful: {success_count}")
    print(f"  Failed: {fail_count}")

    if output_dir:
        print(f"  CSV files saved to: {output_dir}")

    print("\n" + "=" * 50)
    print("Download completed!")
    print("=" * 50)

    return fail_count == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
