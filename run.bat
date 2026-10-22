@echo off
REM Quantitative Trading Tool - Windows Launcher
REM Usage: run.bat [command]

setlocal enabledelayedexpansion

REM Always run from the project folder (double-click safe)
cd /d "%~dp0"

REM Prefer the project virtual environment when it exists
set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

REM Double-click (no argument) = start the app
if "%1"=="" goto app
if "%1"=="help" goto help
if "%1"=="app" goto app
if "%1"=="test" goto test
if "%1"=="install" goto install
if "%1"=="db" goto db
if "%1"=="init-db" goto init-db
if "%1"=="download" goto download
if "%1"=="backtest" goto backtest
if "%1"=="example" goto example
if "%1"=="health" goto health
if "%1"=="sample-data" goto sample-data
if "%1"=="scan" goto scan
if "%1"=="check" goto check
if "%1"=="fetch" goto fetch

echo Unknown command: %1
goto help

:help
echo.
echo Quantitative Trading Tool - Command Runner
echo ==========================================
echo.
echo Usage: run.bat [command] [options]
echo.
echo Commands:
echo   app         Start Streamlit web application
echo   test        Run unit tests
echo   install     Install Python dependencies
echo   check       Check which packages are installed
echo   db          Start PostgreSQL database (Docker)
echo   init-db     Initialize database tables
echo   download    Download stock data (use: run.bat download AAPL,MSFT)
echo   backtest    Run backtest (use: run.bat backtest mean_reversion AAPL)
echo   example     Run example script (use: run.bat example basic)
echo   health      Run system health check
echo   scan        Run daily fundamental/sentiment/multi-factor scan
echo   fetch       Download real prices (Yahoo adjusted, FinMind fallback) + FRED rates
echo   sample-data Generate sample data for testing
echo   help        Show this help message
echo.
goto end

:app
echo Starting Streamlit application with %PY% ...
"%PY%" -c "import streamlit" 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] streamlit is not installed for %PY%
    echo Run:  run.bat install
    pause
    goto end
)
"%PY%" -m streamlit run app.py
if errorlevel 1 pause
goto end

:test
echo Running unit tests...
if "%2"=="" (
    "%PY%" -m pytest tests/ -v
) else (
    "%PY%" -m pytest tests/test_%2.py -v
)
goto end

