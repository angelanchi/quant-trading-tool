# Quantitative Trading Tool — CQF Learning Panel

Personal learning project, 2026-01 to 2026-10. Not investment advice.

## Starting point

While studying for the CQF (Certificate in Quantitative Finance), I wanted to check
whether the textbook models still behave as expected on Taiwan and US stock data,
so I implemented each model myself instead of calling a library.

## What I noticed

- The Taiwan price API returned closing prices that were not dividend-adjusted, so I
  added an adjusted-price cache and made it the default source.
- The backtester did not include the 0.3 % Taiwan securities transaction tax on sales,
  so I wrote a separate cost module for the panel.
- I was shown investment-group material promising 30–60 % in 3–7 trading days. Under a
  GBM model with the stock's own volatility, such moves are very unlikely, and the
  material followed a typical pump-and-dump structure.

## Tools I built

- `core/quant/` — GBM simulation, EWMA / GARCH(1,1) volatility, historical / parametric /
  Cornish-Fisher VaR with Kupiec and Christoffersen backtests, CAPM decomposition,
  Black-Scholes pricing and Greeks, Kelly and volatility-target sizing, bond pricing,
  duration, convexity and Vasicek. Each is checked against textbook values
  (`tests/test_quant.py`; 130 tests in total).
- `core/quant/claims.py` — a claim checker that turns a promised return over a horizon
  into a probability, plus a red-flag checklist.
- `core/quant/costs.py` — Taiwan / US trading costs for the panel.
- A Streamlit panel that strings these into a six-step routine: market regime → screening →
  scenario pricing → risk & position sizing → claim check → execution & review.
  When a data source is unreachable it switches to clearly labelled demo data.

| Layer | Stack |
|---|---|
| UI | Streamlit, Plotly |
| Quant | NumPy, pandas, SciPy, statsmodels |
| Backtest / portfolio | VectorBT, PyPortfolioOpt (optional; built-in fallbacks) |
| Data | FinMind (TW), Finnhub / yfinance (US), FRED |
| Infra | pytest, GitHub Actions; optional PostgreSQL, Docker, FastAPI |

```bash
python -m pytest tests/ -q      # run the test suite
streamlit run app.py            # start the panel at http://localhost:8501
```

Design notes: `docs/CQF_PANEL_REDESIGN.md` · Curriculum mapping: `docs/LEARNING_CURRICULUM.md`

### 中文簡介

準備 CQF 時，想確認教科書模型放到台股與美股資料上是否仍成立，因此每個模型都自己實作，
並以教科書數值做單元測試。過程中發現價格未還原權值、回測未計證交稅等問題，
也把一份投資社團「報酬承諾」轉成機率來檢驗，最後整合成六步驟的研究面板。

---

## Features (full list)

A comprehensive quantitative trading platform supporting Taiwan and US stock markets, built for learning CQF (Certificate in Quantitative Finance) concepts and practical trading assistance.


- **Data Management**: Fetch stock data from Taiwan (FinMind) and US markets (Finnhub/yfinance)
- **Backtesting Engine**: Test trading strategies with historical data using VectorBT
- **Portfolio Optimization**: Markowitz Mean-Variance, Black-Litterman, Risk Parity (HRP)
- **Risk Analysis**: VaR, CVaR, Sharpe/Sortino/Calmar ratios, drawdown analysis
- **Walk-Forward Optimization**: Robust parameter optimization with out-of-sample testing
- **Alert System**: Price, signal, and drawdown alerts with customizable handlers
- **Report Generation**: HTML reports with interactive Plotly charts
- **Trade Logging**: Manual trade recording with P&L tracking
- **Web Dashboard**: Interactive Streamlit interface
- **CLI Tool**: Command-line interface for all operations
- **REST API**: FastAPI-based programmatic access
- **Docker Support**: Containerized deployment

## Quick Start

### Prerequisites

- Python 3.9+
- Docker (for PostgreSQL database)
- API Keys (optional):
  - FinMind token (Taiwan stocks)
  - Finnhub API key (US stocks)

### Installation

```bash
# Clone or navigate to project directory
cd quant_trading_tool

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL database (optional, for data persistence)
docker-compose up -d

# Configure environment variables
cp .env.example .env
# Edit .env with your API keys
cp config/watchlists.example.json config/watchlists.json

# Run the application
streamlit run app.py
```

### Access the Application

Open your browser and navigate to: `http://localhost:8501`

## Project Structure

