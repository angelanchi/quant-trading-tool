# -*- coding: utf-8 -*-
"""
REST API for quantitative trading tool.

Provides programmatic access to all trading tool functionality.

Usage:
    uvicorn api:app --reload --port 8000

Endpoints:
    GET  /                      - API info
    GET  /health                - Health check
    GET  /data/{symbol}         - Fetch stock data
    POST /backtest              - Run backtest
    POST /optimize              - Optimize portfolio
    POST /risk                  - Calculate risk metrics
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import json

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("FastAPI not installed. Run: pip install fastapi uvicorn")


if FASTAPI_AVAILABLE:

    app = FastAPI(
        title="Quantitative Trading Tool API",
        description="REST API for quantitative trading analysis",
        version="1.0.0"
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request/Response Models

    class BacktestRequest(BaseModel):
        symbols: List[str] = Field(..., description="List of stock symbols")
        strategy: str = Field("mean_reversion", description="Strategy name")
        start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
        end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")
        initial_capital: float = Field(100000, description="Initial capital")
        parameters: Optional[Dict[str, Any]] = Field(None, description="Strategy parameters")

    class BacktestResponse(BaseModel):
        strategy: str
        symbols: List[str]
        total_return: float
        cagr: float
        sharpe_ratio: float
        sortino_ratio: float
        max_drawdown: float
        win_rate: float
        total_trades: int

    class OptimizeRequest(BaseModel):
        symbols: List[str] = Field(..., description="List of stock symbols")
        method: str = Field("max_sharpe", description="Optimization method")
        start_date: Optional[str] = Field(None, description="Start date")
        end_date: Optional[str] = Field(None, description="End date")
        risk_free_rate: float = Field(0.02, description="Risk-free rate")

    class OptimizeResponse(BaseModel):
        method: str
        weights: Dict[str, float]
        expected_return: float
        volatility: float
        sharpe_ratio: float

    class RiskRequest(BaseModel):
        symbols: List[str] = Field(..., description="List of stock symbols")
        start_date: Optional[str] = Field(None, description="Start date")
        end_date: Optional[str] = Field(None, description="End date")
        risk_free_rate: float = Field(0.02, description="Risk-free rate")

    class RiskResponse(BaseModel):
        var_95: float
        cvar_95: float
        sharpe_ratio: float
        sortino_ratio: float
        max_drawdown: float
        volatility: float

    # Helper functions

    def get_default_dates():
        """Get default date range."""
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=365*2)).strftime('%Y-%m-%d')
        return start_date, end_date

    def fetch_prices(symbols: List[str], start_date: str, end_date: str):
        """Fetch price data for symbols."""
        from core import DataManager
        import pandas as pd

        dm = DataManager()
        prices = {}

        for symbol in symbols:
            df = dm.fetch_ohlcv(symbol, start_date, end_date)
            if df is not None and not df.empty:
                prices[symbol] = df['close']

        if not prices:
            return None

        return pd.DataFrame(prices).dropna()

    # Endpoints

    @app.get("/")
    async def root():
        """API information."""
        return {
            "name": "Quantitative Trading Tool API",
            "version": "1.0.0",
            "endpoints": [
                {"path": "/health", "method": "GET", "description": "Health check"},
                {"path": "/data/{symbol}", "method": "GET", "description": "Fetch stock data"},
                {"path": "/backtest", "method": "POST", "description": "Run backtest"},
                {"path": "/optimize", "method": "POST", "description": "Optimize portfolio"},
                {"path": "/risk", "method": "POST", "description": "Calculate risk metrics"},
            ]
        }

    @app.get("/health")
    async def health_check():
        """System health check."""
        checks = {
            "api": True,
            "database": False,
            "data_fetcher": False
        }

        # Check database
        try:
            from core import DatabaseManager
            db = DatabaseManager()
            checks["database"] = db.test_connection()
        except:
            pass

        # Check data fetcher
        try:
            from core import DataManager
            dm = DataManager()
            checks["data_fetcher"] = True
        except:
            pass

        status = "healthy" if all(checks.values()) else "degraded"

        return {
            "status": status,
            "checks": checks,
            "timestamp": datetime.now().isoformat()
        }

    @app.get("/data/{symbol}")
    async def get_stock_data(
        symbol: str,
        start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
        end: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
        limit: int = Query(100, description="Maximum records to return")
    ):
        """Fetch stock price data."""
        from core import DataManager

        default_start, default_end = get_default_dates()
        start_date = start or default_start
        end_date = end or default_end

        dm = DataManager()
        df = dm.fetch_ohlcv(symbol.upper(), start_date, end_date)

        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {symbol}")

        # Convert to records
        df = df.tail(limit)
        records = df.reset_index().to_dict(orient='records')

        # Convert timestamps
        for record in records:
            if 'date' in record:
                record['date'] = str(record['date'])[:10]

        return {
            "symbol": symbol.upper(),
            "start_date": start_date,
            "end_date": end_date,
            "count": len(records),
            "data": records
        }

    @app.post("/backtest", response_model=BacktestResponse)
    async def run_backtest(request: BacktestRequest):
        """Run a backtest with specified strategy."""
        from core import BacktestEngine

        default_start, default_end = get_default_dates()
        start_date = request.start_date or default_start
        end_date = request.end_date or default_end

        # Fetch data
        prices_df = fetch_prices(request.symbols, start_date, end_date)

        if prices_df is None or prices_df.empty:
            raise HTTPException(status_code=400, detail="No price data available")

        engine = BacktestEngine()
        params = request.parameters or {}

        try:
            if request.strategy == 'mean_reversion':
                result = engine.run_mean_reversion(
                    prices_df,
                    lookback=params.get('lookback', 20),
                    entry_zscore=params.get('entry_zscore', 2.0),
                    exit_zscore=params.get('exit_zscore', 0.5),
                    initial_capital=request.initial_capital
                )
            elif request.strategy == 'ma_crossover':
                result = engine.run_ma_crossover(
                    prices_df,
                    fast_period=params.get('fast_period', 10),
                    slow_period=params.get('slow_period', 30),
                    initial_capital=request.initial_capital
                )
            else:
                raise HTTPException(status_code=400, detail=f"Unknown strategy: {request.strategy}")

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Backtest error: {str(e)}")

        return BacktestResponse(
            strategy=request.strategy,
            symbols=request.symbols,
            total_return=result.total_return,
            cagr=result.cagr,
            sharpe_ratio=result.sharpe_ratio,
            sortino_ratio=result.sortino_ratio,
            max_drawdown=result.max_drawdown,
            win_rate=result.win_rate,
            total_trades=result.total_trades
        )

    @app.post("/optimize", response_model=OptimizeResponse)
    async def optimize_portfolio(request: OptimizeRequest):
        """Optimize portfolio allocation."""
        from core import PortfolioOptimizer

        default_start, default_end = get_default_dates()
        start_date = request.start_date or default_start
        end_date = request.end_date or default_end

        # Fetch data
        prices_df = fetch_prices(request.symbols, start_date, end_date)

        if prices_df is None or len(prices_df.columns) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 assets for optimization")

        optimizer = PortfolioOptimizer()

        try:
            if request.method == 'max_sharpe':
                result = optimizer.max_sharpe(prices_df, risk_free_rate=request.risk_free_rate)
            elif request.method == 'min_volatility':
                result = optimizer.min_volatility(prices_df)
            elif request.method == 'risk_parity':
                result = optimizer.risk_parity(prices_df)
            elif request.method == 'equal_weight':
                result = optimizer.equal_weight(prices_df)
            else:
                raise HTTPException(status_code=400, detail=f"Unknown method: {request.method}")

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Optimization error: {str(e)}")

        return OptimizeResponse(
            method=request.method,
            weights=result.weights,
            expected_return=result.expected_return,
            volatility=result.volatility,
            sharpe_ratio=result.sharpe_ratio
        )

    @app.post("/risk", response_model=RiskResponse)
    async def calculate_risk(request: RiskRequest):
        """Calculate risk metrics."""
        from core import RiskCalculator

        default_start, default_end = get_default_dates()
        start_date = request.start_date or default_start
        end_date = request.end_date or default_end

        # Fetch data
        prices_df = fetch_prices(request.symbols, start_date, end_date)

        if prices_df is None or prices_df.empty:
            raise HTTPException(status_code=400, detail="No price data available")

        # Calculate portfolio returns (equal weight)
        returns = prices_df.pct_change().dropna()
        portfolio_returns = returns.mean(axis=1)

        try:
            calc = RiskCalculator(portfolio_returns, risk_free_rate=request.risk_free_rate)
            metrics = calc.calculate_all()

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Risk calculation error: {str(e)}")

        return RiskResponse(
            var_95=metrics.var_95_historical,
            cvar_95=metrics.cvar_95,
            sharpe_ratio=metrics.sharpe_ratio,
            sortino_ratio=metrics.sortino_ratio,
            max_drawdown=metrics.max_drawdown,
            volatility=metrics.volatility
        )

    @app.get("/strategies")
    async def list_strategies():
        """List available strategies."""
        return {
            "strategies": [
                {
                    "name": "mean_reversion",
                    "description": "Z-score based mean reversion",
                    "parameters": {
                        "lookback": {"type": "int", "default": 20},
                        "entry_zscore": {"type": "float", "default": 2.0},
                        "exit_zscore": {"type": "float", "default": 0.5}
                    }
                },
                {
                    "name": "ma_crossover",
                    "description": "Moving average crossover",
                    "parameters": {
                        "fast_period": {"type": "int", "default": 10},
                        "slow_period": {"type": "int", "default": 30}
                    }
                }
            ]
        }

    @app.get("/methods")
    async def list_optimization_methods():
        """List available optimization methods."""
        return {
            "methods": [
                {"name": "max_sharpe", "description": "Maximum Sharpe ratio"},
                {"name": "min_volatility", "description": "Minimum volatility"},
                {"name": "risk_parity", "description": "Risk parity (HRP)"},
                {"name": "equal_weight", "description": "Equal weight allocation"}
            ]
        }


else:
    # Stub when FastAPI not available
    def main():
        print("FastAPI is not installed.")
        print("Install with: pip install fastapi uvicorn")
        print("\nAlternatively, use the CLI: python cli.py --help")


if __name__ == "__main__":
    if FASTAPI_AVAILABLE:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        main()
