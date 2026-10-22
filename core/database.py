# -*- coding: utf-8 -*-
"""
Database module for quantitative trading tool.

This module provides:
- DatabaseManager: Connection management and session handling
- ORM Models: SQLAlchemy models for all database tables

Usage:
    from core.database import DatabaseManager, Security, Price

    db = DatabaseManager()
    db.create_tables()

    with db.get_session() as session:
        securities = session.query(Security).all()
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any, Generator
from contextlib import contextmanager
import os

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    BigInteger,
    String,
    Numeric,
    Date,
    DateTime,
    ForeignKey,
    Text,
    Boolean,
    UniqueConstraint,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.pool import QueuePool
import uuid

Base = declarative_base()


class DatabaseManager:
    """
    PostgreSQL connection manager.

    Handles database connections, session management, and table creation.

    Attributes:
        connection_string: PostgreSQL connection URL
        engine: SQLAlchemy engine instance
        session_factory: Session factory for creating database sessions
    """

    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize database manager.

        Args:
            connection_string: PostgreSQL connection URL.
                If not provided, reads from DATABASE_URL environment variable.
        """
        self.connection_string = connection_string or os.environ.get(
            'DATABASE_URL',
            'postgresql://quant_user:quant_password@localhost:5432/quant_trading'
        )
        # Handle Heroku-style postgres:// URLs
        if self.connection_string.startswith('postgres://'):
            self.connection_string = self.connection_string.replace(
                'postgres://', 'postgresql://', 1
            )

        self._engine = None
        self._session_factory = None

    @property
    def engine(self):
        """Lazy initialization of database engine."""
        if self._engine is None:
            self._engine = create_engine(
                self.connection_string,
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                echo=False,
            )
        return self._engine

    @property
    def session_factory(self):
        """Lazy initialization of session factory."""
        if self._session_factory is None:
            self._session_factory = sessionmaker(bind=self.engine)
        return self._session_factory

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Get a database session with automatic cleanup.

        Usage:
            with db.get_session() as session:
                securities = session.query(Security).all()

        Yields:
            Session: SQLAlchemy session object
        """
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_tables(self):
        """Create all tables defined in ORM models."""
        Base.metadata.create_all(self.engine)

    def drop_tables(self):
        """
        Drop all tables.

        WARNING: This will delete all data. Use with caution.
        """
        Base.metadata.drop_all(self.engine)

    def test_connection(self) -> bool:
        """
        Test database connection.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            with self.engine.connect() as conn:
                conn.execute('SELECT 1')
            return True
        except Exception:
            # DB is optional - silently return False if not available
            return False


# =============================================================================
# ORM Models
# =============================================================================

class Exchange(Base):
    """
    Exchange reference data.

    Stores information about stock exchanges (TWSE, NYSE, NASDAQ, etc.)
    """
    __tablename__ = 'exchanges'

    id = Column(Integer, primary_key=True)
    code = Column(String(10), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    name_zh = Column(String(100))
    timezone = Column(String(50), default='UTC')
    currency = Column(String(3), nullable=False)
    trading_hours = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    securities = relationship('Security', back_populates='exchange')

    def __repr__(self):
        return f"<Exchange(code='{self.code}', name='{self.name}')>"


class Security(Base):
    """
    Securities master data.

    Stores stock information including symbol, name, sector, etc.
    """
    __tablename__ = 'securities'

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)
    exchange_id = Column(Integer, ForeignKey('exchanges.id'))
    name = Column(String(200))
    name_zh = Column(String(200))
    sector = Column(String(100))
    industry = Column(String(100))
    asset_type = Column(String(20), default='stock')
    market_cap = Column(Numeric(20, 2))
    is_active = Column(Boolean, default=True)
    metadata_ = Column('metadata', JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('symbol', 'exchange_id', name='uq_security_symbol_exchange'),
        Index('idx_securities_symbol', 'symbol'),
        Index('idx_securities_asset_type', 'asset_type'),
    )

    # Relationships
    exchange = relationship('Exchange', back_populates='securities')
    prices = relationship('Price', back_populates='security', cascade='all, delete-orphan')
    trades = relationship('Trade', back_populates='security')
    positions = relationship('Position', back_populates='security')

    def __repr__(self):
        return f"<Security(symbol='{self.symbol}', name='{self.name}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'name': self.name,
            'name_zh': self.name_zh,
            'sector': self.sector,
            'industry': self.industry,
            'asset_type': self.asset_type,
            'exchange_code': self.exchange.code if self.exchange else None,
        }


