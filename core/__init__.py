# -*- coding: utf-8 -*-
"""
Core module for quantitative trading tool.

This module contains the core functionality:
- data_fetcher: Data retrieval from various sources
- database: PostgreSQL ORM models and database operations
- backtester: VectorBT backtesting engine wrapper
- optimizer: Portfolio optimization using PyPortfolioOpt
- risk: Risk metrics calculation
- report: Report generation (HTML/PDF)
- alerts: Price and signal alert system
"""

# Ensure .env is loaded before any module reads os.environ
import os as _os
from pathlib import Path as _Path
try:
    from dotenv import load_dotenv as _load_dotenv
    _env_file = _Path(__file__).parent.parent / '.env'
    if _env_file.exists():
        _load_dotenv(_env_file, override=False)
except ImportError:
    pass

try:
    # sqlalchemy is optional (requirements-optional.txt); keep core importable without it.
    from .database import DatabaseManager
except ImportError:  # pragma: no cover
    DatabaseManager = None
from .data_fetcher import (
    DataManager,
    TaiwanStockFetcher,
    USStockFetcher,
    get_data_manager,
)
from .backtester import (
    BacktestConfig,
    BacktestResult,
    BacktestEngine,
)
from .optimizer import (
    OptimizationResult,
    PortfolioOptimizer,
)
from .risk import (
    RiskMetrics,
    RiskCalculator,
    PortfolioRiskDecomposition,
)
from .report import (
    ReportGenerator,
    generate_backtest_report,
    generate_full_report,
)
from .alerts import (
    Alert,
    AlertEvent,
    AlertManager,
    AlertType,
    AlertPriority,
    console_alert_handler,
)
from .financial_reports import (
    FinancialReportManager,
    TaiwanFinancialFetcher,
    USFinancialFetcher,
)
from .news_fetcher import (
    NewsManager,
    NewsFetcher,
    MacroDataFetcher,
    EarningsCalendarFetcher,
)
from .context_engine import (
    ContextEngine,
    ContextEvent,
    StockTimeline,
    EventType,
)
from .fundamental_alerts import (
    FundamentalAlertChecker,
    FundamentalAlert,
    FundamentalAlertType,
    AlertThresholds,
    generate_scan_report,
)
from .walk_forward import (
    WalkForwardOptimizer,
    WalkForwardResult,
    WalkForwardWindow,
    RollingOptimizer,
    walk_forward_analyze,
)
from .sentiment import (
    SentimentAnalyzer,
    KeywordSentimentAnalyzer,
    FinBERTSentimentAnalyzer,
)
from .multi_factor import (
    MultiFactorModel,
    FactorWeights,
)
from .sector_analysis import (
    SectorAnalysisManager,
    SectorMap,
    SectorRotationTracker,
    SupplyChainAnalyzer,
    PeerComparison,
    SectorNewsTracker,
)

__all__ = [
    # Database
    'DatabaseManager',
    # Data Fetcher
    'DataManager',
    'TaiwanStockFetcher',
    'USStockFetcher',
    'get_data_manager',
    # Backtester
    'BacktestConfig',
    'BacktestResult',
    'BacktestEngine',
    # Optimizer
    'OptimizationResult',
    'PortfolioOptimizer',
    # Risk
    'RiskMetrics',
    'RiskCalculator',
    'PortfolioRiskDecomposition',
    # Report
    'ReportGenerator',
    'generate_backtest_report',
    'generate_full_report',
    # Alerts
    'Alert',
    'AlertEvent',
    'AlertManager',
    'AlertType',
    'AlertPriority',
    'console_alert_handler',
    # Walk-Forward
    'WalkForwardOptimizer',
    'WalkForwardResult',
    'WalkForwardWindow',
    'RollingOptimizer',
    'walk_forward_analyze',
    # Financial Reports
    'FinancialReportManager',
    'TaiwanFinancialFetcher',
    'USFinancialFetcher',
    # News & Macro
    'NewsManager',
    'NewsFetcher',
    'MacroDataFetcher',
    'EarningsCalendarFetcher',
    # Context Engine
    'ContextEngine',
    'ContextEvent',
    'StockTimeline',
    'EventType',
    # Fundamental Alerts
    'FundamentalAlertChecker',
    'FundamentalAlert',
    'FundamentalAlertType',
    'AlertThresholds',
    'generate_scan_report',
    # Sentiment Analysis
    'SentimentAnalyzer',
    'KeywordSentimentAnalyzer',
    'FinBERTSentimentAnalyzer',
    # Multi-Factor Model
    'MultiFactorModel',
    'FactorWeights',
    # Sector Analysis
    'SectorAnalysisManager',
    'SectorMap',
    'SectorRotationTracker',
    'SupplyChainAnalyzer',
    'PeerComparison',
    'SectorNewsTracker',
]