```
quant_trading_tool/
├── app.py                    # Main Streamlit entry point
├── cli.py                    # Command-line interface
├── api.py                    # FastAPI REST API
├── pages/                    # Streamlit pages
│   ├── 1_Dashboard.py        # Portfolio overview
│   ├── 2_Data_Management.py  # Stock data management
│   ├── 3_Backtesting.py      # Strategy backtesting
│   ├── 4_Portfolio.py        # Portfolio optimization
│   ├── 5_Risk_Analysis.py    # Risk metrics
│   └── 6_Trade_Log.py        # Trade recording
├── core/                     # Core modules
│   ├── database.py           # PostgreSQL ORM models
│   ├── data_fetcher.py       # Data fetching (FinMind, Finnhub, yfinance)
│   ├── backtester.py         # Backtesting engine
│   ├── optimizer.py          # Portfolio optimization
│   ├── risk.py               # Risk calculations
│   ├── walk_forward.py       # Walk-forward optimization
│   ├── alerts.py             # Alert system
│   └── report.py             # HTML report generation
├── strategies/               # Trading strategies
│   ├── base.py               # Base strategy class
│   ├── mean_reversion.py     # Mean reversion strategies
│   ├── pairs_trading.py      # Pairs trading strategy
│   ├── momentum.py           # Momentum strategies
│   └── registry.py           # Strategy registry
├── scripts/                  # Utility scripts
│   ├── init_database.py      # Database initialization
│   ├── download_data.py      # Batch data download
│   ├── run_backtest.py       # CLI backtest runner
│   ├── health_check.py       # System health check
│   └── generate_sample_data.py  # Sample data generator
├── examples/                 # Usage examples
│   ├── basic_usage.py        # Basic data fetching
│   ├── backtest_example.py   # Backtesting examples
│   ├── optimization_example.py  # Portfolio optimization
│   ├── risk_analysis_example.py # Risk metrics
│   ├── pairs_trading_example.py # Pairs trading
│   ├── momentum_example.py   # Momentum strategies
│   ├── alerts_example.py     # Alert system
│   ├── report_example.py     # Report generation
│   └── walk_forward_example.py  # Walk-forward optimization
├── config/                   # Configuration
│   ├── settings.py           # Settings management
│   └── logging_config.py     # Logging configuration
├── tests/                    # Unit tests
├── notebooks/                # Jupyter notebooks
│   └── quickstart.ipynb      # Interactive tutorial
├── docker-compose.yml        # PostgreSQL container
├── docker-compose.full.yml   # Full stack deployment
├── Dockerfile                # Container build
├── Makefile                  # Build commands
├── run.bat                   # Windows launcher
├── requirements.txt          # Python dependencies
└── .env.example              # Environment variables template
```

## Core Modules

### Data Fetcher

```python
from core import DataManager

dm = DataManager()

# Fetch Taiwan stock (auto-detected by 4-digit symbol)
tw_data = dm.fetch_ohlcv('2330', '2023-01-01', '2023-12-31')

# Fetch US stock
us_data = dm.fetch_ohlcv('AAPL', '2023-01-01', '2023-12-31')

# Get real-time quote
quote = dm.fetch_quote('AAPL')
```

### Backtesting

```python
from core import BacktestEngine
import pandas as pd

engine = BacktestEngine()

# Run mean reversion strategy
result = engine.run_mean_reversion(
    prices,
    lookback=20,
    entry_zscore=2.0,
    exit_zscore=0.5,
    initial_capital=100000
)

print(f"Total Return: {result.total_return:.2%}")
print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
print(f"Max Drawdown: {result.max_drawdown:.2%}")
```

### Portfolio Optimization

```python
from core import PortfolioOptimizer

optimizer = PortfolioOptimizer()

# Maximum Sharpe ratio
result = optimizer.max_sharpe(prices, risk_free_rate=0.02)
print(f"Optimal Weights: {result.weights}")
print(f"Expected Return: {result.expected_return:.2%}")
print(f"Volatility: {result.volatility:.2%}")

# Risk Parity (HRP)
result = optimizer.risk_parity(prices)

# Black-Litterman with views
views = {'AAPL': 0.15}  # 15% expected return for AAPL
result = optimizer.black_litterman(prices, views=views)
```

### Risk Analysis

```python
from core import RiskCalculator

returns = prices.pct_change().dropna()
calc = RiskCalculator(returns, risk_free_rate=0.02)

# Get all metrics
metrics = calc.calculate_all()
print(metrics.summary())

# Individual metrics
print(f"VaR 95%: {calc.var_historical(0.95):.2%}")
print(f"CVaR 95%: {calc.cvar(0.95):.2%}")
print(f"Sharpe Ratio: {calc.sharpe_ratio():.2f}")
```

## Trading Strategies