class Price(Base):
    """
    Historical OHLCV price data.

    Stores daily price data for securities.
    Note: In PostgreSQL, this table is partitioned by date.
    """
    __tablename__ = 'prices'

    id = Column(BigInteger, primary_key=True)
    security_id = Column(Integer, ForeignKey('securities.id'), nullable=False)
    date = Column(Date, nullable=False, primary_key=True)
    timeframe = Column(String(10), default='1D')
    open = Column(Numeric(18, 6))
    high = Column(Numeric(18, 6))
    low = Column(Numeric(18, 6))
    close = Column(Numeric(18, 6))
    adj_close = Column(Numeric(18, 6))
    volume = Column(BigInteger)
    turnover = Column(Numeric(20, 2))
    data_source = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_prices_security_date', 'security_id', 'date'),
        Index('idx_prices_date', 'date'),
    )

    # Relationships
    security = relationship('Security', back_populates='prices')

    def __repr__(self):
        return f"<Price(security_id={self.security_id}, date={self.date}, close={self.close})>"


class Trade(Base):
    """
    Trade execution records.

    Stores both actual and backtest trade records.
    """
    __tablename__ = 'trades'

    id = Column(Integer, primary_key=True)
    security_id = Column(Integer, ForeignKey('securities.id'), nullable=False)
    strategy_name = Column(String(100))
    trade_type = Column(String(10), nullable=False)
    quantity = Column(Numeric(18, 6), nullable=False)
    order_price = Column(Numeric(18, 6))
    fill_price = Column(Numeric(18, 6))
    commission = Column(Numeric(18, 6), default=0)
    tax = Column(Numeric(18, 6), default=0)
    slippage = Column(Numeric(18, 6), default=0)
    order_time = Column(DateTime)
    fill_time = Column(DateTime)
    status = Column(String(20), default='FILLED')
    notes = Column(Text)
    backtest_id = Column(Integer, ForeignKey('backtest_runs.id'), nullable=True)
    is_paper_trade = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "trade_type IN ('BUY', 'SELL', 'SHORT', 'COVER')",
            name='ck_trade_type'
        ),
        CheckConstraint(
            "status IN ('PENDING', 'PARTIAL', 'FILLED', 'CANCELLED', 'REJECTED')",
            name='ck_trade_status'
        ),
        Index('idx_trades_security', 'security_id'),
        Index('idx_trades_strategy', 'strategy_name'),
        Index('idx_trades_backtest', 'backtest_id'),
        Index('idx_trades_fill_time', 'fill_time'),
    )

    # Relationships
    security = relationship('Security', back_populates='trades')
    backtest = relationship('BacktestRun', back_populates='trades')

    def __repr__(self):
        return f"<Trade(security_id={self.security_id}, type={self.trade_type}, qty={self.quantity})>"

    @property
    def total_cost(self) -> Decimal:
        """Calculate total cost including commission and slippage."""
        base_cost = self.fill_price * self.quantity
        return base_cost + (self.commission or 0) + (self.slippage or 0) + (self.tax or 0)


