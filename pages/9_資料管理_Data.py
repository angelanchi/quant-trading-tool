# -*- coding: utf-8 -*-
"""
Data Management Page

Features:
- Stock search and quote display
- Historical data download
- Watchlist management
- Price charts with candlestick
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


from views._shared import (chart, money, page_header, key_points, ACCENT, ACCENT2, GRAY, LIGHT,  # house style
                           RED, GREEN, UP, DOWN)

# Initialize session state
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = []
if 'price_data' not in st.session_state:
    st.session_state.price_data = {}


def get_data_manager():
    """Get or create DataManager instance."""
    if 'data_manager' not in st.session_state:
        try:
            from core import DataManager
            st.session_state.data_manager = DataManager()
        except Exception as e:
            st.error(f"初始化 DataManager 失敗: {e}")
            return None
    return st.session_state.data_manager


def plot_candlestick(df: pd.DataFrame, symbol: str):
    """Create candlestick chart with volume."""
    fig = go.Figure()

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='股價'
    ))

    # Volume bars
    colors = [DOWN if row['close'] < row['open'] else UP
              for _, row in df.iterrows()]

    fig.add_trace(go.Bar(
        x=df.index,
        y=df['volume'],
        name='成交量',
        marker_color=colors,
        opacity=0.3,
        yaxis='y2'
    ))

    # Layout
    fig.update_layout(
        title=f'{symbol} 股價圖表',
        yaxis_title='股價',
        yaxis2=dict(
            title='成交量',
            overlaying='y',
            side='right',
            showgrid=False
        ),
        xaxis_rangeslider_visible=False,
        height=500
    )

    return fig


page_header("資料管理", "搜尋、下載與快取歷史價格。")

# Stock search section
st.subheader("搜尋股票")

col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    symbol_input = st.text_input(
        "輸入股票代碼",
        placeholder="例如: 2330 (台灣) 或 AAPL (美國)",
        key="symbol_search"
    )

with col2:
    market = st.selectbox(
        "市場",
        ["自動偵測", "台灣", "美國"],
        key="market_select"
    )

with col3:
    st.write("")  # Spacing
    st.write("")  # Spacing
    search_button = st.button("搜尋", type="primary")

# Search and display quote
if search_button and symbol_input:
    dm = get_data_manager()
    if dm:
        with st.spinner(f"正在取得 {symbol_input} 的行情資料..."):
            try:
                quote = dm.fetch_quote(symbol_input.upper())
                if quote:
                    # Display quote information
                    st.success(f"找到: {symbol_input.upper()}")

                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        price = quote.get('current_price', quote.get('close', 'N/A'))
                        st.metric("目前股價", money(price, symbol_input.upper()) if isinstance(price, (int, float)) else price)

                    with col2:
                        change = quote.get('change', 0)
                        change_pct = quote.get('change_percent', 0)
                        st.metric("漲跌", money(change, symbol_input.upper()) if isinstance(change, (int, float)) else "N/A",
                                  delta=f"{change_pct:.2f}%" if isinstance(change_pct, (int, float)) else None, delta_color="inverse")

                    with col3:
                        high = quote.get('high', 'N/A')
                        st.metric("最高", money(high, symbol_input.upper()) if isinstance(high, (int, float)) else high)

                    with col4:
                        low = quote.get('low', 'N/A')
                        st.metric("最低", money(low, symbol_input.upper()) if isinstance(low, (int, float)) else low)

                    # Add to watchlist button
                    if st.button(f"加入 {symbol_input.upper()} 到監控清單"):
                        if symbol_input.upper() not in st.session_state.watchlist:
                            st.session_state.watchlist.append(symbol_input.upper())
                            st.success(f"已加入 {symbol_input.upper()} 到監控清單")
                        else:
                            st.warning(f"{symbol_input.upper()} 已在監控清單中")
                else:
                    st.warning(f"找不到 {symbol_input} 的行情資料")
            except Exception as e:
                st.error(f"取得行情資料出錯: {e}")

st.markdown("---")

# Historical data download section
st.subheader("下載歷史資料")

col1, col2, col3 = st.columns(3)

with col1:
    download_symbol = st.text_input(
        "股票代碼",
        value=symbol_input if symbol_input else "",
        key="download_symbol"
    )

with col2:
    start_date = st.date_input(
        "開始日期",
        value=datetime.now() - timedelta(days=365),
        key="start_date"
    )

with col3:
    end_date = st.date_input(
        "結束日期",
        value=datetime.now(),
        key="end_date"
    )

if st.button("下載資料", type="primary"):
    if download_symbol:
        dm = get_data_manager()
        if dm:
            with st.spinner(f"正在下載 {download_symbol} 的資料..."):
                try:
                    df = dm.fetch_ohlcv(
                        download_symbol.upper(),
                        start_date.strftime('%Y-%m-%d'),
                        end_date.strftime('%Y-%m-%d')
                    )
                    if df is not None and not df.empty:
                        st.session_state.price_data[download_symbol.upper()] = df
                        st.success(f"已下載 {len(df)} 筆 {download_symbol.upper()} 的資料")

                        # Show chart
                        fig = plot_candlestick(df, download_symbol.upper())
                        chart(fig)

                        # Show data preview
                        with st.expander("資料預覽"):
                            st.dataframe(df.tail(20))

                        # Download as CSV
                        csv = df.to_csv()
                        st.download_button(
                            "匯出為 CSV",
                            data=csv,
                            file_name=f"{download_symbol}_{start_date}_{end_date}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.warning(f"找不到 {download_symbol} 的資料")
                except Exception as e:
                    st.error(f"下載資料出錯: {e}")
    else:
        st.warning("請輸入股票代碼")

st.markdown("---")

# Watchlist section
st.subheader("監控清單")

if st.session_state.watchlist:
    # Display watchlist in a table
    watchlist_data = []
    dm = get_data_manager()

    for symbol in st.session_state.watchlist:
        row = {'Symbol': symbol, 'Price': '-', 'Change': '-'}
        if dm:
            try:
                quote = dm.fetch_quote(symbol)
                if quote:
                    price = quote.get('current_price', quote.get('close', '-'))
                    change = quote.get('change_percent', '-')
                    row['Price'] = money(price, symbol) if isinstance(price, (int, float)) else '-'
                    row['Change'] = f"{change:.2f}%" if isinstance(change, (int, float)) else '-'
            except Exception:
                pass
        watchlist_data.append(row)

    watchlist_df = pd.DataFrame(watchlist_data)
    st.dataframe(watchlist_df, width="stretch", hide_index=True)

    # Remove from watchlist
    col1, col2 = st.columns([3, 1])
    with col1:
        remove_symbol = st.selectbox(
            "選擇要移除的股票代碼",
            st.session_state.watchlist,
            key="remove_select"
        )
    with col2:
        st.write("")  # Spacing
        st.write("")  # Spacing
        if st.button("移除"):
            st.session_state.watchlist.remove(remove_symbol)
            st.rerun()
else:
    st.info("監控清單中無股票。請在上方搜尋並加入股票。")

st.markdown("---")

# Batch download section
st.subheader("批次下載")

if st.session_state.watchlist:
    selected_stocks = st.multiselect(
        "選擇要下載的股票",
        st.session_state.watchlist,
        default=st.session_state.watchlist
    )

    col1, col2 = st.columns(2)
    with col1:
        batch_start = st.date_input(
            "開始日期",
            value=datetime.now() - timedelta(days=365),
            key="batch_start"
        )
    with col2:
        batch_end = st.date_input(
            "結束日期",
            value=datetime.now(),
            key="batch_end"
        )

    if st.button("下載全部已選項目", type="primary"):
        if selected_stocks:
            dm = get_data_manager()
            if dm:
                progress_bar = st.progress(0)
                for i, symbol in enumerate(selected_stocks):
                    with st.spinner(f"正在下載 {symbol}..."):
                        try:
                            df = dm.fetch_ohlcv(
                                symbol,
                                batch_start.strftime('%Y-%m-%d'),
                                batch_end.strftime('%Y-%m-%d')
                            )
                            if df is not None and not df.empty:
                                st.session_state.price_data[symbol] = df
                                st.success(f"已下載 {len(df)} 筆 {symbol} 的資料")
                        except Exception as e:
                            st.error(f"下載 {symbol} 失敗: {e}")
                    progress_bar.progress((i + 1) / len(selected_stocks))
                st.success("批次下載已完成!")
        else:
            st.warning("請至少選擇一支股票")
else:
    st.info("請先在監控清單中加入股票，然後才能使用批次下載功能。")

# Show cached data
if st.session_state.price_data:
    st.markdown("---")
    st.subheader("已快取資料")
    cached_symbols = list(st.session_state.price_data.keys())
    selected_cached = st.selectbox("檢視已快取資料", cached_symbols)

    if selected_cached:
        df = st.session_state.price_data[selected_cached]
        fig = plot_candlestick(df, selected_cached)
        chart(fig)

        with st.expander("資料預覽"):
            st.dataframe(df.tail(20))