### Built-in Strategies

1. **Mean Reversion**: Trades based on Z-score deviation from rolling mean
2. **MA Crossover**: Fast/slow moving average crossover signals
3. **RSI Strategy**: Oversold/overbought based on RSI indicator
4. **Bollinger Bands**: Trades at band boundaries
5. **Pairs Trading**: Cointegration-based statistical arbitrage

### Custom Strategy

```python
from strategies import BaseStrategy
import pandas as pd

class MyStrategy(BaseStrategy):
    def __init__(self, param1=10, **kwargs):
        super().__init__(name="MyStrategy", param1=param1, **kwargs)
        self.param1 = param1

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        # Your signal logic here
        signals = pd.DataFrame(index=prices.index)
        # ...
        return signals
```

### Momentum Strategies

```python
from strategies import (
    MomentumStrategy,
    TrendFollowingStrategy,
    DualMomentumStrategy,
    BreakoutStrategy
)

# Classic momentum
momentum = MomentumStrategy(lookback=20, ma_period=50)
signals = momentum.generate_signals(prices)

# Trend following with ADX filter
trend = TrendFollowingStrategy(adx_period=14, adx_threshold=25)

# Dual momentum (absolute + relative)
dual = DualMomentumStrategy(abs_lookback=12, rel_lookback=6)

# Breakout strategy
breakout = BreakoutStrategy(lookback=20, volume_factor=1.5)
```

## Command-Line Interface (CLI)

The CLI provides full access to all functionality from the terminal.

### Basic Usage

```bash
# Show help
python cli.py --help

# Show subcommand help
python cli.py data --help
python cli.py backtest --help
```

### Data Commands

```bash
# Fetch stock data
python cli.py data fetch AAPL --start 2023-01-01 --end 2023-12-31

# Fetch multiple symbols
python cli.py data fetch AAPL MSFT GOOGL --start 2023-01-01

# Search for symbols
python cli.py data search "台積電"
python cli.py data search "Apple"

# Get real-time quote
python cli.py data quote AAPL
```

### Backtest Commands

```bash
# Run mean reversion strategy
python cli.py backtest run --strategy mean_reversion --symbols AAPL,MSFT \
    --start 2022-01-01 --end 2023-12-31 --capital 100000

# Run MA crossover strategy
python cli.py backtest run --strategy ma_crossover --symbols AAPL \
    --params '{"fast_period": 10, "slow_period": 30}'

# List available strategies
python cli.py backtest list
```

### Portfolio Commands

```bash
# Optimize portfolio (max Sharpe)
python cli.py portfolio optimize --method max_sharpe --symbols AAPL,MSFT,GOOGL,AMZN

# Minimum volatility
python cli.py portfolio optimize --method min_volatility --symbols AAPL,MSFT,GOOGL

# Risk parity
python cli.py portfolio optimize --method risk_parity --symbols AAPL,MSFT,GOOGL

# Black-Litterman with views
python cli.py portfolio optimize --method black_litterman --symbols AAPL,MSFT \
    --views '{"AAPL": 0.15}'
```

### Risk Commands

```bash
# Calculate risk metrics
python cli.py risk calculate --symbols AAPL,MSFT --start 2023-01-01

# Detailed report
python cli.py risk calculate --symbols AAPL,MSFT --detailed
```

### Report Commands

```bash
# Generate backtest report
python cli.py report backtest --strategy mean_reversion --symbols AAPL,MSFT \
    --output reports/backtest_report.html

# Generate risk report
python cli.py report risk --symbols AAPL,MSFT --output reports/risk_report.html
```

### Health Check

```bash
# Check system status
python cli.py health
```

## REST API

The REST API provides programmatic access via HTTP endpoints.

### Starting the API Server

```bash
# Start API server
uvicorn api:app --reload --port 8000

# Or use the CLI
python api.py
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API information |
| GET | `/health` | System health check |
| GET | `/data/{symbol}` | Fetch stock data |
| POST | `/backtest` | Run backtest |
| POST | `/optimize` | Optimize portfolio |
| POST | `/risk` | Calculate risk metrics |
| GET | `/strategies` | List available strategies |
| GET | `/methods` | List optimization methods |

### API Examples

```bash
# Fetch stock data
curl http://localhost:8000/data/AAPL?start=2023-01-01&end=2023-12-31

# Run backtest
curl -X POST http://localhost:8000/backtest \
    -H "Content-Type: application/json" \
    -d '{
        "symbols": ["AAPL", "MSFT"],
        "strategy": "mean_reversion",
        "initial_capital": 100000,
        "parameters": {"lookback": 20, "entry_zscore": 2.0}
    }'

