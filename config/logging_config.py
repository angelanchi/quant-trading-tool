# -*- coding: utf-8 -*-
"""
Logging configuration for quantitative trading tool.

Provides centralized logging setup with file and console handlers.
"""

import logging
import logging.handlers
import os
from pathlib import Path
from datetime import datetime


def setup_logging(
    log_level: str = "INFO",
    log_dir: str = "logs",
    log_to_file: bool = True,
    log_to_console: bool = True
) -> logging.Logger:
    """
    Setup application logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files
        log_to_file: Enable file logging
        log_to_console: Enable console logging

    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("quant_trading")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear existing handlers
    logger.handlers = []

    # Log format
    detailed_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    simple_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S"
    )

    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_format)
        logger.addHandler(console_handler)

    # File handler
    if log_to_file:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        # Daily rotating file handler
        log_file = log_path / f"quant_trading_{datetime.now().strftime('%Y%m%d')}.log"

        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_format)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = None) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (will be prefixed with 'quant_trading.')

    Returns:
        Logger instance
    """
    if name:
        return logging.getLogger(f"quant_trading.{name}")
    return logging.getLogger("quant_trading")


# Module-specific loggers
class LoggerFactory:
    """Factory for creating module-specific loggers."""

    @staticmethod
    def get_data_logger() -> logging.Logger:
        """Logger for data fetching operations."""
        return get_logger("data")

    @staticmethod
    def get_backtest_logger() -> logging.Logger:
        """Logger for backtesting operations."""
        return get_logger("backtest")

    @staticmethod
    def get_optimizer_logger() -> logging.Logger:
        """Logger for portfolio optimization."""
        return get_logger("optimizer")

    @staticmethod
    def get_risk_logger() -> logging.Logger:
        """Logger for risk calculations."""
        return get_logger("risk")

    @staticmethod
    def get_strategy_logger() -> logging.Logger:
        """Logger for trading strategies."""
        return get_logger("strategy")

    @staticmethod
    def get_db_logger() -> logging.Logger:
        """Logger for database operations."""
        return get_logger("database")


# Initialize default logging on import
_default_logger = None


def init_default_logging():
    """Initialize default logging configuration."""
    global _default_logger
    if _default_logger is None:
        log_level = os.getenv("LOG_LEVEL", "INFO")
        debug_mode = os.getenv("DEBUG", "false").lower() == "true"

        if debug_mode:
            log_level = "DEBUG"

        _default_logger = setup_logging(
            log_level=log_level,
            log_to_file=not debug_mode  # Don't log to file in debug mode
        )

    return _default_logger
