# -*- coding: utf-8 -*-
"""
Data fetcher module for quantitative trading tool.

This module provides unified data fetching interfaces for:
- Taiwan stocks (via FinMind API)
- US stocks (via Finnhub + yfinance)

Classes:
    BaseDataFetcher: Abstract base class for data fetchers
    TaiwanStockFetcher: Taiwan stock data fetcher using FinMind
    USStockFetcher: US stock data fetcher using Finnhub and yfinance
    DataManager: Unified data manager with caching

Usage:
    from core.data_fetcher import DataManager

    manager = DataManager()
    df = manager.fetch_prices('2330', start_date, end_date)  # Taiwan
    df = manager.fetch_prices('AAPL', start_date, end_date)  # US
"""

from abc import ABC, abstractmethod
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Union
import time
import logging

import pandas as pd
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Simple rate limiter to prevent API throttling.

    Attributes:
        calls_per_minute: Maximum number of calls allowed per minute
        calls: List of timestamps of recent calls
    """

    def __init__(self, calls_per_minute: int = 60):
        """
        Initialize rate limiter.

        Args:
            calls_per_minute: Maximum calls allowed per minute
        """
        self.calls_per_minute = calls_per_minute
        self.calls: List[float] = []

    def wait_if_needed(self):
        """Wait if rate limit would be exceeded."""
        now = time.time()
        # Remove calls older than 1 minute
        self.calls = [t for t in self.calls if now - t < 60]

        if len(self.calls) >= self.calls_per_minute:
            # Wait until oldest call is more than 1 minute ago
            sleep_time = 60 - (now - self.calls[0]) + 0.1
            if sleep_time > 0:
                logger.info(f"Rate limit reached. Waiting {sleep_time:.1f} seconds...")
                time.sleep(sleep_time)

        self.calls.append(time.time())


class BaseDataFetcher(ABC):
    """
    Abstract base class for data fetchers.

    All data fetchers must implement these methods to ensure
    a consistent interface across different data sources.
    """

    @abstractmethod
    def fetch_ohlcv(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        timeframe: str = '1D'
    ) -> pd.DataFrame:
        """
        Fetch OHLCV (Open, High, Low, Close, Volume) data.

        Args:
            symbol: Stock symbol
            start_date: Start date for data
            end_date: End date for data
            timeframe: Data timeframe ('1D', '1H', etc.)

        Returns:
            DataFrame with columns: date, open, high, low, close, volume
        """
        pass

    @abstractmethod
    def fetch_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch real-time quote for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Dictionary with quote data (price, change, volume, etc.)
        """
        pass

    @abstractmethod
    def search_symbol(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for symbols matching a query.

        Args:
            query: Search query string

        Returns:
            List of matching symbols with metadata
        """
        pass

    def _normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize DataFrame to standard column names.

        Standard columns: date, open, high, low, close, adj_close, volume

        Args:
            df: Input DataFrame

        Returns:
            Normalized DataFrame
        """
        if df.empty:
            return df

        # Common column mappings
        column_map = {
            # Date columns
            'Date': 'date',
            'DATE': 'date',
            'trading_date': 'date',
            'trade_date': 'date',

            # OHLC columns
            'Open': 'open',
            'OPEN': 'open',
            'open_price': 'open',

            'High': 'high',
            'HIGH': 'high',
            'max': 'high',
            'high_price': 'high',

            'Low': 'low',
            'LOW': 'low',
            'min': 'low',
            'low_price': 'low',

            'Close': 'close',
            'CLOSE': 'close',
            'close_price': 'close',

            'Adj Close': 'adj_close',
            'Adj_Close': 'adj_close',
            'adjusted_close': 'adj_close',

            # Volume columns
            'Volume': 'volume',
            'VOLUME': 'volume',
            'Trading_Volume': 'volume',
            'trading_volume': 'volume',
        }

        # Apply column mapping
        df = df.rename(columns=column_map)

        # Ensure date column is datetime
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])

        # Ensure numeric columns
        numeric_cols = ['open', 'high', 'low', 'close', 'adj_close', 'volume']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        return df


