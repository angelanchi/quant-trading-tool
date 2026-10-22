# -*- coding: utf-8 -*-
"""
Backtesting engine module.

This module provides a VectorBT-based backtesting engine with support for:
- Signal-driven backtesting
- Built-in strategies (Mean Reversion, MA Crossover)
- Parameter optimization
- Performance metrics calculation

Classes:
    BacktestConfig: Configuration for backtests
    BacktestResult: Results from a backtest run
    BacktestEngine: Main backtesting engine

Usage:
    from core.backtester import BacktestEngine, BacktestConfig

    engine = BacktestEngine()
    result = engine.run_mean_reversion(prices, lookback=20, entry_zscore=-2.0)
    print(f"Sharpe Ratio: {result.sharpe_ratio}")
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional, Callable, Any, Tuple, Union
import logging

import pandas as pd
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """
    Backtest configuration parameters.

    Attributes:
        initial_capital: Starting capital for the backtest
        commission: Commission rate per trade (0.001 = 0.1%)
        slippage: Slippage rate per trade (0.0005 = 0.05%)
        size_type: How to determine position size ('percent', 'shares', 'value')
        size: Size value (depends on size_type)
        allow_shorting: Whether to allow short positions
        freq: Data frequency ('1D', '1H', etc.)
        risk_free_rate: Annual risk-free rate for Sharpe calculation
    """
    initial_capital: float = 1_000_000
    commission: float = 0.001  # 0.1%
    slippage: float = 0.0005  # 0.05%
    size_type: str = 'percent'  # 'percent', 'shares', 'value'
    size: float = 0.1  # 10% of portfolio per trade
    allow_shorting: bool = False
    freq: str = '1D'
    risk_free_rate: float = 0.02  # 2% annual


@dataclass
class BacktestResult:
    """
    Backtest results container.

    Contains all performance metrics, equity curve, and trade records
    from a backtest run.
    """
    strategy_name: str
    symbols: List[str]
    start_date: date
    end_date: date
    initial_capital: float
    final_value: float

    # Performance metrics
    total_return: float
    cagr: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    calmar_ratio: float

    # Trade statistics
    total_trades: int
    win_rate: float
    profit_factor: float
    avg_trade_return: float

    # Data
    equity_curve: pd.DataFrame
    trades: pd.DataFrame
    parameters: Dict = field(default_factory=dict)

    # Risk metrics
    volatility: float = 0.0
    var_95: float = 0.0
    cvar_95: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            'strategy_name': self.strategy_name,
            'symbols': self.symbols,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'initial_capital': self.initial_capital,
            'final_value': self.final_value,
            'total_return': self.total_return,
            'cagr': self.cagr,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'max_drawdown': self.max_drawdown,
            'calmar_ratio': self.calmar_ratio,
            'total_trades': self.total_trades,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'avg_trade_return': self.avg_trade_return,
            'volatility': self.volatility,
            'var_95': self.var_95,
            'cvar_95': self.cvar_95,
            'parameters': self.parameters,
        }

    def summary(self) -> str:
        """Generate a text summary of results."""
        return f"""
Backtest Results: {self.strategy_name}
{'='*50}
Period: {self.start_date} to {self.end_date}
Symbols: {', '.join(self.symbols)}

Performance:
  Total Return: {self.total_return*100:.2f}%
  CAGR: {self.cagr*100:.2f}%
  Sharpe Ratio: {self.sharpe_ratio:.2f}
  Sortino Ratio: {self.sortino_ratio:.2f}
  Max Drawdown: {self.max_drawdown*100:.2f}%
  Calmar Ratio: {self.calmar_ratio:.2f}

Trading:
  Total Trades: {self.total_trades}
  Win Rate: {self.win_rate*100:.1f}%
  Profit Factor: {self.profit_factor:.2f}
  Avg Trade Return: {self.avg_trade_return*100:.2f}%

Capital:
  Initial: ${self.initial_capital:,.0f}
  Final: ${self.final_value:,.0f}
