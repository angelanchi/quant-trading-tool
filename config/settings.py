# -*- coding: utf-8 -*-
"""
Configuration management module.

This module handles application settings through environment variables
and provides a centralized configuration object.
"""

import os
from dataclasses import dataclass, field
from typing import Optional
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


# Load .env file from project root
PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE = PROJECT_ROOT / '.env'

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)


@dataclass
class DatabaseSettings:
    """Database connection settings."""

    url: str = field(default_factory=lambda: os.getenv(
        'DATABASE_URL',
        'postgresql://quant_user:quant_password@localhost:5432/quant_trading'
    ))
    pool_size: int = field(default_factory=lambda: int(os.getenv('DB_POOL_SIZE', '5')))
    max_overflow: int = field(default_factory=lambda: int(os.getenv('DB_MAX_OVERFLOW', '10')))
    pool_pre_ping: bool = True


@dataclass
class APISettings:
    """API keys and settings for data sources."""

    # FinMind API (Taiwan stocks)
    finmind_token: Optional[str] = field(
        default_factory=lambda: os.getenv('FINMIND_API_TOKEN')
    )

    # Finnhub API (US stocks real-time)
    finnhub_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv('FINNHUB_API_KEY')
    )

    # FRED API (US macro data)
    fred_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv('FRED_API_KEY')
    )

    # Rate limits (requests per minute)
    finmind_rate_limit: int = 10  # 600/hour = 10/minute
    finnhub_rate_limit: int = 60
    yfinance_rate_limit: int = 2  # Conservative limit


@dataclass
class BacktestSettings:
    """Backtesting default settings."""

    initial_capital: float = field(
        default_factory=lambda: float(os.getenv('BACKTEST_INITIAL_CAPITAL', '1000000'))
    )
    commission: float = field(
        default_factory=lambda: float(os.getenv('BACKTEST_COMMISSION', '0.001'))
    )
    slippage: float = field(
        default_factory=lambda: float(os.getenv('BACKTEST_SLIPPAGE', '0.0005'))
    )
    risk_free_rate: float = field(
        default_factory=lambda: float(os.getenv('RISK_FREE_RATE', '0.02'))
    )


@dataclass
class AppSettings:
    """Application general settings."""

    debug: bool = field(
        default_factory=lambda: os.getenv('DEBUG', 'false').lower() == 'true'
    )
    log_level: str = field(
        default_factory=lambda: os.getenv('LOG_LEVEL', 'INFO')
    )
    timezone: str = field(
        default_factory=lambda: os.getenv('TIMEZONE', 'Asia/Taipei')
    )


@dataclass
class Settings:
    """
    Main settings class that aggregates all configuration.

    Usage:
        from config import get_settings
        settings = get_settings()
        print(settings.database.url)
    """

    database: DatabaseSettings = field(default_factory=DatabaseSettings)
    api: APISettings = field(default_factory=APISettings)
    backtest: BacktestSettings = field(default_factory=BacktestSettings)
    app: AppSettings = field(default_factory=AppSettings)

    # Project paths
    project_root: Path = PROJECT_ROOT

    def validate(self) -> bool:
        """
        Validate critical settings.

        Returns:
            True if all critical settings are valid.

        Raises:
            ValueError: If validation fails.
        """
        errors = []

        # Check database URL format
        if not self.database.url.startswith(('postgresql://', 'postgres://')):
            errors.append('DATABASE_URL must be a PostgreSQL connection string')

        # Warn about missing API keys (not critical)
        if not self.api.finmind_token:
            print('Warning: FINMIND_API_TOKEN not set. Taiwan stock data may be limited.')

        if not self.api.finnhub_api_key:
            print('Warning: FINNHUB_API_KEY not set. US real-time quotes unavailable.')

        if errors:
            raise ValueError('\n'.join(errors))

        return True

    def get_database_url(self) -> str:
        """Get database URL with any necessary transformations."""
        url = self.database.url
        # Handle Heroku-style postgres:// URLs
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        return url


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    This function is cached to ensure the same settings object
    is returned throughout the application lifecycle.

    Returns:
        Settings: The application settings instance.
    """
    settings = Settings()
    settings.validate()
    return settings


# Convenience functions for common settings
def get_database_url() -> str:
    """Get the database connection URL."""
    return get_settings().get_database_url()


def get_api_key(service: str) -> Optional[str]:
    """
    Get API key for a specific service.

    Args:
        service: Service name ('finmind', 'finnhub')

    Returns:
        API key string or None if not set.
    """
    settings = get_settings()
    if service.lower() == 'finmind':
        return settings.api.finmind_token
    elif service.lower() == 'finnhub':
        return settings.api.finnhub_api_key
    elif service.lower() == 'fred':
        return settings.api.fred_api_key
    return None


def is_debug() -> bool:
    """Check if debug mode is enabled."""
    return get_settings().app.debug