# Optimize portfolio
curl -X POST http://localhost:8000/optimize \
    -H "Content-Type: application/json" \
    -d '{
        "symbols": ["AAPL", "MSFT", "GOOGL"],
        "method": "max_sharpe"
    }'

# Calculate risk
curl -X POST http://localhost:8000/risk \
    -H "Content-Type: application/json" \
    -d '{
        "symbols": ["AAPL", "MSFT"],
        "start_date": "2023-01-01"
    }'
```

### Python API Client

```python
import requests

BASE_URL = "http://localhost:8000"

# Fetch data
response = requests.get(f"{BASE_URL}/data/AAPL", params={
    "start": "2023-01-01",
    "end": "2023-12-31"
})
data = response.json()

# Run backtest
response = requests.post(f"{BASE_URL}/backtest", json={
    "symbols": ["AAPL", "MSFT"],
    "strategy": "mean_reversion",
    "initial_capital": 100000
})
result = response.json()
print(f"Sharpe Ratio: {result['sharpe_ratio']}")
```

## Walk-Forward Optimization

Avoid overfitting with out-of-sample testing.

```python
from core import WalkForwardOptimizer, BacktestEngine

engine = BacktestEngine()

def strategy_func(data, lookback=20, entry_zscore=2.0):
    return engine.run_mean_reversion(
        data,
        lookback=lookback,
        entry_zscore=entry_zscore,
        initial_capital=100000
    )

param_grid = {
    'lookback': [10, 15, 20, 25, 30],
    'entry_zscore': [1.5, 2.0, 2.5]
}

optimizer = WalkForwardOptimizer(
    train_period=252,  # 1 year training
    test_period=63,    # 3 months testing
    step_size=63       # Move forward 3 months
)

result = optimizer.run(prices, param_grid, strategy_func, 'sharpe_ratio')

print(f"Combined Test Sharpe: {result.combined_test_sharpe:.2f}")
print(f"Overfitting Ratio: {result.overfitting_ratio:.2f}")
# Ratio close to 1.0 = less overfitting
```

### Rolling Optimization

```python
from core import RollingOptimizer

optimizer = RollingOptimizer(
    lookback=252,           # Use 1 year history
    reoptimize_frequency=21 # Re-optimize monthly
)

results = optimizer.run(prices, param_grid, strategy_func, 'sharpe_ratio')
print(results[['date', 'lookback', 'metric']])
```

## Alert System

Set up price, signal, and drawdown alerts.

```python
from core import AlertManager, AlertType, console_alert_handler

# Create manager with console handler
manager = AlertManager()
manager.add_handler(console_alert_handler)

# Price alerts
manager.create_price_alert('AAPL', 180.0, 'above')  # Alert when AAPL > 180
manager.create_price_alert('AAPL', 150.0, 'below')  # Alert when AAPL < 150

# Signal alert
manager.create_signal_alert('AAPL', 'MeanReversion', 'buy')

# Drawdown alert
manager.create_drawdown_alert('AAPL', 0.10)  # Alert on 10% drawdown

# Check alerts (in your trading loop)
manager.check_price_alerts('AAPL', current_price=185.0)

# List active alerts
for alert in manager.list_alerts():
    print(f"{alert.alert_type}: {alert.symbol}")
```

### Custom Alert Handler

```python
def email_alert_handler(event):
    """Send email on alert trigger."""
    import smtplib
    # Your email logic here
    print(f"Sending email for: {event.alert.symbol}")

manager.add_handler(email_alert_handler)
```

## Report Generation

Generate HTML reports with interactive charts.

```python
from core import ReportGenerator, generate_backtest_report

# Quick backtest report
html = generate_backtest_report(
    backtest_result,
    strategy_name="Mean Reversion",
    symbols=["AAPL", "MSFT"],
    parameters={"lookback": 20}
)

# Save to file
with open("backtest_report.html", "w") as f:
    f.write(html)

# Full report with multiple sections
generator = ReportGenerator("Portfolio Analysis Report")
generator.add_header()

# Add backtest results
generator.generate_backtest_report(result, "Mean Reversion", symbols, params)

# Add risk analysis
generator.generate_risk_report(risk_metrics, returns)

# Add portfolio optimization
generator.generate_portfolio_report(optimization_result, "Max Sharpe")