"""


class BacktestEngine:
    """
    VectorBT-based backtesting engine.

    Provides high-performance vectorized backtesting with support for
    various trading strategies and comprehensive performance metrics.

    Attributes:
        config: BacktestConfig instance

    Example:
        engine = BacktestEngine()

        # Run mean reversion strategy
        result = engine.run_mean_reversion(
            prices,
            lookback=20,
            entry_zscore=-2.0,
            exit_zscore=0.0
        )

        # Run MA crossover strategy
        result = engine.run_ma_crossover(
            prices,
            fast_period=10,
            slow_period=30
        )
    """

    def __init__(self, config: Optional[BacktestConfig] = None):
        """
        Initialize backtest engine.

        Args:
            config: BacktestConfig instance. If None, uses defaults.
        """
        self.config = config or BacktestConfig()
        self._vbt_available = self._check_vectorbt()

    def _check_vectorbt(self) -> bool:
        """Check if VectorBT is available."""
        try:
            import vectorbt as vbt
            return True
        except ImportError:
            logger.warning("VectorBT not installed. Using fallback implementation.")
            return False

    def run_signals(
        self,
        prices: pd.DataFrame,
        entries: pd.DataFrame,
        exits: pd.DataFrame,
        strategy_name: str = "Custom Strategy",
        parameters: Optional[Dict] = None
    ) -> BacktestResult:
        """
        Run backtest based on entry/exit signals.

        Args:
            prices: Price DataFrame (columns = symbols, index = dates)
            entries: Entry signals (True/False DataFrame)
            exits: Exit signals (True/False DataFrame)
            strategy_name: Name of the strategy
            parameters: Strategy parameters for logging

        Returns:
            BacktestResult with all metrics
        """
        if self._vbt_available:
            return self._run_signals_vbt(prices, entries, exits, strategy_name, parameters)
        return self._run_signals_fallback(prices, entries, exits, strategy_name, parameters)

    def _run_signals_vbt(
        self,
        prices: pd.DataFrame,
        entries: pd.DataFrame,
        exits: pd.DataFrame,
        strategy_name: str,
        parameters: Optional[Dict]
    ) -> BacktestResult:
        """Run backtest using VectorBT."""
        import vectorbt as vbt

        # Align data
        prices, entries, exits = self._align_data(prices, entries, exits)

        # Create portfolio
        portfolio = vbt.Portfolio.from_signals(
            close=prices,
            entries=entries,
            exits=exits,
            init_cash=self.config.initial_capital,
            fees=self.config.commission,
            slippage=self.config.slippage,
            freq=self.config.freq,
            direction='both' if self.config.allow_shorting else 'longonly'
        )

        return self._extract_results_vbt(portfolio, strategy_name, prices, parameters)

    def _run_signals_fallback(
        self,
        prices: pd.DataFrame,
        entries: pd.DataFrame,
        exits: pd.DataFrame,
        strategy_name: str,
        parameters: Optional[Dict]
    ) -> BacktestResult:
        """Run backtest using fallback implementation (without VectorBT)."""
        # Align data
        prices, entries, exits = self._align_data(prices, entries, exits)

        # Simple vectorized backtest
        # Assume single asset for simplicity
        if isinstance(prices, pd.DataFrame):
            close = prices.iloc[:, 0] if len(prices.columns) > 0 else prices
            entry_signals = entries.iloc[:, 0] if isinstance(entries, pd.DataFrame) else entries
            exit_signals = exits.iloc[:, 0] if isinstance(exits, pd.DataFrame) else exits
        else:
            close = prices
            entry_signals = entries
            exit_signals = exits

        # Track positions and equity
        position = 0
        cash = self.config.initial_capital
        equity = [cash]
        trades_list = []
        entry_price = 0

        for i in range(1, len(close)):
            current_price = close.iloc[i]
            prev_price = close.iloc[i-1]

            # Check signals
            if position == 0 and entry_signals.iloc[i]:
                # Enter position
                shares = (cash * self.config.size) / current_price
                cost = shares * current_price * (1 + self.config.commission + self.config.slippage)
                if cost <= cash:
                    position = shares
                    cash -= cost
                    entry_price = current_price
                    trades_list.append({
                        'date': close.index[i],
                        'type': 'BUY',
                        'price': current_price,
                        'shares': shares
                    })

            elif position > 0 and exit_signals.iloc[i]:
                # Exit position
                proceeds = position * current_price * (1 - self.config.commission - self.config.slippage)
                pnl = proceeds - (position * entry_price)
                trades_list.append({
                    'date': close.index[i],
                    'type': 'SELL',
                    'price': current_price,
                    'shares': position,
                    'pnl': pnl
                })
                cash += proceeds
                position = 0

            # Calculate equity
            current_equity = cash + position * current_price
            equity.append(current_equity)

        # Create equity curve
        equity_curve = pd.DataFrame({
            'date': close.index,
            'equity': equity
        })

        # Calculate metrics
        returns = pd.Series(equity).pct_change().dropna()
        total_return = (equity[-1] - self.config.initial_capital) / self.config.initial_capital

        # Handle edge cases
        n_days = len(equity)
        years = n_days / 252

        if years > 0 and total_return > -1:
            cagr = (1 + total_return) ** (1 / years) - 1
        else:
            cagr = 0

        volatility = returns.std() * np.sqrt(252) if len(returns) > 0 else 0
        sharpe = (cagr - self.config.risk_free_rate) / volatility if volatility > 0 else 0

        # Drawdown
        equity_series = pd.Series(equity)
        peak = equity_series.cummax()
        drawdown = (equity_series - peak) / peak
        max_dd = drawdown.min()

        calmar = cagr / abs(max_dd) if max_dd != 0 else 0

        # Sortino
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 0
        sortino = (cagr - self.config.risk_free_rate) / downside_std if downside_std > 0 else 0

        # Trade statistics
        trades_df = pd.DataFrame(trades_list)
        sell_trades = trades_df[trades_df['type'] == 'SELL'] if not trades_df.empty else pd.DataFrame()

        if not sell_trades.empty and 'pnl' in sell_trades.columns:
            wins = sell_trades[sell_trades['pnl'] > 0]
            losses = sell_trades[sell_trades['pnl'] <= 0]
            win_rate = len(wins) / len(sell_trades)
            total_profit = wins['pnl'].sum() if not wins.empty else 0
            total_loss = abs(losses['pnl'].sum()) if not losses.empty else 0
            profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
            avg_trade_return = sell_trades['pnl'].mean() / self.config.initial_capital
        else:
            win_rate = 0
            profit_factor = 0
            avg_trade_return = 0

        # Symbols
        symbols = list(prices.columns) if isinstance(prices, pd.DataFrame) else ['unknown']

        return BacktestResult(
            strategy_name=strategy_name,
            symbols=symbols,
            start_date=close.index[0].date() if hasattr(close.index[0], 'date') else close.index[0],
            end_date=close.index[-1].date() if hasattr(close.index[-1], 'date') else close.index[-1],
            initial_capital=self.config.initial_capital,
            final_value=equity[-1],
            total_return=total_return,
            cagr=cagr,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            calmar_ratio=calmar,
            total_trades=len(sell_trades),
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_trade_return=avg_trade_return,
            equity_curve=equity_curve,
            trades=trades_df,
            parameters=parameters or {},
            volatility=volatility
        )

    def _extract_results_vbt(
        self,
        portfolio,
        strategy_name: str,
        prices: pd.DataFrame,
        parameters: Optional[Dict]
    ) -> BacktestResult:
        """Extract results from VectorBT portfolio."""
        stats = portfolio.stats()

        # Get equity curve
        equity = portfolio.value()
        equity_curve = pd.DataFrame({
            'date': equity.index,
            'equity': equity.values,
        })

        if hasattr(portfolio, 'drawdown'):
            equity_curve['drawdown'] = portfolio.drawdown().values

        if hasattr(portfolio, 'returns'):
            returns = portfolio.returns()
            equity_curve['daily_return'] = returns.values

        # Get trades
        try:
            trades_df = portfolio.trades.records_readable
        except:
            trades_df = pd.DataFrame()

        # Extract metrics with safe fallbacks
        def get_stat(key, default=0):
            try:
                val = stats.get(key, default)
                return float(val) if val is not None else default
            except:
                return default

        total_return = get_stat('Total Return [%]', 0) / 100
        sharpe = get_stat('Sharpe Ratio', 0)
        sortino = get_stat('Sortino Ratio', 0)
        max_dd = get_stat('Max Drawdown [%]', 0) / 100
        calmar = get_stat('Calmar Ratio', 0)
        win_rate = get_stat('Win Rate [%]', 0) / 100
        profit_factor = get_stat('Profit Factor', 0)
        total_trades = int(get_stat('Total Trades', 0))
        avg_trade = get_stat('Avg Winning Trade [%]', 0) / 100

        # CAGR calculation
        n_days = len(equity)
        years = n_days / 252
        if years > 0 and total_return > -1:
            cagr = (1 + total_return) ** (1 / years) - 1
        else:
            cagr = 0

        # Symbols
        symbols = list(prices.columns) if isinstance(prices, pd.DataFrame) else ['unknown']

        return BacktestResult(
            strategy_name=strategy_name,
            symbols=symbols,
            start_date=equity.index[0].date() if hasattr(equity.index[0], 'date') else equity.index[0],
            end_date=equity.index[-1].date() if hasattr(equity.index[-1], 'date') else equity.index[-1],
            initial_capital=self.config.initial_capital,
            final_value=float(stats.get('End Value', self.config.initial_capital)),
            total_return=total_return,
            cagr=cagr,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            calmar_ratio=calmar,
            total_trades=total_trades,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_trade_return=avg_trade,
            equity_curve=equity_curve,
            trades=trades_df,
            parameters=parameters or {}
        )

    def run_mean_reversion(
        self,
        prices: pd.DataFrame,
        lookback: int = 20,
        entry_zscore: float = -2.0,
        exit_zscore: float = 0.0,
        strategy_name: str = "Mean Reversion"
    ) -> BacktestResult:
        """
        Run mean reversion strategy backtest.

        Strategy Logic:
        - Calculate rolling z-score of prices
        - Enter long when z-score < entry_zscore (oversold)
        - Exit when z-score > exit_zscore (mean reversion)

        Args:
            prices: Price DataFrame
            lookback: Rolling window for mean/std calculation
            entry_zscore: Z-score threshold for entry (negative = oversold)
            exit_zscore: Z-score threshold for exit
            strategy_name: Name for the strategy

        Returns:
            BacktestResult
        """
        # Calculate z-score
        rolling_mean = prices.rolling(window=lookback).mean()
        rolling_std = prices.rolling(window=lookback).std()
        zscore = (prices - rolling_mean) / rolling_std

        # Generate signals
        entries = zscore < entry_zscore
        exits = zscore > exit_zscore

        parameters = {
            'lookback': lookback,
            'entry_zscore': entry_zscore,
            'exit_zscore': exit_zscore
        }

        return self.run_signals(
            prices=prices,
            entries=entries,
            exits=exits,
            strategy_name=strategy_name,
            parameters=parameters
        )

    def run_ma_crossover(
        self,
        prices: pd.DataFrame,
        fast_period: int = 10,
        slow_period: int = 30,
        strategy_name: str = "MA Crossover"
    ) -> BacktestResult:
        """
        Run moving average crossover strategy backtest.

        Strategy Logic:
        - Calculate fast and slow moving averages
        - Enter when fast MA crosses above slow MA (golden cross)
        - Exit when fast MA crosses below slow MA (death cross)

        Args:
            prices: Price DataFrame
            fast_period: Fast MA period
            slow_period: Slow MA period
            strategy_name: Name for the strategy

        Returns:
            BacktestResult
        """
        # Calculate moving averages
        fast_ma = prices.rolling(window=fast_period).mean()
        slow_ma = prices.rolling(window=slow_period).mean()

        # Golden cross: fast crosses above slow
        entries = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))

        # Death cross: fast crosses below slow
        exits = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))

        parameters = {
            'fast_period': fast_period,
            'slow_period': slow_period
        }

        return self.run_signals(
            prices=prices,
            entries=entries,
            exits=exits,
            strategy_name=strategy_name,
            parameters=parameters
        )

    def run_rsi_strategy(
        self,
        prices: pd.DataFrame,
        period: int = 14,
        oversold: float = 30,
        overbought: float = 70,
        strategy_name: str = "RSI Strategy"
    ) -> BacktestResult:
        """
        Run RSI (Relative Strength Index) strategy backtest.

        Strategy Logic:
        - Calculate RSI
        - Enter when RSI < oversold threshold
        - Exit when RSI > overbought threshold

        Args:
            prices: Price DataFrame
            period: RSI calculation period
            oversold: RSI level for entry (typically 30)
            overbought: RSI level for exit (typically 70)
            strategy_name: Name for the strategy

        Returns:
            BacktestResult
        """
        # Calculate RSI
        delta = prices.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        # Generate signals
        entries = rsi < oversold
        exits = rsi > overbought

        parameters = {
            'period': period,
            'oversold': oversold,
            'overbought': overbought
        }

        return self.run_signals(
            prices=prices,
            entries=entries,
            exits=exits,
            strategy_name=strategy_name,
            parameters=parameters
        )

    def run_bollinger_bands(
        self,
        prices: pd.DataFrame,
        period: int = 20,
        num_std: float = 2.0,
        strategy_name: str = "Bollinger Bands"
    ) -> BacktestResult:
        """
        Run Bollinger Bands strategy backtest.

        Strategy Logic:
        - Calculate upper/lower bands as mean +/- num_std * std
        - Enter when price touches lower band
        - Exit when price touches upper band

        Args:
            prices: Price DataFrame
            period: Moving average period
            num_std: Number of standard deviations for bands
            strategy_name: Name for the strategy

        Returns:
            BacktestResult
        """
        # Calculate Bollinger Bands
        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()

        upper_band = sma + (std * num_std)
        lower_band = sma - (std * num_std)

        # Generate signals
        entries = prices < lower_band  # Buy when touching lower band
        exits = prices > upper_band    # Sell when touching upper band

        parameters = {
            'period': period,
            'num_std': num_std
        }

        return self.run_signals(
            prices=prices,
            entries=entries,
            exits=exits,
            strategy_name=strategy_name,
            parameters=parameters
        )

    def parameter_optimization(
        self,
        prices: pd.DataFrame,
        strategy_func: Callable,
        param_grid: Dict[str, List],
        metric: str = 'sharpe_ratio',
        top_n: int = 10
    ) -> pd.DataFrame:
        """
        Optimize strategy parameters using grid search.

        Tests all combinations of parameters and returns results
        sorted by the specified metric.

        Args:
            prices: Price DataFrame
            strategy_func: Strategy function that returns BacktestResult
            param_grid: Parameter grid {'param1': [1, 2, 3], 'param2': [10, 20]}
            metric: Metric to optimize ('sharpe_ratio', 'total_return', etc.)
            top_n: Number of top results to return

        Returns:
            DataFrame with parameter combinations and their metrics

        Example:
            results = engine.parameter_optimization(
                prices,
                engine.run_mean_reversion,
                {'lookback': [10, 20, 30], 'entry_zscore': [-1.5, -2.0, -2.5]}
            )
        """
        import itertools

        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())

        results = []
        total_combinations = 1
        for values in param_values:
            total_combinations *= len(values)

        logger.info(f"Testing {total_combinations} parameter combinations...")

        for i, combination in enumerate(itertools.product(*param_values)):
            params = dict(zip(param_names, combination))

            try:
                result = strategy_func(prices, **params)
                results.append({
                    **params,
                    'total_return': result.total_return,
                    'cagr': result.cagr,
                    'sharpe_ratio': result.sharpe_ratio,
                    'sortino_ratio': result.sortino_ratio,
                    'max_drawdown': result.max_drawdown,
                    'calmar_ratio': result.calmar_ratio,
                    'win_rate': result.win_rate,
                    'total_trades': result.total_trades,
                    'profit_factor': result.profit_factor,
                })
            except Exception as e:
                logger.warning(f"Parameter combination {params} failed: {e}")
                continue

            # Progress logging
            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i + 1}/{total_combinations}")

        if not results:
            logger.warning("No successful backtests")
            return pd.DataFrame()

        results_df = pd.DataFrame(results)
        results_df = results_df.sort_values(metric, ascending=False)

        return results_df.head(top_n)

    def walk_forward_optimization(
        self,
        prices: pd.DataFrame,
        strategy_func: Callable,
        param_grid: Dict[str, List],
        train_period: int = 252,
        test_period: int = 63,
        metric: str = 'sharpe_ratio'
    ) -> List[BacktestResult]:
        """
        Perform walk-forward optimization.

        Splits data into training and testing periods, optimizes on
        training data, and tests on out-of-sample data.

        Args:
            prices: Price DataFrame
            strategy_func: Strategy function
            param_grid: Parameter grid for optimization
            train_period: Number of days for training
            test_period: Number of days for testing
            metric: Metric to optimize

        Returns:
            List of BacktestResults for each test period
        """
        results = []
        n_days = len(prices)

        i = 0
        while i + train_period + test_period <= n_days:
            # Training period
            train_data = prices.iloc[i:i + train_period]

            # Find best parameters
            optimization_results = self.parameter_optimization(
                train_data,
                strategy_func,
                param_grid,
                metric=metric,
                top_n=1
            )

            if optimization_results.empty:
                i += test_period
                continue

            # Get best parameters
            best_params = optimization_results.iloc[0].to_dict()
            # Remove metric columns
            param_keys = list(param_grid.keys())
            best_params = {k: v for k, v in best_params.items() if k in param_keys}

            # Test period
            test_data = prices.iloc[i + train_period:i + train_period + test_period]

            # Run backtest with best parameters
            try:
                result = strategy_func(test_data, **best_params)
                result.parameters['walk_forward_period'] = i // test_period
                results.append(result)
            except Exception as e:
                logger.warning(f"Walk-forward test failed: {e}")

            i += test_period

        return results

    def _align_data(
        self,
        prices: pd.DataFrame,
        entries: pd.DataFrame,
        exits: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Align data indices and remove NaN rows."""
        # Get common index
        common_index = prices.index.intersection(entries.index).intersection(exits.index)

        prices = prices.loc[common_index]
        entries = entries.loc[common_index]
        exits = exits.loc[common_index]

        # Remove rows with NaN
        valid_mask = ~(prices.isna().any(axis=1) | entries.isna().any(axis=1) | exits.isna().any(axis=1))
        prices = prices.loc[valid_mask]
        entries = entries.loc[valid_mask]
        exits = exits.loc[valid_mask]

        return prices, entries, exits


# =============================================================================
# Strategy Helpers
# =============================================================================

def calculate_zscore(series: pd.Series, lookback: int = 20) -> pd.Series:
    """
    Calculate rolling z-score.

    Args:
        series: Price series
        lookback: Rolling window period

    Returns:
        Z-score series
    """
    rolling_mean = series.rolling(window=lookback).mean()
    rolling_std = series.rolling(window=lookback).std()
    return (series - rolling_mean) / rolling_std


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate RSI (Relative Strength Index).

    Args:
        prices: Price series
        period: RSI period

    Returns:
        RSI series (0-100)
    """
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_macd(
    prices: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate MACD (Moving Average Convergence Divergence).

    Args:
        prices: Price series
        fast: Fast EMA period
        slow: Slow EMA period
        signal: Signal line period

    Returns:
        Tuple of (MACD line, Signal line, Histogram)
    """
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()

    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram
