# -*- coding: utf-8 -*-
"""
個股深入分析 (Stock Deep Analysis)

一頁搞定一檔股票的所有資訊：
- K 線圖 + 技術指標（MA、RSI、MACD、布林帶）
- 風險指標卡片（Sharpe、VaR、MDD）
- 基本面數據（財報比率、月營收）
- 相關新聞 + 大幅波動事件
- 快捷操作列（跳轉回測、投組、警報）

設計理念：
    在觀察清單選好一檔股票後，跳到這一頁做完整分析，
    然後再根據分析結果決定要「回測策略」「加入投組」還是「設定警報」。
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys
import logging

sys.path.insert(0, str(Path(__file__).parent.parent))
logger = logging.getLogger(__name__)


from views._shared import (chart, money, page_header, key_points, ACCENT, ACCENT2, GRAY, LIGHT,  # house style
                           RED, GREEN, UP, DOWN)

# =============================================================================
# Cached Resources
# =============================================================================
@st.cache_resource
def get_data_manager():
    try:
        from core.data_fetcher import DataManager
        return DataManager()
    except Exception as e:
        logger.warning(f"DataManager init failed: {e}")
        return None


@st.cache_resource
def get_context_engine():
    try:
        from core.context_engine import ContextEngine
        return ContextEngine()
    except Exception:
        return None


@st.cache_resource
def get_financial_manager():
    try:
        from core.financial_reports import FinancialReportManager
        return FinancialReportManager()
    except Exception:
        return None


@st.cache_resource
def get_news_manager():
    try:
        from core.news_fetcher import NewsManager
        return NewsManager()
    except Exception:
        return None


# =============================================================================
# Helper Functions (from original Watchlist, kept here for self-containedness)
# =============================================================================
def _is_tw(symbol: str) -> bool:
    clean = symbol.strip().replace(".TW", "").replace(".TWO", "")
    return clean.isdigit() and len(clean) in (4, 5)


def fetch_prices(dm, symbol: str, start: str, end: str):
    if dm is None:
        return None
    try:
        df = dm.fetch_prices(symbol, start, end)
        return df if df is not None and not df.empty else None
    except Exception as e:
        logger.warning(f"Price fetch failed {symbol}: {e}")
        return None


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    close = df["close"] if "close" in df.columns else df["Close"]
    df["MA5"] = close.rolling(5).mean()
    df["MA20"] = close.rolling(20).mean()
    df["MA60"] = close.rolling(60).mean()

    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_hist"] = df["MACD"] - df["MACD_signal"]

    df["BB_mid"] = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    df["BB_upper"] = df["BB_mid"] + 2 * bb_std
    df["BB_lower"] = df["BB_mid"] - 2 * bb_std
    return df


def compute_risk_metrics(df: pd.DataFrame) -> dict:
    close = df["close"] if "close" in df.columns else df["Close"]
    returns = close.pct_change().dropna()
    if len(returns) < 10:
        return {}
    total_return = (close.iloc[-1] / close.iloc[0] - 1) * 100
    ann_return = ((1 + total_return / 100) ** (252 / len(returns)) - 1) * 100
    volatility = returns.std() * np.sqrt(252) * 100
    sharpe = (ann_return - 2) / volatility if volatility > 0 else 0
    var_95 = np.percentile(returns, 5) * 100
    cvar_95 = returns[returns <= np.percentile(returns, 5)].mean() * 100
    cummax = close.cummax()
    max_dd = ((close - cummax) / cummax).min() * 100
    return {
        "總報酬": f"{total_return:.1f}%",
        "年化報酬": f"{ann_return:.1f}%",
        "波動率": f"{volatility:.1f}%",
        "Sharpe": f"{sharpe:.2f}",
        "VaR 95%": f"{var_95:.2f}%",
        "CVaR": f"{cvar_95:.2f}%",
        "最大回撤": f"{max_dd:.1f}%",
    }


def detect_big_moves(df: pd.DataFrame, threshold: float = 2.0) -> pd.DataFrame:
    close = df["close"] if "close" in df.columns else df["Close"]
    returns = close.pct_change()
    mean_r = returns.rolling(20).mean()
    std_r = returns.rolling(20).std()
    zscore = (returns - mean_r) / std_r.replace(0, np.nan)
    big = df[zscore.abs() > threshold].copy()
    big["漲跌%"] = (returns[big.index] * 100).round(2)
    big["Z-score"] = zscore[big.index].round(2)
    big["類型"] = big["漲跌%"].apply(lambda x: "大漲" if x > 0 else "大跌")
    return big


def plot_candlestick(df, symbol, show_ma, show_bb, big_moves=None):
    o = df["open"] if "open" in df.columns else df["Open"]
    h = df["high"] if "high" in df.columns else df["High"]
    lo = df["low"] if "low" in df.columns else df["Low"]
    c = df["close"] if "close" in df.columns else df["Close"]
    v = df["volume"] if "volume" in df.columns else df.get("Volume", pd.Series(0, index=df.index))

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03,
        row_heights=[0.55, 0.25, 0.20],
        subplot_titles=[f"{symbol} K 線圖", "RSI (14)", "MACD"],
    )

    fig.add_trace(go.Candlestick(x=df.index, open=o, high=h, low=lo, close=c, name="K線"), row=1, col=1)

    if show_ma:
        for ma, color in [("MA5", ACCENT2), ("MA20", ACCENT), ("MA60", GRAY)]:
            if ma in df.columns:
                fig.add_trace(go.Scatter(x=df.index, y=df[ma], name=ma, line=dict(width=1, color=color)), row=1, col=1)

    if show_bb and "BB_upper" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["BB_upper"], name="BB上", line=dict(width=1, dash="dash", color=GRAY)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["BB_lower"], name="BB下", line=dict(width=1, dash="dash", color=GRAY), fill="tonexty", fillcolor="rgba(128,128,128,0.1)"), row=1, col=1)

    if big_moves is not None and not big_moves.empty:
        bm_close = big_moves["close"] if "close" in big_moves.columns else big_moves["Close"]
        colors = [DOWN if t == "大跌" else UP for t in big_moves["類型"]]
        texts = [f"{row['類型']} {row['漲跌%']:+.1f}%" for _, row in big_moves.iterrows()]
        fig.add_trace(go.Scatter(x=big_moves.index, y=bm_close, mode="markers+text", name="大波動",
                                 marker=dict(size=10, color=colors, symbol="diamond"),
                                 text=texts, textposition="top center", textfont=dict(size=9)), row=1, col=1)

    if "RSI" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI", line=dict(color=ACCENT)), row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color=RED, opacity=0.5, row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color=GREEN, opacity=0.5, row=2, col=1)

    if "MACD" in df.columns:
        colors_hist = [UP if v >= 0 else DOWN for v in df["MACD_hist"].fillna(0)]
        fig.add_trace(go.Bar(x=df.index, y=df["MACD_hist"], name="MACD柱", marker_color=colors_hist), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], name="MACD", line=dict(width=1, color=ACCENT)), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["MACD_signal"], name="Signal", line=dict(width=1, color=ACCENT2)), row=3, col=1)

    fig.update_layout(height=700, xaxis_rangeslider_visible=False, showlegend=True,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig


def fetch_news_safe(symbol: str) -> list:
    news_items = []
    try:
        import yfinance as yf
        # 台股：先試 .TW（上市），失敗再試 .TWO（上櫃）
        candidates = [f"{symbol}.TW", f"{symbol}.TWO"] if _is_tw(symbol) else [symbol]
        ticker = None
        for yf_sym in candidates:
            t = yf.Ticker(yf_sym)
            if t.news:
                ticker = t
                break
        if ticker is None:
            ticker = yf.Ticker(candidates[0])
        for item in (ticker.news or [])[:10]:
            content = item.get("content", {})
            title = content.get("title", item.get("title", ""))
            canonical = content.get("canonicalUrl", {})
            link = canonical.get("url", "") if isinstance(canonical, dict) else ""
            pub_date = content.get("pubDate", item.get("providerPublishTime", ""))
            provider = content.get("provider", {})
            source = provider.get("displayName", "") if isinstance(provider, dict) else str(provider)
            if title:
                news_items.append({"title": title, "link": link, "date": pub_date, "source": source})
    except Exception as e:
        logger.warning(f"yfinance news failed for {symbol}: {e}")
    if not news_items:
        try:
            import finnhub, os
            api_key = os.getenv("FINNHUB_API_KEY")
            if api_key:
                client = finnhub.Client(api_key=api_key)
                end = datetime.now()
                start = end - timedelta(days=7)
                for item in (client.company_news(symbol, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")) or [])[:10]:
                    news_items.append({
                        "title": item.get("headline", ""), "link": item.get("url", ""),
                        "date": datetime.fromtimestamp(item.get("datetime", 0)).strftime("%Y-%m-%d %H:%M") if item.get("datetime") else "",
                        "source": item.get("source", ""),
                    })
        except Exception:
            pass
    return news_items


# =============================================================================
# Load symbol list from watchlists.json
# =============================================================================
def load_all_symbols() -> dict:
    wl_path = Path(__file__).parent.parent / "config" / "watchlists.json"
    try:
        with open(wl_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        symbols = {}
        for key, group in data.items():
            if key.startswith("_"):
                continue
            if isinstance(group, dict) and "symbols" in group:
                for sym, desc in group["symbols"].items():
                    symbols[sym] = desc
        return symbols
    except Exception:
        return {"2330": "台積電", "AAPL": "Apple"}


# =============================================================================
# Main Page
# =============================================================================
page_header("個股分析", "單一標的的技術面、風險指標、基本面與新聞事件。")

# --- Get active stock from workflow or let user select ---
all_symbols = load_all_symbols()

_default_sym = None
try:
    from core.workflow import WorkflowState, render_action_bar
    _default_sym = WorkflowState.get_active_stock()
except Exception:
    pass

# Sidebar: stock selection + settings
with st.sidebar:
    st.subheader("分析設定")

    sym_list = list(all_symbols.keys())
    default_idx = 0
    if _default_sym and _default_sym in sym_list:
        default_idx = sym_list.index(_default_sym)

    symbol = st.selectbox(
        "股票代碼",
        options=sym_list,
        index=default_idx,
        format_func=lambda s: f"{s} — {all_symbols.get(s, '')[:20]}",
    )

    # Update workflow state
    try:
        WorkflowState.set_active_stock(symbol, all_symbols.get(symbol, ""))
    except Exception:
        pass

    st.markdown("---")

    period_options = {"3 個月": 90, "6 個月": 180, "1 年": 365, "2 年": 730}
    period_label = st.selectbox("時間範圍", list(period_options.keys()), index=2)
    days = period_options[period_label]

    show_ma = st.checkbox("移動平均線", value=True)
    show_bb = st.checkbox("布林通道", value=False)

    st.markdown("---")
    st.caption("分析完後，用底部的快捷列跳轉到回測或投組")


# --- Header ---
desc = all_symbols.get(symbol, "")
st.subheader(f"{symbol}　{desc}")

end_date = datetime.now()
start_date = end_date - timedelta(days=days)

# =============================================================================
# Tab layout: 技術面 / 基本面 / 新聞事件
# =============================================================================
tab_tech, tab_fund, tab_news = st.tabs([
    "技術分析",
    "基本面",
    "新聞與事件",
])

dm = get_data_manager()
price_data = fetch_prices(dm, symbol, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))


# =============================================================================
# Tab 1: 技術分析
# =============================================================================
with tab_tech:
    if price_data is not None and not price_data.empty:
        price_data = compute_indicators(price_data)

        # Risk metrics bar
        risk = compute_risk_metrics(price_data)
        if risk:
            cols = st.columns(len(risk))
            for i, (label, value) in enumerate(risk.items()):
                cols[i].metric(label, value)
            st.markdown("---")

        # K-line chart
        big_moves = detect_big_moves(price_data)
        fig = plot_candlestick(price_data, symbol, show_ma, show_bb, big_moves=big_moves)
        chart(fig)

        # Big moves table
        if not big_moves.empty:
            with st.expander(f"大幅波動事件 ({len(big_moves)} 筆)", expanded=False):
                display_cols = ["漲跌%", "Z-score", "類型"]
                avail = [c for c in display_cols if c in big_moves.columns]
                st.dataframe(big_moves[avail].sort_index(ascending=False), width="stretch")
    else:
        st.warning(f"無法取得 {symbol} 的價格資料。請確認代碼正確且 DataManager 已初始化。")


# =============================================================================
# Tab 2: 基本面
# =============================================================================
with tab_fund:
    engine = get_context_engine()
    fm = get_financial_manager()

    if engine:
        try:
            with st.spinner("取得基本面資料..."):
                card = engine.get_context_card(symbol)

            ratios = card.get("key_ratios", {})

            if ratios:
                if not _is_tw(symbol):
                    # US stock fundamentals
                    cols = st.columns(6)
                    metrics = [
                        ("P/E", ratios.get("pe_ratio"), ".1f"),
                        ("P/B", ratios.get("pb_ratio"), ".1f"),
                        ("ROE", ratios.get("roe"), ".1%"),
                        ("淨利率", ratios.get("profit_margin"), ".1%"),
                        ("D/E", ratios.get("debt_to_equity"), ".0f"),
                        ("分析師", ratios.get("recommendation", "—"), "s"),
                    ]
                    for i, (label, val, fmt) in enumerate(metrics):
                        with cols[i]:
                            if val is not None and fmt != "s":
                                st.metric(label, f"{val:{fmt}}")
                            else:
                                st.metric(label, str(val).upper() if val else "—")

                    target = ratios.get("target_mean_price")
                    if target:
                        low = ratios.get("target_low_price", "?")
                        high = ratios.get("target_high_price", "?")
                        n = ratios.get("number_of_analysts", "?")
                        st.caption(f"目標價: {money(low, symbol, 0)} → **{money(target, symbol, 0)}** → {money(high, symbol, 0)}　({n} 位分析師)")

                    rev_g = ratios.get("revenue_growth")
                    earn_g = ratios.get("earnings_growth")
                    if rev_g or earn_g:
                        g1, g2 = st.columns(2)
                        with g1:
                            if rev_g:
                                st.metric("營收成長", f"{rev_g:.1%}")
                        with g2:
                            if earn_g:
                                st.metric("盈餘成長", f"{earn_g:.1%}")
                else:
                    # Taiwan stock: monthly revenue
                    rev_data = card.get("monthly_revenue")
                    if rev_data:
                        r1, r2, r3 = st.columns(3)
                        with r1:
                            st.metric("最新月營收", f"{rev_data.get('revenue', 0):,.0f}")
                        with r2:
                            yoy = rev_data.get("yoy", 0)
                            st.metric("年增率 YoY", f"{yoy:+.1f}%", delta=f"{yoy:+.1f}%", delta_color="inverse")
                        with r3:
                            mom = rev_data.get("mom", 0)
                            st.metric("月增率 MoM", f"{mom:+.1f}%", delta=f"{mom:+.1f}%", delta_color="inverse")

            # Macro snapshot
            macro = card.get("macro_snapshot", {})
            if macro:
                st.markdown("---")
                st.write("**總經環境：**")
                m_cols = st.columns(3)
                with m_cols[0]:
                    fed = macro.get("fed_rate")
                    st.metric("聯邦利率", f"{fed:.2f}%" if fed else "—")
                with m_cols[1]:
                    cpi = macro.get("cpi")
                    st.metric("CPI", f"{cpi:.1f}" if cpi else "—")
                with m_cols[2]:
                    vix = macro.get("vix")
                    st.metric("VIX", f"{vix:.1f}" if vix else "—")

        except Exception as e:
            st.warning(f"基本面資料取得失敗: {e}")
    else:
        st.info("ContextEngine 未初始化。請確認相關模組已安裝。")

    # Sector info
    st.markdown("---")
    st.write("**所屬產業：**")
    try:
        from core.sector_analysis import SectorMap
        sm = SectorMap()
        sector = sm.find_sector_by_symbol(symbol)
        if sector:
            st.write(f"**{sector.name}** ({sector.name_en}) — {sector.description}")
            peers = [s for s in sector.symbols.keys() if s != symbol][:5]
            if peers:
                st.caption(f"同業: {', '.join(peers)}")
        else:
            st.caption("此股票不在已定義的產業分類中")
    except Exception:
        st.caption("產業分類模組未載入")


# =============================================================================
# Tab 3: 新聞與事件
# =============================================================================
with tab_news:
    col_news, col_events = st.columns([3, 2])

    with col_news:
        st.write("**相關新聞**")
        with st.spinner("載入新聞中..."):
            news = fetch_news_safe(symbol)

        if news:
            for item in news[:8]:
                title = item.get("title", "")
                link = item.get("link", "")
                source = item.get("source", "")
                if link:
                    st.markdown(f"- [{title}]({link})　*{source}*")
                else:
                    st.write(f"- {title}　*{source}*")
        else:
            st.info("暫無相關新聞")

    with col_events:
        st.write("**大幅波動事件**")
        if price_data is not None:
            bm = detect_big_moves(price_data)
            if not bm.empty:
                for idx, row in bm.sort_index(ascending=False).head(10).iterrows():
                    icon = "▲" if row["類型"] == "大漲" else "▼"
                    date_str = idx.strftime("%m/%d") if hasattr(idx, "strftime") else str(idx)[:10]
                    st.write(f"{icon} **{date_str}** {row['漲跌%']:+.1f}% (Z={row['Z-score']:.1f})")
            else:
                st.info("期間內無大幅波動事件")


# =============================================================================
# Quick Action Bar — jump to related pages
# =============================================================================
st.divider()
st.write(f"**{symbol} — 下一步：**")
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    if st.button("回測策略", width="stretch", key="goto_bt"):
        st.switch_page("pages/4_策略回測_Backtesting.py")
with col2:
    if st.button("加入投組", width="stretch", key="goto_pf"):
        st.switch_page("pages/5_投資組合_Portfolio.py")
with col3:
    if st.button("風險分析", width="stretch", key="goto_risk"):
        st.switch_page("pages/6_風險分析_Risk.py")
with col4:
    if st.button("產業分析", width="stretch", key="goto_sector"):
        st.switch_page("pages/1_產業分析_Sector.py")
with col5:
    if st.button("設定警報", width="stretch", key="goto_alert"):
        st.switch_page("pages/8_警報系統_Alerts.py")
