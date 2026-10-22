# -*- coding: utf-8 -*-
"""
Dashboard Page - Portfolio Overview

Displays:
- Portfolio summary and total value
- Holdings breakdown
- Market indices
- Recent activity and performance
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import sys
from pathlib import Path
import io

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


from views._shared import (chart, money, page_header, key_points, ACCENT, ACCENT2, GRAY, LIGHT,  # house style
                           RED, GREEN, UP, DOWN)

# Initialize session state
if 'positions' not in st.session_state:
    st.session_state.positions = {}
if 'trades' not in st.session_state:
    st.session_state.trades = []


def calculate_positions_from_trades() -> dict:
    """從交易紀錄自動計算目前持倉 (Current positions from Trade Log)。"""
    try:
        from core.local_storage import get_all_trades
        trades = get_all_trades()
    except Exception:
        trades = st.session_state.get('trades', [])

    if not trades:
        return {}

    positions = {}
    for trade in trades:
        symbol = trade.get('symbol', '')
        if not symbol:
            continue

        shares = float(trade.get('shares', 0))
        price = float(trade.get('price', 0))
        trade_type = trade.get('trade_type', trade.get('type', ''))

        if symbol not in positions:
            positions[symbol] = {'shares': 0, 'total_cost': 0, 'trades': 0}

        if '買' in str(trade_type).lower() or 'buy' in str(trade_type).lower():
            positions[symbol]['shares'] += shares
            positions[symbol]['total_cost'] += shares * price
            positions[symbol]['trades'] += 1
        elif '賣' in str(trade_type).lower() or 'sell' in str(trade_type).lower():
            positions[symbol]['shares'] -= shares
            positions[symbol]['total_cost'] -= shares * price
            positions[symbol]['trades'] += 1

    # 過濾掉已清倉的（shares == 0）
    result = {}
    for symbol, pos in positions.items():
        if pos['shares'] > 0:
            avg_cost = pos['total_cost'] / pos['shares'] if pos['shares'] > 0 else 0
            result[symbol] = {
                'shares': pos['shares'],
                'avg_cost': round(avg_cost, 2),
                'cost': round(pos['total_cost'], 2),
                'current_price': avg_cost,  # Will be updated if DataManager available
                'value': round(pos['total_cost'], 2),
                'pnl': 0,
                'pnl_pct': 0,
            }

    return result


def get_data_manager():
    """Get or create DataManager instance."""
    if 'data_manager' not in st.session_state:
        try:
            from core import DataManager
            st.session_state.data_manager = DataManager()
        except Exception as e:
            st.error(f"Failed to initialize DataManager: {e}")
            return None
    return st.session_state.data_manager


def plot_portfolio_pie(positions: dict):
    """Create pie chart for portfolio allocation."""
    if not positions:
        return None

    fig = go.Figure(data=[go.Pie(
        labels=list(positions.keys()),
        values=[p['value'] for p in positions.values()],
        textinfo='label+percent',
        hole=0.3
    )])

    fig.update_layout(
        title='投資組合配置 (Portfolio Allocation)',
        height=350
    )

    return fig


def plot_performance_line(returns_data: dict):
    """Create performance line chart."""
    fig = go.Figure()

    for name, returns in returns_data.items():
        fig.add_trace(go.Scatter(
            x=returns.index,
            y=(1 + returns).cumprod() * 100 - 100,
            mode='lines',
            name=name
        ))

    fig.update_layout(
        title='績效比較 (Performance Comparison)',
        xaxis_title='日期 (Date)',
        yaxis_title='報酬率 (Return %)',
        height=350,
        showlegend=True
    )

    return fig


page_header("總績效", "投資組合、持股、市場與近期交易的摘要。")

# Quick actions
col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    st.markdown("**快速操作 (Quick Actions)**")

with col3:
    if st.button("重新整理資料 (Refresh Data)"):
        st.rerun()

# Portfolio metrics
st.subheader("投資組合摘要 (Portfolio Summary)")

# Calculate portfolio metrics
total_value = 0
total_cost = 0
positions = st.session_state.positions

# 自動從交易紀錄計算持倉
if not positions:
    auto_positions = calculate_positions_from_trades()
    if auto_positions:
        st.session_state.positions = auto_positions
        positions = auto_positions

if positions:
    for symbol, pos in positions.items():
        total_value += pos.get('value', 0)
        total_cost += pos.get('cost', 0)

total_pnl = total_value - total_cost if total_cost > 0 else 0
total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="投資組合市值 (Portfolio Value)",
        value=money(total_value, list(positions)),
        delta=f"{total_pnl_pct:+.2f}%" if total_cost > 0 else None,
        delta_color="inverse",
    )

with col2:
    st.metric(
        label="總損益 (Total P&L)",
        value=money(total_pnl, list(positions)),
        delta=None
    )

with col3:
    st.metric(
        label="總報酬率 (Total Return)",
        value=f"{total_pnl_pct:.2f}%" if total_cost > 0 else "N/A",
        delta=None
    )

with col4:
    st.metric(
        label="持倉數 (Positions)",
        value=str(len(positions)),
        delta=None
    )

st.markdown("---")

# Main content area
col1, col2 = st.columns(2)

with col1:
    # Holdings section
    st.subheader("持股明細 (Holdings)")

    if positions:
        holdings_data = []
        for symbol, pos in positions.items():
            holdings_data.append({
                '股票代碼 (Symbol)': symbol,
                '股數 (Shares)': pos.get('shares', 0),
                '平均成本 (Avg Cost)': money(pos.get('avg_cost', 0), symbol),
                '現價 (Current Price)': money(pos.get('current_price', 0), symbol),
                '市值 (Value)': money(pos.get('value', 0), symbol),
                '損益 (P&L)': money(pos.get('pnl', 0), symbol),
                '損益% (P&L %)': f"{pos.get('pnl_pct', 0):.2f}%"
            })

        holdings_df = pd.DataFrame(holdings_data)
        st.dataframe(holdings_df, width="stretch", hide_index=True)

        # Portfolio pie chart
        fig = plot_portfolio_pie(positions)
        if fig:
            chart(fig)
    else:
        st.info("尚無持倉資料，請至資料管理頁面新增股票，或在交易紀錄頁面記錄交易。")

        # Demo data option
        if st.button("載入範例投資組合 (Demo)"):
            st.session_state.positions = {
                'AAPL': {'shares': 100, 'avg_cost': 150, 'current_price': 175, 'value': 17500, 'cost': 15000, 'pnl': 2500, 'pnl_pct': 16.67},
                'MSFT': {'shares': 50, 'avg_cost': 280, 'current_price': 310, 'value': 15500, 'cost': 14000, 'pnl': 1500, 'pnl_pct': 10.71},
                'GOOGL': {'shares': 30, 'avg_cost': 120, 'current_price': 140, 'value': 4200, 'cost': 3600, 'pnl': 600, 'pnl_pct': 16.67},
            }
            st.rerun()

with col2:
    # Market overview
    st.subheader("市場概覽 (Market Overview)")

    dm = get_data_manager()

    # Market indices
    indices = [
        ('SPY', 'S&P 500'),
        ('QQQ', 'NASDAQ'),
        ('IWM', 'Russell 2000'),
    ]

    if dm:
        for symbol, name in indices:
            try:
                quote = dm.fetch_quote(symbol)
                if quote:
                    price = quote.get('current_price', quote.get('close', 0))
                    change = quote.get('change_percent', 0)
                    col_a, col_b = st.columns([2, 1])
                    with col_a:
                        st.write(f"**{name}** ({symbol})")
                    with col_b:
                        st.metric(
                            label="",
                            value=money(price, symbol) if isinstance(price, (int, float)) else "N/A",
                            delta=f"{change:.2f}%" if isinstance(change, (int, float)) else None,
                            delta_color="inverse",
                        )
            except Exception:
                st.write(f"**{name}** ({symbol}): Data unavailable")
    else:
        st.info("設定好 DataManager (資料管理器) 後即可顯示市場資料")

    st.markdown("---")

    # Quick stats from backtest results
    st.subheader("最近回測結果 (Recent Backtest Results)")

    if 'backtest_results' in st.session_state and st.session_state.backtest_results:
        result = st.session_state.backtest_results
        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("夏普比率 (Sharpe Ratio)", f"{result.sharpe_ratio:.2f}")
            st.metric("總報酬率 (Total Return)", f"{result.total_return:.2%}")
        with col_b:
            st.metric("最大回撤 (Max Drawdown)", f"{result.max_drawdown:.2%}")
            st.metric("勝率 (Win Rate)", f"{result.win_rate:.2%}")
    else:
        st.info("執行回測後即可在此查看結果")

st.markdown("---")

# Recent trades
st.subheader("最近交易紀錄 (Recent Trades)")

if st.session_state.trades:
    trades_df = pd.DataFrame(st.session_state.trades[-10:])  # Last 10 trades
    st.dataframe(trades_df, width="stretch", hide_index=True)
else:
    st.info("尚無交易紀錄，請至交易紀錄頁面記錄交易。")

st.markdown("---")

# Performance section (if we have cached price data)
if 'price_data' in st.session_state and st.session_state.price_data:
    st.subheader("價格表現 (Price Performance) （快取資料）")

    cached_symbols = list(st.session_state.price_data.keys())
    selected_symbols = st.multiselect(
        "選擇要比較的股票 (Select symbols to compare)",
        cached_symbols,
        default=cached_symbols[:3] if len(cached_symbols) >= 3 else cached_symbols
    )

    if selected_symbols:
        returns_data = {}
        for symbol in selected_symbols:
            df = st.session_state.price_data[symbol]
            if 'close' in df.columns:
                returns = df['close'].pct_change().dropna()
                returns_data[symbol] = returns

        if returns_data:
            fig = plot_performance_line(returns_data)
            chart(fig)

st.markdown("---")

# --- 匯出功能 (Export) ---
st.subheader("匯出資料 (Export)")
export_col1, export_col2 = st.columns(2)

with export_col1:
    if positions:
        positions_df = pd.DataFrame([
            {"代碼": sym, "股數": p.get("shares", 0), "均價": p.get("avg_cost", 0),
             "現價": p.get("current_price", 0), "市值": p.get("value", 0),
             "損益": p.get("pnl", 0), "損益%": p.get("pnl_pct", 0)}
            for sym, p in positions.items()
        ])
        csv = positions_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            "匯出持倉為 CSV",
            csv,
            file_name=f"持倉_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

with export_col2:
    if st.session_state.trades:
        trades_df = pd.DataFrame(st.session_state.trades)
        csv = trades_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            "匯出交易紀錄為 CSV",
            csv,
            file_name=f"交易紀錄_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

st.markdown("---")

# Footer
st.markdown("---")
st.caption("量化交易工具 (Quantitative Trading Tool) - 用於學習與交易")

# Sidebar info
with st.sidebar:
    st.subheader("系統狀態 (System Status)")

    # Check module availability
    modules_status = {
        'DataManager': False,
        'BacktestEngine': False,
        'PortfolioOptimizer': False,
        'RiskCalculator': False
    }

    try:
        from core import DataManager
        modules_status['DataManager'] = True
    except Exception:
        pass

    try:
        from core import BacktestEngine
        modules_status['BacktestEngine'] = True
    except Exception:
        pass

    try:
        from core import PortfolioOptimizer
        modules_status['PortfolioOptimizer'] = True
    except Exception:
        pass

    try:
        from core import RiskCalculator
        modules_status['RiskCalculator'] = True
    except Exception:
        pass

    for module, status in modules_status.items():
        if status:
            st.write(f"[正常 (OK)] {module}")
        else:
            st.write(f"[未啟用 (--)] {module}")

    st.markdown("---")
    st.caption(f"最後更新 (Last updated): {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