generator.add_footer()
generator.save("full_report.html")
```

## Supported Markets

| Market | Data Source | Symbol Format | Example |
|--------|-------------|---------------|---------|
| Taiwan (TWSE) | FinMind | 4-digit number | 2330, 2317 |
| US (NYSE/NASDAQ) | Finnhub + yfinance | Ticker symbol | AAPL, MSFT |

## Configuration

### Environment Variables (.env)

```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=quant_trading
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# API Keys
FINMIND_TOKEN=your_finmind_token
FINNHUB_API_KEY=your_finnhub_key

# App Settings
DEBUG=false
LOG_LEVEL=INFO
```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=core --cov=strategies --cov-report=html

# Run specific test file
pytest tests/test_risk.py -v
```

## Dependencies

### Core
- streamlit >= 1.31.0
- pandas >= 2.0.0
- numpy >= 1.24.0
- plotly >= 5.18.0

### Database
- sqlalchemy >= 2.0.25
- psycopg2-binary >= 2.9.9

### Backtesting & Optimization
- vectorbt >= 0.26.0
- pypfopt >= 1.5.5
- riskfolio-lib >= 4.0.0

### Data Sources
- yfinance >= 0.2.36
- finnhub-python >= 2.4.18
- FinMind >= 1.4.0

### Analysis
- statsmodels >= 0.14.0
- scipy >= 1.11.0
- quantstats >= 0.0.62

## Docker Deployment

### Quick Start with Docker

```bash
# Build and run full stack (PostgreSQL + pgAdmin + App)
docker-compose -f docker-compose.full.yml up -d

# Access services:
# - Streamlit App: http://localhost:8501
# - pgAdmin: http://localhost:5050 (admin@admin.com / admin)
# - API: http://localhost:8000
```

### Build Image Only

```bash
# Build Docker image
docker build -t quant-trading-tool .

# Run container
docker run -p 8501:8501 quant-trading-tool
```

### Docker Compose Services

| Service | Port | Description |
|---------|------|-------------|
| app | 8501 | Streamlit web dashboard |
| api | 8000 | FastAPI REST API |
| postgres | 5432 | PostgreSQL database |
| pgadmin | 5050 | Database admin UI |

### Production Deployment

```bash
# Set environment variables
export POSTGRES_PASSWORD=your_secure_password
export FINMIND_TOKEN=your_token
export FINNHUB_API_KEY=your_key

# Deploy with production settings
docker-compose -f docker-compose.full.yml up -d --build
```

## Windows Quick Start (run.bat)

```batch
# Start the web application
run.bat app

# Run tests
run.bat test

# Start database
run.bat db

# Initialize database tables
run.bat init-db

# Download sample data
run.bat download

# Run backtest example
run.bat backtest

# Run all examples
run.bat example

# System health check
run.bat health

# Generate sample data (offline testing)
run.bat sample-data

# Start API server
run.bat api
```

## Example Scripts

Run example scripts to learn the tool:

```bash
# Basic data fetching and analysis
python examples/basic_usage.py

# Backtesting strategies
python examples/backtest_example.py

# Portfolio optimization
python examples/optimization_example.py

# Risk analysis
python examples/risk_analysis_example.py

# Pairs trading
python examples/pairs_trading_example.py

# Momentum strategies
python examples/momentum_example.py

# Alert system
python examples/alerts_example.py

# Report generation
python examples/report_example.py

# Walk-forward optimization
python examples/walk_forward_example.py
```

## Jupyter Notebook

Interactive tutorial available:

```bash
jupyter notebook notebooks/quickstart.ipynb
```

## Makefile Commands (Linux/Mac)

```bash
make install    # Install dependencies
make run        # Start Streamlit app
make test       # Run tests
make lint       # Run linting
make db         # Start PostgreSQL
make clean      # Clean cache files
make docker     # Build Docker image
```

## Troubleshooting

### Common Issues

**1. Database Connection Failed**
```bash
# Check if PostgreSQL is running
docker-compose ps

# Restart database
docker-compose restart postgres
```

**2. Missing API Keys**
```bash
# Create .env file
cp .env.example .env
# Edit .env with your API keys
cp config/watchlists.example.json config/watchlists.json
```

**3. Import Errors**
```bash
# Ensure you're in the project directory
cd quant_trading_tool

# Install dependencies
pip install -r requirements.txt
```

**4. VectorBT Installation Issues (Windows)**
```bash
# Install Visual C++ Build Tools first
# Then install vectorbt
pip install vectorbt
```

### Health Check

Run the health check to verify system status:

```bash
python scripts/health_check.py
# Or
python cli.py health
```

## License

This project is for educational purposes.

## Acknowledgments

- CQF (Certificate in Quantitative Finance) for theoretical foundations
- VectorBT for backtesting framework
- PyPortfolioOpt for optimization algorithms
- FinMind for Taiwan market data
