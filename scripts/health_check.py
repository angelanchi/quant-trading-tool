# -*- coding: utf-8 -*-
"""
System health check script.

Verifies that all components are properly configured and working.

Usage:
    python scripts/health_check.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def check_python_version():
    """Check Python version."""
    print("[1] Python Version")
    version = sys.version_info
    print(f"    Python {version.major}.{version.minor}.{version.micro}")

    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print("    WARNING: Python 3.9+ recommended")
        return False

    print("    OK")
    return True


def check_dependencies():
    """Check required dependencies."""
    print("\n[2] Dependencies")

    required = {
        'pandas': 'Data manipulation',
        'numpy': 'Numerical computing',
        'streamlit': 'Web interface',
        'sqlalchemy': 'Database ORM',
        'plotly': 'Visualization',
    }

    optional = {
        'vectorbt': 'Backtesting engine',
        'pypfopt': 'Portfolio optimization',
        'yfinance': 'US stock data',
        'finnhub': 'Finnhub API',
        'FinMind': 'Taiwan stock data',
        'statsmodels': 'Statistical models',
        'scipy': 'Scientific computing',
    }

    all_ok = True

    print("    Required:")
    for package, desc in required.items():
        try:
            __import__(package)
            print(f"      {package}: OK ({desc})")
        except ImportError:
            print(f"      {package}: MISSING ({desc})")
            all_ok = False

    print("    Optional:")
    for package, desc in optional.items():
        try:
            __import__(package)
            print(f"      {package}: OK ({desc})")
        except ImportError:
            print(f"      {package}: Not installed ({desc})")

    return all_ok


def check_core_modules():
    """Check core modules can be imported."""
    print("\n[3] Core Modules")

    modules = [
        ('core.database', 'DatabaseManager'),
        ('core.data_fetcher', 'DataManager'),
        ('core.backtester', 'BacktestEngine'),
        ('core.optimizer', 'PortfolioOptimizer'),
        ('core.risk', 'RiskCalculator'),
    ]

    all_ok = True

    for module_path, class_name in modules:
        try:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name, None)
            if cls:
                print(f"    {module_path}.{class_name}: OK")
            else:
                print(f"    {module_path}.{class_name}: Class not found")
                all_ok = False
        except Exception as e:
            print(f"    {module_path}: ERROR - {e}")
            all_ok = False

    return all_ok


def check_strategies():
    """Check strategy modules."""
    print("\n[4] Strategy Modules")

    strategies = [
        ('strategies.base', 'BaseStrategy'),
        ('strategies.mean_reversion', 'MeanReversionStrategy'),
        ('strategies.pairs_trading', 'PairsTradingStrategy'),
    ]

    all_ok = True

    for module_path, class_name in strategies:
        try:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name, None)
            if cls:
                print(f"    {module_path}.{class_name}: OK")
            else:
                print(f"    {module_path}.{class_name}: Class not found")
                all_ok = False
        except Exception as e:
            print(f"    {module_path}: ERROR - {e}")
            all_ok = False

    return all_ok


def check_environment():
    """Check environment variables."""
    print("\n[5] Environment Variables")

    import os
    from dotenv import load_dotenv

    env_file = project_root / '.env'

    if env_file.exists():
        load_dotenv(env_file)
        print(f"    .env file: Found")
    else:
        print(f"    .env file: Not found (using defaults)")

    env_vars = {
        'POSTGRES_HOST': 'localhost',
        'POSTGRES_PORT': '5432',
        'POSTGRES_DB': 'quant_trading',
        'FINMIND_API_TOKEN': None,
        'FINNHUB_API_KEY': None,
    }

    for var, default in env_vars.items():
        value = os.getenv(var, default)
        if value:
            # Mask sensitive values
            if 'TOKEN' in var or 'KEY' in var or 'PASSWORD' in var:
                display = value[:4] + '****' if len(value) > 4 else '****'
            else:
                display = value
            print(f"    {var}: {display}")
        else:
            print(f"    {var}: Not set")

    return True


def check_database():
    """Check database connection."""
    print("\n[6] Database Connection")

    try:
        from core.database import DatabaseManager
        db = DatabaseManager()

        if db.test_connection():
            print("    PostgreSQL: Connected")
            return True
        else:
            print("    PostgreSQL: Connection failed")
            print("    TIP: Run 'docker-compose up -d' to start the database")
            return False

    except Exception as e:
        print(f"    PostgreSQL: ERROR - {e}")
        print("    TIP: Database is optional for basic functionality")
        return False


def check_data_sources():
    """Check data source availability."""
    print("\n[7] Data Sources")

    # Test yfinance (no API key required)
    try:
        import yfinance as yf
        ticker = yf.Ticker("AAPL")
        info = ticker.info
        if info:
            print("    yfinance (US stocks): OK")
        else:
            print("    yfinance (US stocks): No data")
    except Exception as e:
        print(f"    yfinance (US stocks): ERROR - {e}")

    # Test FinMind
    try:
        import os
        token = os.getenv('FINMIND_API_TOKEN')
        if token:
            print("    FinMind (Taiwan stocks): Token configured")
        else:
            print("    FinMind (Taiwan stocks): No token (limited access)")
    except Exception as e:
        print(f"    FinMind (Taiwan stocks): ERROR - {e}")

    # Test Finnhub
    try:
        import os
        api_key = os.getenv('FINNHUB_API_KEY')
        if api_key:
            print("    Finnhub (US stocks): API key configured")
        else:
            print("    Finnhub (US stocks): No API key")
    except Exception as e:
        print(f"    Finnhub (US stocks): ERROR - {e}")

    return True


def check_pages():
    """Check Streamlit pages exist."""
    print("\n[8] Streamlit Pages")

    pages_dir = project_root / 'pages'
    expected_pages = [
        '1_Dashboard.py',
        '2_Data_Management.py',
        '3_Backtesting.py',
        '4_Portfolio.py',
        '5_Risk_Analysis.py',
        '6_Trade_Log.py',
    ]

    all_ok = True

    for page in expected_pages:
        page_path = pages_dir / page
        if page_path.exists():
            print(f"    {page}: OK")
        else:
            print(f"    {page}: MISSING")
            all_ok = False

    return all_ok


def main():
    """Run all health checks."""
    print("=" * 60)
    print("Quantitative Trading Tool - System Health Check")
    print("=" * 60)

    results = {
        'Python Version': check_python_version(),
        'Dependencies': check_dependencies(),
        'Core Modules': check_core_modules(),
        'Strategies': check_strategies(),
        'Environment': check_environment(),
        'Database': check_database(),
        'Data Sources': check_data_sources(),
        'Streamlit Pages': check_pages(),
    }

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for check, status in results.items():
        status_str = "PASS" if status else "FAIL"
        print(f"    {check}: {status_str}")

    print(f"\n    Result: {passed}/{total} checks passed")

    if passed == total:
        print("\n    System is ready!")
        print("    Run 'streamlit run app.py' to start the application.")
    else:
        print("\n    Some checks failed. Review the output above for details.")

    print("=" * 60)

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