class Position(Base):
    """
    Current portfolio positions.

    Tracks current holdings and their market values.
    """
    __tablename__ = 'positions'

    id = Column(Integer, primary_key=True)
    security_id = Column(Integer, ForeignKey('securities.id'), nullable=False, unique=True)
    quantity = Column(Numeric(18, 6), nullable=False)
    avg_cost = Column(Numeric(18, 6), nullable=False)
    market_price = Column(Numeric(18, 6))
    market_value = Column(Numeric(18, 6))
    unrealized_pnl = Column(Numeric(18, 6))
    unrealized_pnl_pct = Column(Numeric(10, 6))
    realized_pnl = Column(Numeric(18, 6), default=0)
    opened_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    security = relationship('Security', back_populates='positions')

    def __repr__(self):
        return f"<Position(security_id={self.security_id}, qty={self.quantity})>"

    def update_market_value(self, current_price: Decimal):
        """Update market value and unrealized P&L."""
        self.market_price = current_price
        self.market_value = self.quantity * current_price
        self.unrealized_pnl = self.market_value - (self.quantity * self.avg_cost)
        if self.avg_cost > 0:
            self.unrealized_pnl_pct = (current_price - self.avg_cost) / self.avg_cost


class BacktestRun(Base):
    """
    Backtest execution results.

    Stores parameters and performance metrics for each backtest run.
    """
    __tablename__ = 'backtest_runs'

    id = Column(Integer, primary_key=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True)
    strategy_name = Column(String(100), nullable=False)
    strategy_class = Column(String(100))
    parameters = Column(JSON)
    symbols = Column(JSON)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    # Capital
    initial_capital = Column(Numeric(18, 2))
    final_value = Column(Numeric(18, 2))

    # Performance metrics
    total_return = Column(Numeric(10, 6))
    cagr = Column(Numeric(10, 6))
    sharpe_ratio = Column(Numeric(10, 6))
    sortino_ratio = Column(Numeric(10, 6))
    calmar_ratio = Column(Numeric(10, 6))
    max_drawdown = Column(Numeric(10, 6))
    avg_drawdown = Column(Numeric(10, 6))

    # Trade statistics
    total_trades = Column(Integer)
    winning_trades = Column(Integer)
    losing_trades = Column(Integer)
    win_rate = Column(Numeric(10, 6))
    profit_factor = Column(Numeric(10, 6))
    avg_trade_return = Column(Numeric(10, 6))
    avg_win = Column(Numeric(10, 6))
    avg_loss = Column(Numeric(10, 6))
    max_consecutive_wins = Column(Integer)
    max_consecutive_losses = Column(Integer)

    # Risk metrics
    volatility = Column(Numeric(10, 6))
    var_95 = Column(Numeric(10, 6))
    cvar_95 = Column(Numeric(10, 6))

    # Metadata
    execution_time_ms = Column(Integer)
    notes = Column(Text)
    tags = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_backtest_strategy', 'strategy_name'),
        Index('idx_backtest_created', 'created_at'),
        Index('idx_backtest_sharpe', 'sharpe_ratio'),
    )

    # Relationships
    trades = relationship('Trade', back_populates='backtest')
    equity_curve = relationship(
        'EquityCurve',
        back_populates='backtest',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f"<BacktestRun(strategy='{self.strategy_name}', sharpe={self.sharpe_ratio})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'uuid': str(self.uuid),
            'strategy_name': self.strategy_name,
            'parameters': self.parameters,
            'symbols': self.symbols,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'initial_capital': float(self.initial_capital) if self.initial_capital else None,
            'final_value': float(self.final_value) if self.final_value else None,
            'total_return': float(self.total_return) if self.total_return else None,
            'sharpe_ratio': float(self.sharpe_ratio) if self.sharpe_ratio else None,
            'max_drawdown': float(self.max_drawdown) if self.max_drawdown else None,
            'win_rate': float(self.win_rate) if self.win_rate else None,
            'total_trades': self.total_trades,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class EquityCurve(Base):
    """
    Backtest equity curves.

    Stores daily equity values for each backtest.
    """
    __tablename__ = 'equity_curves'

    id = Column(Integer, primary_key=True)
    backtest_id = Column(
        Integer,
        ForeignKey('backtest_runs.id', ondelete='CASCADE'),
        nullable=False
    )
    date = Column(Date, nullable=False)
    equity = Column(Numeric(18, 6))
    cash = Column(Numeric(18, 6))
    drawdown = Column(Numeric(10, 6))
    drawdown_pct = Column(Numeric(10, 6))
    daily_return = Column(Numeric(10, 6))
    cumulative_return = Column(Numeric(10, 6))

    __table_args__ = (
        UniqueConstraint('backtest_id', 'date', name='uq_equity_backtest_date'),
        Index('idx_equity_backtest_date', 'backtest_id', 'date'),
    )

    # Relationships
    backtest = relationship('BacktestRun', back_populates='equity_curve')

    def __repr__(self):
        return f"<EquityCurve(backtest_id={self.backtest_id}, date={self.date}, equity={self.equity})>"


class OptimizationResult(Base):
    """
    Portfolio optimization results.

    Stores weights and performance metrics from optimization runs.
    """
    __tablename__ = 'optimization_results'

    id = Column(Integer, primary_key=True)
    method = Column(String(50), nullable=False)
    symbols = Column(JSON, nullable=False)
    weights = Column(JSON, nullable=False)

    # Expected performance
    expected_return = Column(Numeric(10, 6))
    expected_volatility = Column(Numeric(10, 6))
    sharpe_ratio = Column(Numeric(10, 6))

    # Optimization parameters
    constraints = Column(JSON)
    risk_free_rate = Column(Numeric(10, 6))

    # Black-Litterman specific
    views = Column(JSON)
    market_caps = Column(JSON)

    # Discrete allocation
    total_investment = Column(Numeric(18, 2))
    discrete_allocation = Column(JSON)
    leftover_cash = Column(Numeric(18, 2))

    created_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text)

    __table_args__ = (
        Index('idx_optimization_method', 'method'),
        Index('idx_optimization_created', 'created_at'),
    )

    def __repr__(self):
        return f"<OptimizationResult(method='{self.method}', sharpe={self.sharpe_ratio})>"