class TaiwanStockFetcher(BaseDataFetcher):
    """
    Taiwan stock data fetcher using FinMind API.

    FinMind provides comprehensive Taiwan stock market data including:
    - Daily OHLCV prices
    - Institutional investors (three major institutional investors)
    - Margin trading data
    - Financial statements

    Rate limit: 600 requests per hour (10 per minute)

    Attributes:
        api_token: FinMind API token for authenticated requests
        rate_limiter: Rate limiter to prevent throttling
    """

    def __init__(self, api_token: Optional[str] = None):
        """
        Initialize Taiwan stock fetcher.

        Args:
            api_token: FinMind API token. If provided, enables higher rate limits.
        """
        self.api_token = api_token
        self._client = None
        self.rate_limiter = RateLimiter(calls_per_minute=10)

    @property
    def client(self):
        """Lazy initialization of FinMind DataLoader."""
        if self._client is None:
            try:
                from FinMind.data import DataLoader
                self._client = DataLoader()
                if self.api_token:
                    self._client.login_by_token(api_token=self.api_token)
                    logger.info("FinMind: Authenticated with API token")
                else:
                    logger.warning("FinMind: Using without API token (limited rate)")
            except ImportError:
                logger.error("FinMind package not installed. Run: pip install FinMind")
                raise
        return self._client

    def fetch_ohlcv(
        self,
        symbol: str,
        start_date: Union[date, str],
        end_date: Union[date, str],
        timeframe: str = '1D'
    ) -> pd.DataFrame:
        """
        Fetch Taiwan stock OHLCV data.

        Args:
            symbol: Taiwan stock symbol (e.g., '2330' for TSMC)
            start_date: Start date (date object or 'YYYY-MM-DD' string)
            end_date: End date (date object or 'YYYY-MM-DD' string)
            timeframe: Timeframe (only '1D' supported for Taiwan stocks)

        Returns:
            DataFrame with OHLCV data
        """
        self.rate_limiter.wait_if_needed()

        # Normalize dates to strings
        if isinstance(start_date, (date, datetime)):
            start_date = start_date.strftime('%Y-%m-%d')
        if isinstance(end_date, (date, datetime)):
            end_date = end_date.strftime('%Y-%m-%d')

        try:
            # Remove .TW suffix if present
            symbol = symbol.replace('.TW', '').replace('.TWO', '')

            df = self.client.taiwan_stock_daily(
                stock_id=symbol,
                start_date=start_date,
                end_date=end_date
            )

            if df is None or df.empty:
                logger.warning(f"No data returned for Taiwan stock {symbol}")
                return pd.DataFrame()

            df = self._normalize_dataframe(df)

            # Add adj_close if not present (use close)
            if 'adj_close' not in df.columns:
                df['adj_close'] = df['close']

            # Add metadata
            df['symbol'] = symbol
            df['data_source'] = 'finmind'

            return df[['date', 'open', 'high', 'low', 'close', 'adj_close', 'volume', 'symbol', 'data_source']]

        except Exception as e:
            logger.error(f"Error fetching Taiwan stock {symbol}: {e}")
            return pd.DataFrame()

    def fetch_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch latest quote for Taiwan stock.

        Note: FinMind doesn't provide real-time quotes.
        Returns the most recent daily data as a quote.

        Args:
            symbol: Taiwan stock symbol

        Returns:
            Quote dictionary
        """
        end = date.today()
        start = end - timedelta(days=7)
        df = self.fetch_ohlcv(symbol, start, end)

        if df.empty:
            return {}

        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last

        return {
            'symbol': symbol,
            'price': float(last['close']),
            'open': float(last['open']),
            'high': float(last['high']),
            'low': float(last['low']),
            'volume': int(last['volume']),
            'change': float(last['close'] - prev['close']),
            'change_percent': float((last['close'] - prev['close']) / prev['close'] * 100),
            'timestamp': last['date'],
            'market': 'Taiwan',
            'currency': 'TWD',
        }

    def search_symbol(self, query: str) -> List[Dict[str, Any]]:
        """
        Search Taiwan stock symbols.

        Note: FinMind doesn't provide symbol search.
        Returns empty list. Use a pre-loaded stock list for search.

        Args:
            query: Search query

        Returns:
            Empty list (not supported)
        """
        logger.warning("Symbol search not supported for Taiwan stocks via FinMind")
        return []

    def fetch_institutional_investors(
        self,
        symbol: str,
        start_date: Union[date, str],
        end_date: Optional[Union[date, str]] = None
    ) -> pd.DataFrame:
        """
        Fetch institutional investors (three major) data.

        Returns buy/sell data for:
        - Foreign investors
        - Investment trust
        - Dealers

        Args:
            symbol: Taiwan stock symbol
            start_date: Start date (date object or 'YYYY-MM-DD' string)
            end_date: End date (defaults to today)

        Returns:
            DataFrame with institutional investor data
        """
        self.rate_limiter.wait_if_needed()

        if end_date is None:
            end_date = date.today()

        # Normalize dates to strings
        if isinstance(start_date, (date, datetime)):
            start_date = start_date.strftime('%Y-%m-%d')
        if isinstance(end_date, (date, datetime)):
            end_date = end_date.strftime('%Y-%m-%d')

        try:
            symbol = symbol.replace('.TW', '').replace('.TWO', '')

            df = self.client.taiwan_stock_institutional_investors(
                stock_id=symbol,
                start_date=start_date,
                end_date=end_date
            )

            if df is None or df.empty:
                return pd.DataFrame()

            df['date'] = pd.to_datetime(df['date'])
            return df

        except Exception as e:
            logger.error(f"Error fetching institutional data for {symbol}: {e}")
            return pd.DataFrame()

    def fetch_margin_trading(
        self,
        symbol: str,
        start_date: Union[date, str],
        end_date: Optional[Union[date, str]] = None
    ) -> pd.DataFrame:
        """
        Fetch margin trading data (margin buy/sell, short sell).

        Args:
            symbol: Taiwan stock symbol
            start_date: Start date (date object or 'YYYY-MM-DD' string)
            end_date: End date

        Returns:
            DataFrame with margin trading data
        """
        self.rate_limiter.wait_if_needed()

        if end_date is None:
            end_date = date.today()

        # Normalize dates to strings
        if isinstance(start_date, (date, datetime)):
            start_date = start_date.strftime('%Y-%m-%d')
        if isinstance(end_date, (date, datetime)):
            end_date = end_date.strftime('%Y-%m-%d')

        try:
            symbol = symbol.replace('.TW', '').replace('.TWO', '')

            df = self.client.taiwan_stock_margin_purchase_short_sale(
                stock_id=symbol,
                start_date=start_date,
                end_date=end_date
            )

            if df is None or df.empty:
                return pd.DataFrame()

            df['date'] = pd.to_datetime(df['date'])
            return df

        except Exception as e:
            logger.error(f"Error fetching margin data for {symbol}: {e}")
            return pd.DataFrame()


class USStockFetcher(BaseDataFetcher):
    """
    US stock data fetcher using Finnhub (real-time) and yfinance (historical).

    Finnhub: Real-time quotes and company info (60 requests/minute)
    yfinance: Historical OHLCV data (unofficial, use conservatively)

    Attributes:
        finnhub_api_key: Finnhub API key for real-time data
        rate_limiter: Rate limiter for Finnhub API
    """

    def __init__(self, finnhub_api_key: Optional[str] = None):
        """
        Initialize US stock fetcher.

        Args:
            finnhub_api_key: Finnhub API key for real-time quotes
        """
        self.finnhub_api_key = finnhub_api_key
        self._finnhub_client = None
        self.rate_limiter = RateLimiter(calls_per_minute=60)
        self.yfinance_limiter = RateLimiter(calls_per_minute=2)

    @property
    def finnhub_client(self):
        """Lazy initialization of Finnhub client."""
        if self._finnhub_client is None and self.finnhub_api_key:
            try:
                import finnhub
                self._finnhub_client = finnhub.Client(api_key=self.finnhub_api_key)
                logger.info("Finnhub: Client initialized")
            except ImportError:
                logger.error("Finnhub package not installed. Run: pip install finnhub-python")
        return self._finnhub_client

    def fetch_ohlcv(
        self,
        symbol: str,
        start_date: Union[date, str],
        end_date: Union[date, str],
        timeframe: str = '1D'
    ) -> pd.DataFrame:
        """
        Fetch US stock OHLCV data using yfinance.

        Args:
            symbol: US stock symbol (e.g., 'AAPL')
            start_date: Start date (date object or 'YYYY-MM-DD' string)
            end_date: End date (date object or 'YYYY-MM-DD' string)
            timeframe: Timeframe ('1D', '1H', '5M', etc.)

        Returns:
            DataFrame with OHLCV data
        """
        self.yfinance_limiter.wait_if_needed()

        # Normalize dates
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

        try:
            import yfinance as yf

            # Map timeframe to yfinance interval
            interval_map = {
                '1D': '1d',
                '1H': '1h',
                '5M': '5m',
                '15M': '15m',
                '30M': '30m',
                '1W': '1wk',
                '1M': '1mo',
            }
            interval = interval_map.get(timeframe, '1d')

            ticker = yf.Ticker(symbol)
            df = ticker.history(
                start=start_date.strftime('%Y-%m-%d'),
                end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                interval=interval
            )

            if df.empty:
                logger.warning(f"No data returned for US stock {symbol}")
                return pd.DataFrame()

            df = df.reset_index()
            df = self._normalize_dataframe(df)

            # Rename 'Date' index to 'date' if needed
            if 'Date' in df.columns:
                df = df.rename(columns={'Date': 'date'})

            # Handle adj_close
            if 'adj_close' not in df.columns and 'close' in df.columns:
                df['adj_close'] = df['close']

            # Add metadata
            df['symbol'] = symbol
            df['data_source'] = 'yfinance'

            # Select and order columns
            cols = ['date', 'open', 'high', 'low', 'close', 'adj_close', 'volume', 'symbol', 'data_source']
            available_cols = [c for c in cols if c in df.columns]
            df = df[available_cols]

            return df

        except Exception as e:
            logger.error(f"Error fetching US stock {symbol}: {e}")
            return pd.DataFrame()

    def fetch_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch real-time quote for US stock.

        Uses Finnhub if API key is provided, otherwise falls back to yfinance.

        Args:
            symbol: US stock symbol

        Returns:
            Quote dictionary
        """
        if self.finnhub_client:
            return self._fetch_quote_finnhub(symbol)
        return self._fetch_quote_yfinance(symbol)

    def _fetch_quote_finnhub(self, symbol: str) -> Dict[str, Any]:
        """Fetch quote using Finnhub API."""
        self.rate_limiter.wait_if_needed()

        try:
            quote = self.finnhub_client.quote(symbol)

            if not quote or quote.get('c') is None:
                return {}

            return {
                'symbol': symbol,
                'price': quote.get('c'),  # Current price
                'open': quote.get('o'),
                'high': quote.get('h'),
                'low': quote.get('l'),
                'prev_close': quote.get('pc'),
                'change': quote.get('d'),
                'change_percent': quote.get('dp'),
                'timestamp': datetime.fromtimestamp(quote.get('t', 0)),
                'market': 'US',
                'currency': 'USD',
            }

        except Exception as e:
            logger.error(f"Finnhub quote error for {symbol}: {e}")
            return self._fetch_quote_yfinance(symbol)

    def _fetch_quote_yfinance(self, symbol: str) -> Dict[str, Any]:
        """Fetch quote using yfinance (fallback)."""
        self.yfinance_limiter.wait_if_needed()

        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            info = ticker.info

            return {
                'symbol': symbol,
                'price': info.get('regularMarketPrice') or info.get('currentPrice'),
                'open': info.get('regularMarketOpen'),
                'high': info.get('regularMarketDayHigh'),
                'low': info.get('regularMarketDayLow'),
                'prev_close': info.get('regularMarketPreviousClose'),
                'change': info.get('regularMarketChange'),
                'change_percent': info.get('regularMarketChangePercent'),
                'volume': info.get('regularMarketVolume'),
                'market_cap': info.get('marketCap'),
                'timestamp': datetime.now(),
                'market': 'US',
                'currency': 'USD',
            }

        except Exception as e:
            logger.error(f"yfinance quote error for {symbol}: {e}")
            return {}

    def search_symbol(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for US stock symbols.

        Uses Finnhub symbol lookup if available.

        Args:
            query: Search query

        Returns:
            List of matching symbols
        """
        if self.finnhub_client:
            self.rate_limiter.wait_if_needed()
            try:
                results = self.finnhub_client.symbol_lookup(query)
                return results.get('result', [])
            except Exception as e:
                logger.error(f"Symbol search error: {e}")
        return []

    def fetch_company_profile(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch company profile information.

        Args:
            symbol: US stock symbol

        Returns:
            Company profile dictionary
        """
        if self.finnhub_client:
            self.rate_limiter.wait_if_needed()
            try:
                profile = self.finnhub_client.company_profile2(symbol=symbol)
                return profile
            except Exception as e:
                logger.error(f"Company profile error for {symbol}: {e}")

        # Fallback to yfinance
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            info = ticker.info
            return {
                'name': info.get('longName'),
                'industry': info.get('industry'),
                'sector': info.get('sector'),
                'country': info.get('country'),
                'market_cap': info.get('marketCap'),
                'employees': info.get('fullTimeEmployees'),
                'website': info.get('website'),
            }
        except Exception as e:
            logger.error(f"yfinance profile error for {symbol}: {e}")
            return {}


class DataManager:
    """
    Unified data manager with automatic routing and caching.

    Automatically routes requests to the appropriate data source based on
    the stock symbol format and handles database caching.

    Attributes:
        taiwan_fetcher: TaiwanStockFetcher instance
        us_fetcher: USStockFetcher instance
        db_manager: DatabaseManager for caching (optional)

    Usage:
        manager = DataManager()

        # Automatically routes based on symbol
        tsmc = manager.fetch_prices('2330', start, end)  # -> Taiwan
        apple = manager.fetch_prices('AAPL', start, end)  # -> US
    """

    def __init__(
        self,
        finmind_token: Optional[str] = None,
        finnhub_api_key: Optional[str] = None,
        db_manager=None
    ):
        """
        Initialize data manager.

        Args:
            finmind_token: FinMind API token for Taiwan stocks
            finnhub_api_key: Finnhub API key for US stocks
            db_manager: DatabaseManager instance for caching
        """
        # Try to load from environment if not provided
        import os

        if finmind_token is None:
            finmind_token = os.environ.get('FINMIND_API_TOKEN')

        if finnhub_api_key is None:
            finnhub_api_key = os.environ.get('FINNHUB_API_KEY')

        self.taiwan_fetcher = TaiwanStockFetcher(api_token=finmind_token)
        self.us_fetcher = USStockFetcher(finnhub_api_key=finnhub_api_key)
        self.db_manager = db_manager

    def get_fetcher(self, symbol: str) -> BaseDataFetcher:
        """
        Get appropriate fetcher based on symbol format.

        Taiwan symbols:
        - 4-digit numbers: '2330'
        - With .TW suffix: '2330.TW'
        - With .TWO suffix: '6547.TWO' (OTC)

        US symbols: Everything else

        Args:
            symbol: Stock symbol

        Returns:
            Appropriate data fetcher
        """
        # Taiwan stock patterns
        clean_symbol = symbol.upper().strip()

        # Check for Taiwan suffixes
        if clean_symbol.endswith('.TW') or clean_symbol.endswith('.TWO'):
            return self.taiwan_fetcher

        # Check for 4-digit numeric symbols (Taiwan)
        base_symbol = clean_symbol.replace('.TW', '').replace('.TWO', '')
        if base_symbol.isdigit() and len(base_symbol) == 4:
            return self.taiwan_fetcher

        # Check for 5-digit numeric symbols (Taiwan ETF, warrant)
        if base_symbol.isdigit() and len(base_symbol) == 5:
            return self.taiwan_fetcher

        # Default to US
        return self.us_fetcher

    def is_taiwan_stock(self, symbol: str) -> bool:
        """Check if symbol is a Taiwan stock."""
        return self.get_fetcher(symbol) == self.taiwan_fetcher

    def fetch_prices(
        self,
        symbol: str,
        start_date: Union[date, str],
        end_date: Union[date, str],
        use_cache: bool = True,
        timeframe: str = '1D'
    ) -> pd.DataFrame:
        """
        Fetch price data for a symbol.

        Automatically routes to the correct data source and uses
        database caching if available.

        Args:
            symbol: Stock symbol
            start_date: Start date (date object or 'YYYY-MM-DD' string)
            end_date: End date
            use_cache: Whether to use database cache
            timeframe: Data timeframe

        Returns:
            DataFrame with OHLCV data
        """
        # Parse dates if strings
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

        # 1) Local adjusted-price cache written by scripts/fetch_market_data.py
        if use_cache and timeframe == '1D':
            local = self._get_local_csv(symbol, start_date, end_date)
            if not local.empty:
                return local

        # 2) Database cache
        if use_cache and self.db_manager:
            cached = self._get_cached_prices(symbol, start_date, end_date, timeframe)
            if not cached.empty:
                logger.info(f"Cache hit for {symbol}")
                return cached

        # Fetch from API
        fetcher = self.get_fetcher(symbol)
        df = fetcher.fetch_ohlcv(symbol, start_date, end_date, timeframe)

        # Save to cache
        if self.db_manager and not df.empty:
            self._cache_prices(symbol, df)

        return df

    @staticmethod
    def _get_local_csv(symbol: str, start_date, end_date) -> pd.DataFrame:
        """
        Read data/prices/<symbol>.csv (dividend/split adjusted, see scripts/fetch_market_data.py).

        Used only when the file covers the requested start date and is no more than
        7 days behind the requested end date; otherwise the caller falls back to the APIs.
        Returns the same columns as the API fetchers.
        """
        from pathlib import Path
        import json
        root = Path(__file__).resolve().parent.parent / 'data' / 'prices'
        f = root / f"{symbol.replace('.TWO', '').replace('.TW', '')}.csv"
        if not f.exists():
            return pd.DataFrame()
        try:
            df = pd.read_csv(f, parse_dates=['date'])
        except Exception:
            return pd.DataFrame()
        if df.empty:
            return df
        first, last = df['date'].min().date(), df['date'].max().date()
        if first > start_date + timedelta(days=7) or last < end_date - timedelta(days=7):
            return pd.DataFrame()
        df = df[(df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date)].copy()
        df['adj_close'] = df['close']
        df['symbol'] = symbol
        try:
            meta = json.loads((root / '_manifest.json').read_text(encoding='utf-8')).get(symbol, {})
            df['data_source'] = f"local:{meta.get('source', 'csv')}"
        except Exception:
            df['data_source'] = 'local:csv'
        return df[['date', 'open', 'high', 'low', 'close', 'adj_close', 'volume', 'symbol', 'data_source']].reset_index(drop=True)

    def fetch_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch real-time quote for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Quote dictionary
        """
        fetcher = self.get_fetcher(symbol)
        return fetcher.fetch_quote(symbol)

    def fetch_multiple_prices(
        self,
        symbols: List[str],
        start_date: Union[date, str],
        end_date: Union[date, str],
        timeframe: str = '1D'
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch price data for multiple symbols.

        Args:
            symbols: List of stock symbols
            start_date: Start date
            end_date: End date
            timeframe: Data timeframe

        Returns:
            Dictionary mapping symbols to DataFrames
        """
        results = {}
        for symbol in symbols:
            try:
                df = self.fetch_prices(symbol, start_date, end_date, timeframe=timeframe)
                if not df.empty:
                    results[symbol] = df
            except Exception as e:
                logger.error(f"Error fetching {symbol}: {e}")

        return results

    def get_combined_prices(
        self,
        symbols: List[str],
        start_date: Union[date, str],
        end_date: Union[date, str],
        column: str = 'close'
    ) -> pd.DataFrame:
        """
        Get combined price data for multiple symbols.

        Returns a DataFrame with dates as index and symbols as columns.
        Useful for portfolio analysis.

        Args:
            symbols: List of stock symbols
            start_date: Start date
            end_date: End date
            column: Price column to use ('close', 'adj_close', etc.)

        Returns:
            DataFrame with symbols as columns
        """
        data = self.fetch_multiple_prices(symbols, start_date, end_date)

        if not data:
            return pd.DataFrame()

        # Combine into single DataFrame
        combined = pd.DataFrame()
        for symbol, df in data.items():
            if column in df.columns:
                series = df.set_index('date')[column]
                series.name = symbol
                combined = pd.concat([combined, series], axis=1)

        combined = combined.sort_index()
        return combined

    def _get_cached_prices(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        timeframe: str
    ) -> pd.DataFrame:
        """
        Get cached prices from database.

        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date
            timeframe: Data timeframe

        Returns:
            DataFrame with cached data or empty DataFrame
        """
        if not self.db_manager:
            return pd.DataFrame()

        try:
            from .database import Security, Price

            with self.db_manager.get_session() as session:
                # Find security
                security = session.query(Security).filter_by(symbol=symbol).first()
                if not security:
                    return pd.DataFrame()

                # Query prices
                prices = session.query(Price).filter(
                    Price.security_id == security.id,
                    Price.date >= start_date,
                    Price.date <= end_date,
                    Price.timeframe == timeframe
                ).order_by(Price.date).all()

                if not prices:
                    return pd.DataFrame()

                # Convert to DataFrame
                data = [{
                    'date': p.date,
                    'open': float(p.open) if p.open else None,
                    'high': float(p.high) if p.high else None,
                    'low': float(p.low) if p.low else None,
                    'close': float(p.close) if p.close else None,
                    'adj_close': float(p.adj_close) if p.adj_close else None,
                    'volume': int(p.volume) if p.volume else None,
                    'symbol': symbol,
                    'data_source': p.data_source,
                } for p in prices]

                return pd.DataFrame(data)

        except Exception as e:
            logger.error(f"Cache read error for {symbol}: {e}")
            return pd.DataFrame()

    def _cache_prices(self, symbol: str, df: pd.DataFrame):
        """
        Cache price data to database.

        Args:
            symbol: Stock symbol
            df: DataFrame with price data
        """
        if not self.db_manager or df.empty:
            return

        try:
            from .database import Security, Price, Exchange, get_or_create_security

            with self.db_manager.get_session() as session:
                # Determine exchange
                exchange_code = 'TWSE' if self.is_taiwan_stock(symbol) else 'NYSE'

                # Get or create security
                security = get_or_create_security(
                    session,
                    symbol=symbol.replace('.TW', '').replace('.TWO', ''),
                    exchange_code=exchange_code
                )
                session.flush()

                # Insert prices (upsert logic)
                for _, row in df.iterrows():
                    # Check if price exists
                    existing = session.query(Price).filter(
                        Price.security_id == security.id,
                        Price.date == row['date'].date() if hasattr(row['date'], 'date') else row['date'],
                    ).first()

                    if existing:
                        # Update existing
                        existing.open = row.get('open')
                        existing.high = row.get('high')
                        existing.low = row.get('low')
                        existing.close = row.get('close')
                        existing.adj_close = row.get('adj_close')
                        existing.volume = row.get('volume')
                        existing.data_source = row.get('data_source', 'api')
                    else:
                        # Insert new
                        price = Price(
                            security_id=security.id,
                            date=row['date'].date() if hasattr(row['date'], 'date') else row['date'],
                            open=row.get('open'),
                            high=row.get('high'),
                            low=row.get('low'),
                            close=row.get('close'),
                            adj_close=row.get('adj_close'),
                            volume=row.get('volume'),
                            data_source=row.get('data_source', 'api'),
                        )
                        session.add(price)

                logger.info(f"Cached {len(df)} prices for {symbol}")

        except Exception as e:
            logger.error(f"Cache write error for {symbol}: {e}")


# =============================================================================
# Convenience Functions
# =============================================================================

def get_data_manager(
    finmind_token: Optional[str] = None,
    finnhub_api_key: Optional[str] = None,
    use_database: bool = False
) -> DataManager:
    """
    Create a DataManager instance.

    Convenience function to create a DataManager with optional database support.

    Args:
        finmind_token: FinMind API token
        finnhub_api_key: Finnhub API key
        use_database: Whether to enable database caching

    Returns:
        DataManager instance
    """
    db_manager = None

    if use_database:
        try:
            from .database import DatabaseManager
            db_manager = DatabaseManager()
            if not db_manager.test_connection():
                logger.warning("Database connection failed. Caching disabled.")
                db_manager = None
        except Exception as e:
            logger.warning(f"Database initialization failed: {e}")

    return DataManager(
        finmind_token=finmind_token,
        finnhub_api_key=finnhub_api_key,
        db_manager=db_manager
    )
