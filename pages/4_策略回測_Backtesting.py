# -*- coding: utf-8 -*-
"""
Backtesting Page

Features:
- Strategy selection and configuration
- Parameter optimization
- Backtest execution with progress
- Results visualization and metrics
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


from views._shared import (chart, page_header, key_points, ACCENT, ACCENT2, GRAY, LIGHT,  # house style
                           RED, GREEN, UP, DOWN)

# Initialize session state
if 'backtest_results' not in st.session_state:
    st.session_state.backtest_results = None
if 'price_data' not in st.session_state:
    st.session_state.price_data = {}


def get_data_manager():
    """Get or create DataManager instance."""
    if 'data_manager' not in st.session_state:
        try:
            from core import DataManager
            st.session_state.data_manager = DataManager()
        except Exception as e:
            st.error(f"初始化 DataManager 失敗：{e}")
            return None
    return st.session_state.data_manager


def get_backtest_engine():
    """Get BacktestEngine instance."""
    try:
        from core import BacktestEngine
        return BacktestEngine()
    except Exception as e:
        st.error(f"初始化 BacktestEngine 失敗：{e}")
        return None


def plot_equity_curve(equity_curve: pd.Series, benchmark: pd.Series = None):
    """Plot equity curve with optional benchmark."""
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=equity_curve.index,
        y=equity_curve.values,
        mode='lines',
        name='策略 (Strategy)',
        line=dict(color=ACCENT, width=2)
    ))

    if benchmark is not None:
        # Normalize benchmark to start at same value as equity curve
        benchmark_normalized = benchmark / benchmark.iloc[0] * equity_curve.iloc[0]
        fig.add_trace(go.Scatter(
            x=benchmark.index,
            y=benchmark_normalized.values,
            mode='lines',
            name='買入持有 (Buy & Hold)',
            line=dict(color=GRAY, width=1, dash='dash')
        ))

    fig.update_layout(
        title='權益曲線 (Equity Curve)',
        xaxis_title='日期 (Date)',
        yaxis_title='投資組合價值 (Portfolio Value)',
        height=400,
        showlegend=True
    )

    return fig


def plot_drawdown(equity_curve: pd.Series):
    """Plot drawdown chart."""
    # Calculate drawdown
    peak = equity_curve.cummax()
    drawdown = (equity_curve - peak) / peak * 100

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=drawdown.index,
        y=drawdown.values,
        fill='tozeroy',
        mode='lines',
        name='回撤 (Drawdown)',
        line=dict(color=RED, width=1),
        fillcolor='rgba(255, 0, 0, 0.3)'
    ))

    fig.update_layout(
        title='最大回撤 (Max Drawdown)',
        xaxis_title='日期 (Date)',
        yaxis_title='回撤 (%)',
        height=300
    )

    return fig


def plot_returns_distribution(returns: pd.Series):
    """Plot returns distribution histogram."""
    fig = go.Figure()

    fig.add_trace(go.Histogram(
        x=returns.values * 100,
        nbinsx=50,
        name='報酬 (Returns)',
        marker_color=ACCENT,
        opacity=0.7
    ))

    # Add normal distribution overlay
    mean_ret = returns.mean() * 100
    std_ret = returns.std() * 100

    fig.update_layout(
        title='報酬分佈 (Returns Distribution)',
        xaxis_title='日報酬 (%)',
        yaxis_title='頻率 (Frequency)',
        height=300
    )

    return fig


page_header("策略回測", "以歷史資料測試交易規則，並計入手續費與滑價。")

# Strategy selection
st.subheader("策略設定 (Strategy Configuration)")

col1, col2 = st.columns(2)

with col1:
    strategy = st.selectbox(
        "選擇策略 (Select Strategy)",
        ["均值回歸 (Mean Reversion)", "均線交叉 (MA Crossover)", "RSI 策略 (RSI Strategy)", "布林帶 (Bollinger Bands)"],
        key="strategy_select"
    )

with col2:
    # Pre-fill from workflow state if available
    _prefill = ""
    try:
        from core.workflow import WorkflowState, render_active_stock_badge
        _wf_sym = WorkflowState.get_active_stock()
        if _wf_sym:
            _prefill = _wf_sym
            render_active_stock_badge()
    except Exception:
        pass

    symbols_input = st.text_input(
        "股票代碼（逗號分隔）(Symbols)",
        value=_prefill,
        placeholder="例如：AAPL, MSFT, GOOGL",
        key="symbols_input"
    )

# Strategy parameters
st.subheader("參數設定 (Parameters)")

if strategy == "均值回歸 (Mean Reversion)":
    col1, col2, col3 = st.columns(3)
    with col1:
        lookback = st.slider("回望期間 (Lookback Period)", 5, 100, 20, key="mr_lookback")
    with col2:
        entry_z = st.slider("進場門檻 (Entry Z-Score)", 1.0, 4.0, 2.0, 0.1, key="mr_entry")
    with col3:
        exit_z = st.slider("出場門檻 (Exit Z-Score)", 0.0, 2.0, 0.5, 0.1, key="mr_exit")
    params = {'lookback': lookback, 'entry_zscore': entry_z, 'exit_zscore': exit_z}

elif strategy == "均線交叉 (MA Crossover)":
    col1, col2 = st.columns(2)
    with col1:
        fast_period = st.slider("快速均線週期 (Fast MA Period)", 5, 50, 10, key="ma_fast")
    with col2:
        slow_period = st.slider("慢速均線週期 (Slow MA Period)", 20, 200, 30, key="ma_slow")
    params = {'fast_period': fast_period, 'slow_period': slow_period}

elif strategy == "RSI 策略 (RSI Strategy)":
    col1, col2, col3 = st.columns(3)
    with col1:
        rsi_period = st.slider("RSI 週期 (RSI Period)", 5, 30, 14, key="rsi_period")
    with col2:
        oversold = st.slider("超賣水位 (Oversold Level)", 10, 40, 30, key="rsi_oversold")
    with col3:
        overbought = st.slider("超買水位 (Overbought Level)", 60, 90, 70, key="rsi_overbought")
    params = {'period': rsi_period, 'oversold': oversold, 'overbought': overbought}

elif strategy == "布林帶 (Bollinger Bands)":
    col1, col2 = st.columns(2)
    with col1:
        bb_period = st.slider("週期 (Period)", 10, 50, 20, key="bb_period")
    with col2:
        bb_std = st.slider("標準差 (Standard Deviations)", 1.0, 3.0, 2.0, 0.1, key="bb_std")
    params = {'period': bb_period, 'num_std': bb_std}

# Date range
st.subheader("日期範圍 (Date Range)")
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input(
        "開始日期 (Start Date)",
        value=datetime.now() - timedelta(days=365*2),
        key="bt_start"
    )
with col2:
    end_date = st.date_input(
        "結束日期 (End Date)",
        value=datetime.now(),
        key="bt_end"
    )

# Backtest settings
st.subheader("回測設定 (Backtest Settings)")
col1, col2, col3 = st.columns(3)

with col1:
    initial_capital = st.number_input(
        "初始資金 (Initial Capital)",
        min_value=1000,
        value=100000,
        step=1000,
        key="bt_capital"
    )

with col2:
    commission = st.number_input(
        "手續費 (Commission) (%)",
        min_value=0.0,
        value=0.1,
        step=0.01,
        format="%.2f",
        key="bt_commission"
    )

with col3:
    slippage = st.number_input(
        "滑點 (Slippage) (%)",
        min_value=0.0,
        value=0.05,
        step=0.01,
        format="%.2f",
        key="bt_slippage"
    )

# Run backtest
st.markdown("---")

col1, col2 = st.columns([1, 3])

with col1:
    run_backtest = st.button("執行回測 (Run Backtest)", type="primary")

with col2:
    run_optimization = st.button("執行參數最佳化 (Run Parameter Optimization)")

if run_backtest:
    if not symbols_input:
        st.warning("請輸入至少一個股票代碼 (Please enter at least one symbol)")
    else:
        symbols = [s.strip().upper() for s in symbols_input.split(',')]

        dm = get_data_manager()
        engine = get_backtest_engine()

        if dm and engine:
            with st.spinner("正在取得價格資料 (Fetching price data)..."):
                # Fetch data for all symbols
                price_data = {}
                for symbol in symbols:
                    try:
                        df = dm.fetch_ohlcv(
                            symbol,
                            start_date.strftime('%Y-%m-%d'),
                            end_date.strftime('%Y-%m-%d')
                        )
                        if df is not None and not df.empty:
                            price_data[symbol] = df['close']
                    except Exception as e:
                        st.error(f"未能取得 {symbol} 的資料：{e}")

                if not price_data:
                    st.error("沒有可用的價格資料 (No price data available)")
                else:
                    # Combine into single DataFrame
                    prices_df = pd.DataFrame(price_data)
                    prices_df = prices_df.dropna()

                    if prices_df.empty:
                        st.error("選定股票沒有重疊的資料 (No overlapping data for selected symbols)")
                    else:
                        st.success(f"已載入 {len(price_data)} 檔股票、{len(prices_df)} 天的資料")

                        with st.spinner("正在執行回測 (Running backtest)..."):
                            try:
                                # Run backtest based on strategy
                                if strategy == "均值回歸 (Mean Reversion)":
                                    result = engine.run_mean_reversion(
                                        prices_df,
                                        lookback=params['lookback'],
                                        entry_zscore=params['entry_zscore'],
                                        exit_zscore=params['exit_zscore'],
                                        initial_capital=initial_capital,
                                        commission_pct=commission / 100,
                                        slippage_pct=slippage / 100
                                    )
                                elif strategy == "均線交叉 (MA Crossover)":
                                    result = engine.run_ma_crossover(
                                        prices_df,
                                        fast_period=params['fast_period'],
                                        slow_period=params['slow_period'],
                                        initial_capital=initial_capital,
                                        commission_pct=commission / 100,
                                        slippage_pct=slippage / 100
                                    )
                                elif strategy == "RSI 策略 (RSI Strategy)":
                                    result = engine.run_rsi_strategy(
                                        prices_df,
                                        period=params['period'],
                                        oversold=params['oversold'],
                                        overbought=params['overbought'],
                                        initial_capital=initial_capital,
                                        commission_pct=commission / 100,
                                        slippage_pct=slippage / 100
                                    )
                                elif strategy == "布林帶 (Bollinger Bands)":
                                    result = engine.run_bollinger_bands(
                                        prices_df,
                                        period=params['period'],
                                        num_std=params['num_std'],
                                        initial_capital=initial_capital,
                                        commission_pct=commission / 100,
                                        slippage_pct=slippage / 100
                                    )

                                st.session_state.backtest_results = result
                                st.session_state.backtest_prices = prices_df
                                st.success("回測已完成 (Backtest completed)!")

                            except Exception as e:
                                st.error(f"回測失敗：{e}")
                                import traceback
                                st.error(traceback.format_exc())

if run_optimization and symbols_input:
    symbols = [s.strip().upper() for s in symbols_input.split(',')]
    dm = get_data_manager()
    engine = get_backtest_engine()

    if dm and engine:
        with st.spinner("正在執行參數最佳化 (Running parameter optimization)..."):
            # Fetch data
            price_data = {}
            for symbol in symbols:
                try:
                    df = dm.fetch_ohlcv(
                        symbol,
                        start_date.strftime('%Y-%m-%d'),
                        end_date.strftime('%Y-%m-%d')
                    )
                    if df is not None and not df.empty:
                        price_data[symbol] = df['close']
                except Exception as e:
                    st.error(f"未能取得 {symbol} 的資料：{e}")

            if price_data:
                prices_df = pd.DataFrame(price_data).dropna()

                # Define parameter grid based on strategy
                if strategy == "均值回歸 (Mean Reversion)":
                    param_grid = {
                        'lookback': [10, 15, 20, 25, 30],
                        'entry_zscore': [1.5, 2.0, 2.5],
                        'exit_zscore': [0.0, 0.5, 1.0]
                    }
                elif strategy == "均線交叉 (MA Crossover)":
                    param_grid = {
                        'fast_period': [5, 10, 15, 20],
                        'slow_period': [20, 30, 50, 100]
                    }
                else:
                    st.warning("此策略不提供最佳化功能 (Optimization not available for this strategy)")
                    param_grid = None

                if param_grid:
                    try:
                        results = engine.parameter_optimization(
                            prices_df,
                            strategy.lower().replace(' ', '_').replace('(', '').replace(')', ''),
                            param_grid,
                            initial_capital=initial_capital
                        )

                        st.success("最佳化已完成 (Optimization completed)!")
                        st.subheader("最佳化結果 (Optimization Results)")
                        st.dataframe(
                            results.sort_values('sharpe_ratio', ascending=False).head(10)
                        )
                    except Exception as e:
                        st.error(f"最佳化失敗：{e}")

# Results section
st.markdown("---")
st.subheader("回測結果 (Results)")

if st.session_state.backtest_results is not None:
    result = st.session_state.backtest_results

    # Key metrics
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            "總報酬 (Total Return)",
            f"{result.total_return:.2%}",
            delta=None
        )

    with col2:
        st.metric(
            "年化複合報酬率 (CAGR)",
            f"{result.cagr:.2%}",
            delta=None
        )

    with col3:
        st.metric(
            "夏普比率 (Sharpe Ratio)",
            f"{result.sharpe_ratio:.2f}",
            delta=None
        )

    with col4:
        st.metric(
            "最大回撤 (Max Drawdown)",
            f"{result.max_drawdown:.2%}",
            delta=None
        )

    with col5:
        st.metric(
            "勝率 (Win Rate)",
            f"{result.win_rate:.2%}",
            delta=None
        )

    # Secondary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("交易次數 (Total Trades)", f"{result.total_trades}")

    with col2:
        st.metric("索提諾比率 (Sortino Ratio)", f"{result.sortino_ratio:.2f}")

    with col3:
        st.metric("獲利因子 (Profit Factor)", f"{result.profit_factor:.2f}")

    with col4:
        st.metric("卡瑪比率 (Calmar Ratio)", f"{result.calmar_ratio:.2f}")

    st.markdown("---")

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        # Equity curve
        if result.equity_curve is not None:
            benchmark = st.session_state.backtest_prices.iloc[:, 0] if 'backtest_prices' in st.session_state else None
            fig = plot_equity_curve(result.equity_curve, benchmark)
            chart(fig)

    with col2:
        # Drawdown
        if result.equity_curve is not None:
            fig = plot_drawdown(result.equity_curve)
            chart(fig)

    # Returns distribution
    if result.returns is not None:
        fig = plot_returns_distribution(result.returns)
        chart(fig)

    # Trade details
    if result.trades is not None and not result.trades.empty:
        with st.expander("交易紀錄 (Trade Details)"):
            st.dataframe(result.trades)

    # Export results
    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        if result.equity_curve is not None:
            csv = result.equity_curve.to_csv()
            st.download_button(
                "下載權益曲線 (Download Equity Curve)",
                data=csv,
                file_name="equity_curve.csv",
                mime="text/csv"
            )

    with col2:
        if result.trades is not None:
            csv = result.trades.to_csv(index=False)
            st.download_button(
                "下載交易紀錄 (Download Trade Log)",
                data=csv,
                file_name="trades.csv",
                mime="text/csv"
            )

else:
    st.info("執行回測以查看結果 (Run a backtest to see results here.)")