class Watchlist(Base):
    """
    User watchlists.

    Stores lists of securities for monitoring.
    """
    __tablename__ = 'watchlists'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    symbols = Column(JSON)
    is_default = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Watchlist(name='{self.name}')>"


class DataSyncStatus(Base):
    """
    Data synchronization status tracking.

    Tracks when data was last synced for each security.
    """
    __tablename__ = 'data_sync_status'

    id = Column(Integer, primary_key=True)
    security_id = Column(Integer, ForeignKey('securities.id'))
    data_type = Column(String(50), nullable=False)
    last_sync_date = Column(Date)
    last_sync_time = Column(DateTime)
    status = Column(String(20), default='SUCCESS')
    error_message = Column(Text)
    records_synced = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint('security_id', 'data_type', name='uq_sync_security_type'),
    )

    def __repr__(self):
        return f"<DataSyncStatus(security_id={self.security_id}, type='{self.data_type}')>"


# =============================================================================
# Convenience Functions
# =============================================================================

def get_or_create_security(
    session: Session,
    symbol: str,
    exchange_code: str,
    **kwargs
) -> Security:
    """
    Get existing security or create new one.

    Args:
        session: Database session
        symbol: Stock symbol
        exchange_code: Exchange code (TWSE, NYSE, etc.)
        **kwargs: Additional security attributes

    Returns:
        Security instance
    """
    # Get exchange
    exchange = session.query(Exchange).filter_by(code=exchange_code).first()
    if not exchange:
        raise ValueError(f"Exchange '{exchange_code}' not found")

    # Try to find existing security
    security = session.query(Security).filter_by(
        symbol=symbol,
        exchange_id=exchange.id
    ).first()

    if security:
        # Update attributes if provided
        for key, value in kwargs.items():
            if hasattr(security, key) and value is not None:
                setattr(security, key, value)
    else:
        # Create new security
        security = Security(
            symbol=symbol,
            exchange_id=exchange.id,
            **kwargs
        )
        session.add(security)

    return security
