# -*- coding: utf-8 -*-
"""
Trade Log Page

Features:
- Manual trade entry
- Trade history with filtering
- P&L analysis
- Export functionality
- Trade statistics
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import io
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import local storage for persistence
from core.local_storage import (
    save_trade, get_all_trades, delete_trade,
    get_trade_statistics as get_db_statistics
)


from views._state import get_symbol, next_step, plan as _plan, step_bar
from views._shared import (chart, money, page_header, key_points, ACCENT, ACCENT2, GRAY, LIGHT,  # house style
                           RED, GREEN, UP, DOWN)

# Initialize session state from SQLite
if 'trades' not in st.session_state:
    # Load trades from SQLite database
    db_trades = get_all_trades()
    # Convert to session state format
    st.session_state.trades = [
        {
            'id': t['id'],
            'date': t['trade_date'],
            'symbol': t['symbol'],
            'type': '買入 (Buy)' if t['trade_type'] == 'BUY' else '賣出 (Sell)',
            'quantity': t['shares'],
            'price': t['price'],
            'value': t['shares'] * t['price'],
            'commission': 0.0,
            'notes': t['notes'],
            'pnl': t['pnl']
        }
        for t in db_trades
    ]

if 'positions' not in st.session_state:
    st.session_state.positions = {}


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


def calculate_trade_statistics(trades: list) -> dict:
    """Calculate trade statistics."""
    if not trades:
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'total_pnl': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'profit_factor': 0,
            'largest_win': 0,
            'largest_loss': 0
        }

    # Filter trades with P&L (closed trades)
    closed_trades = [t for t in trades if t.get('pnl') is not None]

    if not closed_trades:
        return {
            'total_trades': len(trades),
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'total_pnl': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'profit_factor': 0,
            'largest_win': 0,
            'largest_loss': 0
        }

    pnls = [t['pnl'] for t in closed_trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    total_wins = sum(wins) if wins else 0
    total_losses = abs(sum(losses)) if losses else 0

    return {
        'total_trades': len(trades),
        'winning_trades': len(wins),
        'losing_trades': len(losses),
        'win_rate': len(wins) / len(closed_trades) if closed_trades else 0,
        'total_pnl': sum(pnls),
        'avg_win': np.mean(wins) if wins else 0,
        'avg_loss': np.mean(losses) if losses else 0,
        'profit_factor': total_wins / total_losses if total_losses > 0 else float('inf'),
        'largest_win': max(wins) if wins else 0,
        'largest_loss': min(losses) if losses else 0
    }


def update_positions(trades: list) -> dict:
    """Calculate current positions from trade history."""
    positions = {}

    for trade in sorted(trades, key=lambda x: x.get('date', '')):
        symbol = trade.get('symbol', '')
        trade_type = trade.get('type', '')
        quantity = trade.get('quantity', 0)
        price = trade.get('price', 0)

        if symbol not in positions:
            positions[symbol] = {
                'shares': 0,
                'cost': 0,
                'avg_cost': 0
            }

        if trade_type == 'BUY':
            # Add to position
            new_shares = positions[symbol]['shares'] + quantity
            new_cost = positions[symbol]['cost'] + (quantity * price)
            positions[symbol]['shares'] = new_shares
            positions[symbol]['cost'] = new_cost
            positions[symbol]['avg_cost'] = new_cost / new_shares if new_shares > 0 else 0

        elif trade_type == 'SELL':
            # Reduce position
            positions[symbol]['shares'] -= quantity
            if positions[symbol]['shares'] <= 0:
                positions[symbol] = {'shares': 0, 'cost': 0, 'avg_cost': 0}
            else:
                positions[symbol]['cost'] = positions[symbol]['shares'] * positions[symbol]['avg_cost']

    # Remove zero positions
    positions = {k: v for k, v in positions.items() if v['shares'] > 0}

    return positions


def plot_pnl_over_time(trades: list):
    """Plot cumulative P&L over time."""
    if not trades:
        return None

    # Sort by date
    sorted_trades = sorted(trades, key=lambda x: x.get('date', ''))

    # Calculate cumulative P&L
    dates = []
    cum_pnl = []
    running_pnl = 0

    for trade in sorted_trades:
        if trade.get('pnl') is not None:
            running_pnl += trade['pnl']
            dates.append(trade['date'])
            cum_pnl.append(running_pnl)

    if not dates:
        return None

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=dates,
        y=cum_pnl,
        mode='lines+markers',
        name='Cumulative P&L',
        line=dict(color=ACCENT, width=2)
    ))

    # Add zero line
    fig.add_hline(y=0, line_dash="dash", line_color=GRAY)

    fig.update_layout(
        title='Cumulative P&L Over Time',
        xaxis_title='Date',
        yaxis_title='損益（元）',
        height=400
    )

    return fig


def plot_pnl_distribution(trades: list):
    """Plot P&L distribution."""
    pnls = [t.get('pnl', 0) for t in trades if t.get('pnl') is not None]

    if not pnls:
        return None

    fig = go.Figure()

    fig.add_trace(go.Histogram(
        x=pnls,
        nbinsx=20,
        name='P&L',
        marker_color=ACCENT
    ))

    # Add mean line
    mean_pnl = np.mean(pnls)
    fig.add_vline(x=mean_pnl, line_dash="dash", line_color=RED,
                  annotation_text=f"平均 {mean_pnl:,.0f}")

    fig.update_layout(
        title='P&L Distribution',
        xaxis_title='損益（元）',
        yaxis_title='Frequency',
        height=400
    )

    return fig


page_header("⑥ 執行與覆盤", "記錄每一筆交易，事後與當初的計畫比對。")
step_bar("journal")
_s0 = calculate_trade_statistics(st.session_state.get("trades", []))
if _s0["total_trades"]:
    _pf = f"{_s0['profit_factor']:.2f}" if _s0["profit_factor"] != float("inf") else "無虧損交易"
    key_points([
        f"共 <b>{_s0['total_trades']}</b> 筆已平倉交易，勝率 <b>{_s0['win_rate']:.1%}</b>，總損益 {_s0['total_pnl']:,.0f}。",
        f"平均獲利 {_s0['avg_win']:,.0f}、平均虧損 {_s0['avg_loss']:,.0f}，獲利因子 {_pf}。",
        "覆盤重點：實際虧損是否超過 ④ 設定的單筆風險？達標的交易，事前在 ③ 估的觸價機率是多少？",
    ])
else:
    key_points([
        "尚無交易紀錄。",
        "建議流程：下單前把 ③ 的觸價機率、④ 的停損價與股數寫進「備註」。",
        "賣出後回到這裡，比對實際結果與事前估計，這就是 CQF 期末專案需要的素材。",
    ])

# Trade entry form — prefilled from the workflow plan (③ target/stop/probabilities, ④ shares/entry)
st.subheader("記錄新交易")

_pl = _plan()
_sym0 = _pl.get("symbol") or get_symbol()
_qty0 = int(_pl.get("shares") or 0) or 100
_px0 = float(_pl.get("entry") or 100.0)
_fee0 = 0.0
try:
    from core.quant.costs import TWCostModel, is_tw_symbol
    if is_tw_symbol(_sym0):
        _fee0 = round(TWCostModel().commission(_qty0 * _px0), 0)
except Exception:
    pass
_note_parts = []
if _pl.get("target"):
    _note_parts.append(f"③ 目標 {_pl['target']:,.2f}（{_pl.get('horizon', '?')} 日內觸及機率 {_pl.get('p_target', 0):.0%}）"
                       f"、停損 {_pl.get('stop', 0):,.2f}（觸及機率 {_pl.get('p_stop', 0):.0%}）；σ {_pl.get('sigma', 0):.1%}")
if "shares" in _pl:
    _note_parts.append(f"④ {_pl.get('stop_mode', '')} {_pl.get('stop', 0):,.2f}、單筆風險 {_pl.get('risk_pct', 0):.2%}、"
                       + (f"建議 {_pl['shares']:,} 股、觸停損虧損約 {_pl.get('loss_at_stop', 0):,.0f}" if _pl["shares"]
                          else "建議 0 股（風險預算不足一個交易單位）"))
_notes0 = "；".join(_note_parts)
if _note_parts:
    st.info(f"已從決策流程帶入 {_sym0} 的計畫：股數、價格、手續費與備註。送出前可修改。")

with st.form(f"trade_form_{_sym0}_{_pl.get('updated', '')}", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)

    with col1:
        symbol = st.text_input("股票代碼", value=_sym0, placeholder="例如：2330 或 AAPL").strip().upper()
        trade_type = st.selectbox("交易類型", ["買入 (Buy)", "賣出 (Sell)"])

    with col2:
        quantity = st.number_input("股數", min_value=1, value=_qty0)
        price = st.number_input("價格", min_value=0.01, value=_px0, format="%.2f")

    with col3:
        trade_date = st.date_input("日期", value=datetime.now())
        commission = st.number_input("手續費", min_value=0.0, value=float(_fee0), format="%.2f")

    notes = st.text_area("備註", value=_notes0, placeholder="交易理由、事前估計…")

    col1, col2 = st.columns([1, 3])
    with col1:
        submitted = st.form_submit_button("記錄交易", type="primary")

    if submitted:
        if symbol:
            # Determine trade type code for database
            trade_type_code = 'BUY' if trade_type == '買入 (Buy)' else 'SELL'

            # Calculate P&L for SELL trades
            pnl = None
            if trade_type == '賣出 (Sell)':
                positions = update_positions(st.session_state.trades)
                if symbol in positions and positions[symbol]['shares'] >= quantity:
                    avg_cost = positions[symbol]['avg_cost']
                    pnl = (price - avg_cost) * quantity - commission

            # Save to SQLite database
            trade_id = save_trade(
                symbol=symbol,
                trade_type=trade_type_code,
                shares=quantity,
                price=price,
                trade_date=trade_date.strftime('%Y-%m-%d'),
                notes=notes,
                pnl=pnl
            )

            # Create trade object for session state
            trade = {
                'id': trade_id,
                'date': trade_date.strftime('%Y-%m-%d'),
                'symbol': symbol,
                'type': trade_type,
                'quantity': quantity,
                'price': price,
                'value': quantity * price,
                'commission': commission,
                'notes': notes,
                'pnl': pnl
            }

            st.session_state.trades.append(trade)

            # Update positions
            st.session_state.positions = update_positions(st.session_state.trades)

            st.success(f"已記錄交易：{trade_type} {quantity} {symbol} @ {money(price, symbol)}")

            # Get current price for position update
            dm = get_data_manager()
            if dm and symbol in st.session_state.positions:
                try:
                    quote = dm.fetch_quote(symbol)
                    if quote:
                        current_price = quote.get('current_price', quote.get('close', price))
                        pos = st.session_state.positions[symbol]
                        pos['current_price'] = current_price
                        pos['value'] = pos['shares'] * current_price
                        pos['pnl'] = pos['value'] - pos['cost']
                        pos['pnl_pct'] = (pos['pnl'] / pos['cost'] * 100) if pos['cost'] > 0 else 0
                except Exception:
                    pass
        else:
            st.error("請輸入股票代碼")

# Trade history
st.markdown("---")
st.subheader("交易歷史")

# Filter options
col1, col2, col3, col4 = st.columns(4)

with col1:
    filter_symbol = st.text_input("依股票篩選", key="filter_symbol")

with col2:
    filter_type = st.selectbox("依類型篩選", ["全部", "買入 (Buy)", "賣出 (Sell)"], key="filter_type")

with col3:
    filter_start = st.date_input("起始日期", value=datetime.now() - timedelta(days=365), key="filter_start")

with col4:
    filter_end = st.date_input("結束日期", value=datetime.now(), key="filter_end")

# Apply filters
filtered_trades = st.session_state.trades.copy()

if filter_symbol:
    filtered_trades = [t for t in filtered_trades if filter_symbol.upper() in t.get('symbol', '')]

if filter_type != "全部":
    filtered_trades = [t for t in filtered_trades if t.get('type') == filter_type]

filtered_trades = [t for t in filtered_trades
                   if filter_start.strftime('%Y-%m-%d') <= t.get('date', '') <= filter_end.strftime('%Y-%m-%d')]

# Display trades
if filtered_trades:
    # Sort by date descending
    sorted_trades = sorted(filtered_trades, key=lambda x: x.get('date', ''), reverse=True)

    # Create display dataframe
    display_data = []
    for trade in sorted_trades:
        display_data.append({
            '編號': trade.get('id', ''),
            '日期': trade.get('date', ''),
            '股票代碼': trade.get('symbol', ''),
            '類型': trade.get('type', ''),
            '股數': trade.get('quantity', 0),
            '價格': money(trade.get('price', 0), trade.get('symbol')),
            '金額': money(trade.get('value', 0), trade.get('symbol')),
            '手續費': money(trade.get('commission', 0), trade.get('symbol')),
            '損益': money(trade.get('pnl', 0), trade.get('symbol')) if trade.get('pnl') is not None else '-',
            '備註': trade.get('notes', '')[:30] + '...' if len(trade.get('notes', '')) > 30 else trade.get('notes', '')
        })

    trades_df = pd.DataFrame(display_data)
    st.dataframe(trades_df, width="stretch", hide_index=True)

    # Delete trade option
    col1, col2 = st.columns([3, 1])
    with col1:
        trade_ids = [t['id'] for t in filtered_trades]
        delete_id = st.selectbox("選擇要刪除的交易", trade_ids, key="delete_select")
    with col2:
        st.write("")  # Spacing
        st.write("")  # Spacing
        if st.button("刪除交易", type="secondary"):
            # Delete from SQLite database
            delete_trade(delete_id)
            # Delete from session state
            st.session_state.trades = [t for t in st.session_state.trades if t.get('id') != delete_id]
            st.session_state.positions = update_positions(st.session_state.trades)
            st.rerun()

else:
    st.info("尚未記錄任何交易。使用上面的表單添加交易。")

# Export section
st.markdown("---")
st.subheader("匯出")

col1, col2, col3 = st.columns(3)

with col1:
    if st.session_state.trades:
        # Export to CSV
        trades_df = pd.DataFrame(st.session_state.trades)
        csv = trades_df.to_csv(index=False)
        st.download_button(
            "匯出為 CSV",
            data=csv,
            file_name=f"trades_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.button("匯出為 CSV", disabled=True)

with col2:
    if st.session_state.trades:
        # Export to Excel
        trades_df = pd.DataFrame(st.session_state.trades)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            trades_df.to_excel(writer, index=False, sheet_name='Trades')
        excel_data = output.getvalue()
        st.download_button(
            "匯出為 Excel",
            data=excel_data,
            file_name=f"trades_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.button("匯出為 Excel", disabled=True)

with col3:
    # Import trades
    uploaded_file = st.file_uploader("從 CSV 匯入", type=['csv'], key="import_csv")
    if uploaded_file is not None:
        try:
            imported_df = pd.read_csv(uploaded_file)
            imported_trades = imported_df.to_dict('records')

            # Save each imported trade to SQLite
            for trade in imported_trades:
                # Extract and normalize data
                symbol = str(trade.get('symbol', '')).upper()
                trade_type = trade.get('type', '')
                quantity = float(trade.get('quantity', 0))
                price = float(trade.get('price', 0))
                trade_date = str(trade.get('date', datetime.now().strftime('%Y-%m-%d')))
                notes = str(trade.get('notes', ''))
                pnl = trade.get('pnl', None)
                if pnl is not None and pnl != '':
                    pnl = float(pnl)
                else:
                    pnl = None

                # Convert type to code
                trade_type_code = 'BUY' if '買' in trade_type else 'SELL'

                # Save to SQLite
                save_trade(
                    symbol=symbol,
                    trade_type=trade_type_code,
                    shares=quantity,
                    price=price,
                    trade_date=trade_date,
                    notes=notes,
                    pnl=pnl
                )

            st.session_state.trades.extend(imported_trades)
            st.session_state.positions = update_positions(st.session_state.trades)
            st.success(f"已匯入 {len(imported_trades)} 筆交易")
        except Exception as e:
            st.error(f"匯入失敗：{e}")

# Trade statistics
st.markdown("---")
st.subheader("交易統計")

stats = calculate_trade_statistics(st.session_state.trades)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("總交易數", stats['total_trades'])
    st.metric("獲利交易數", stats['winning_trades'])

with col2:
    st.metric("勝率 (Win Rate)", f"{stats['win_rate']:.1%}")
    st.metric("虧損交易數", stats['losing_trades'])

with col3:
    st.metric("總損益 (P&L)", money(stats['total_pnl'], [t.get('symbol') for t in st.session_state.trades]))
    st.metric("平均獲利", money(stats['avg_win'], [t.get('symbol') for t in st.session_state.trades]))

with col4:
    pf_display = f"{stats['profit_factor']:.2f}" if stats['profit_factor'] != float('inf') else "N/A"
    st.metric("獲利因子 (Profit Factor)", pf_display)
    st.metric("平均虧損", money(stats['avg_loss'], [t.get('symbol') for t in st.session_state.trades]))

# P&L charts
if st.session_state.trades:
    st.markdown("---")
    st.subheader("損益分析")

    col1, col2 = st.columns(2)

    with col1:
        fig = plot_pnl_over_time(st.session_state.trades)
        if fig:
            chart(fig)
        else:
            st.info("無已平倉交易的損益可顯示")

    with col2:
        fig = plot_pnl_distribution(st.session_state.trades)
        if fig:
            chart(fig)
        else:
            st.info("無已平倉交易的損益可顯示")

# Current positions summary
if st.session_state.positions:
    st.markdown("---")
    st.subheader("當前部位（來自交易紀錄）")

    positions_data = []
    for symbol, pos in st.session_state.positions.items():
        positions_data.append({
            '股票代碼': symbol,
            '股數': pos.get('shares', 0),
            '平均成本': money(pos.get('avg_cost', 0), symbol),
            '總成本': money(pos.get('cost', 0), symbol),
            '目前價格': money(pos.get('current_price', 0), symbol) if pos.get('current_price') else '-',
            '部位價值': money(pos.get('value', 0), symbol) if pos.get('value') else '-',
            '損益': money(pos.get('pnl', 0), symbol) if pos.get('pnl') else '-'
        })

    positions_df = pd.DataFrame(positions_data)
    st.dataframe(positions_df, width="stretch", hide_index=True)

# Data persistence notice
st.markdown("---")
st.caption("資料已自動儲存至本地資料庫。即使刷新瀏覽器，所有交易紀錄也會保留。")

next_step("journal")