:install
if not exist ".venv\Scripts\python.exe" (
    echo Creating project virtual environment .venv ...
    python -m venv .venv
    set "PY=.venv\Scripts\python.exe"
)
echo.
echo ======================================
echo  Environment Info
echo ======================================
echo Python:
"%PY%" --version 2>&1
echo Location:
echo %PY%
echo Pip:
"%PY%" -m pip --version 2>&1
echo.
echo ======================================
echo  Installing Core Dependencies...
echo ======================================
REM IMPORTANT: Use "python -m pip" instead of "pip" to ensure
REM packages install to the SAME Python that runs streamlit
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [WARNING] Some core packages failed. Trying one by one...
    for /f "usebackq tokens=*" %%a in (`findstr /v /b "#" requirements.txt`) do (
        if not "%%a"=="" (
            echo Installing: %%a
            "%PY%" -m pip install %%a 2>nul
        )
    )
)
echo.
echo ======================================
echo  Installing Optional Dependencies...
echo ======================================
echo  (These may fail on some systems - that's OK)
echo.
if exist requirements-optional.txt (
    for /f "usebackq tokens=*" %%a in (`findstr /v /b "#" requirements-optional.txt`) do (
        if not "%%a"=="" (
            echo Installing: %%a
            "%PY%" -m pip install %%a 2>nul
            if errorlevel 1 echo   [SKIP] %%a install failed - optional feature disabled
        )
    )
)
echo.
echo ======================================
echo  Install complete! Verifying...
echo ======================================
goto check_packages

:check
echo.
echo ======================================
echo  Environment Info
echo ======================================
echo Python:
"%PY%" --version 2>&1
echo Location:
echo %PY%
echo.

:check_packages
echo.
echo --- Critical packages ---
"%PY%" -c "import yfinance; print('  yfinance: OK (v' + yfinance.__version__ + ')')" 2>nul || echo   [FAIL] yfinance: MISSING - run: "%PY%" -m pip install yfinance
"%PY%" -c "import FinMind; print('  FinMind: OK')" 2>nul || echo   [FAIL] FinMind: MISSING - run: "%PY%" -m pip install FinMind
"%PY%" -c "import pandas_datareader; print('  pandas-datareader: OK')" 2>nul || echo   [FAIL] pandas-datareader: MISSING - run: "%PY%" -m pip install pandas-datareader
"%PY%" -c "import streamlit; print('  streamlit: OK (v' + streamlit.__version__ + ')')" 2>nul || echo   [FAIL] streamlit: MISSING
"%PY%" -c "import plotly; print('  plotly: OK')" 2>nul || echo   [FAIL] plotly: MISSING
"%PY%" -c "import dotenv; print('  python-dotenv: OK')" 2>nul || echo   [FAIL] python-dotenv: MISSING
echo.
echo --- Optional packages ---
"%PY%" -c "import vectorbt; print('  vectorbt: OK')" 2>nul || echo   [skip] vectorbt: not installed (backtesting limited)
"%PY%" -c "import pypfopt; print('  pypfopt: OK')" 2>nul || echo   [skip] pypfopt: not installed (portfolio optimization limited)
"%PY%" -c "import riskfolio; print('  riskfolio: OK')" 2>nul || echo   [skip] riskfolio: not installed
"%PY%" -c "import quantstats; print('  quantstats: OK')" 2>nul || echo   [skip] quantstats: not installed
echo.
goto end

:db
echo Starting PostgreSQL database...
docker-compose up -d
echo.
echo Database started. Access pgAdmin at http://localhost:5050
echo   Email: admin@admin.com
echo   Password: admin
goto end

:init-db
echo Initializing database...
"%PY%" scripts/init_database.py
goto end

:download
if "%2"=="" (
    echo Usage: run.bat download SYMBOL1,SYMBOL2 [start_date] [end_date]
    echo Example: run.bat download AAPL,MSFT 2023-01-01 2023-12-31
    goto end
)
set symbols=%2
set start_date=%3
set end_date=%4
if "%start_date%"=="" set start_date=2022-01-01
if "%end_date%"=="" set end_date=2024-01-01
echo Downloading data for: %symbols%
"%PY%" scripts/download_data.py --symbols %symbols% --start %start_date% --end %end_date%
goto end

:backtest
if "%2"=="" (
    echo Usage: run.bat backtest STRATEGY SYMBOLS [options]
    echo.
    echo Strategies: mean_reversion, ma_crossover, rsi, bollinger
    echo Example: run.bat backtest mean_reversion AAPL,MSFT
    goto end
)
set strategy=%2
set symbols=%3
if "%symbols%"=="" set symbols=AAPL
echo Running %strategy% backtest on %symbols%...
"%PY%" scripts/run_backtest.py --strategy %strategy% --symbols %symbols%
goto end

:example
if "%2"=="" (
    echo Usage: run.bat example [name]
    echo.
    echo Available examples:
    echo   basic          - Basic data fetching and analysis
    echo   backtest       - Backtesting strategies
    echo   optimization   - Portfolio optimization
    echo   risk           - Risk analysis
    echo   pairs          - Pairs trading
    echo   momentum       - Momentum strategies
    echo   alerts         - Alert system
    echo   report         - Report generation
    goto end
)
if "%2"=="basic" "%PY%" examples/basic_usage.py
if "%2"=="backtest" "%PY%" examples/backtest_example.py
if "%2"=="optimization" "%PY%" examples/optimization_example.py
if "%2"=="risk" "%PY%" examples/risk_analysis_example.py
if "%2"=="pairs" "%PY%" examples/pairs_trading_example.py
if "%2"=="momentum" "%PY%" examples/momentum_example.py
if "%2"=="alerts" "%PY%" examples/alerts_example.py
if "%2"=="report" "%PY%" examples/report_example.py
goto end

:health
echo Running system health check...
"%PY%" scripts/health_check.py
goto end

:sample-data
if "%2"=="" (
    echo Usage: run.bat sample-data SYMBOLS [--output DIR]
    echo Example: run.bat sample-data AAPL,MSFT,GOOGL --output data
    "%PY%" scripts/generate_sample_data.py --help
    goto end
)
"%PY%" scripts/generate_sample_data.py --symbols %2 %3 %4 %5
goto end

:scan
echo Running daily scan...
if "%2"=="--fundamental-only" (
    "%PY%" scripts/daily_scan.py --fundamental-only
) else if "%2"=="" (
    "%PY%" scripts/daily_scan.py
) else (
    "%PY%" scripts/daily_scan.py --symbols %2
)
goto end

:fetch
echo Downloading real market data...
"%PY%" -X utf8 scripts/fetch_market_data.py %2 %3 %4 %5
goto end

:end
endlocal
