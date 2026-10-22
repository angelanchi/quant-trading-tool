# -*- coding: utf-8 -*-
"""
基本面與時事整合頁面 (Fundamental & News Context Page)

把財報、新聞、總經數據與股價變化整合在同一個頁面上，
讓你在看盤時能一眼看出「為什麼漲？為什麼跌？」

功能：
1. 股票背景卡片：關鍵比率 + 最新新聞 + 總經快照
2. 時間軸視圖：所有事件（財報、新聞、異常波動）按時間排列
3. 財報深入分析：三表數據 + 趨勢圖
4. 總經儀表板：主要經濟指標追蹤
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta, date
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(
    page_title="基本面與時事 — 量化交易工具",
    page_icon=None,
    layout="wide",
)

st.title("基本面與時事整合 (Fundamental & News Context)")
st.markdown("---")


# =============================================================================
# 初始化 Managers
# =============================================================================

@st.cache_resource
def get_financial_manager():
    """取得 FinancialReportManager（快取）。"""
    try:
        from core.financial_reports import FinancialReportManager
        return FinancialReportManager()
    except Exception as e:
        st.error(f"FinancialReportManager 初始化失敗: {e}")
        return None


@st.cache_resource
def get_news_manager():
    """取得 NewsManager（快取）。"""
    try:
        from core.news_fetcher import NewsManager
        return NewsManager()
    except Exception as e:
        st.error(f"NewsManager 初始化失敗: {e}")
        return None


@st.cache_resource
def get_context_engine():
    """取得 ContextEngine（快取）。"""
    try:
        from core.context_engine import ContextEngine
        return ContextEngine()
    except Exception as e:
        st.error(f"ContextEngine 初始化失敗: {e}")
        return None


@st.cache_resource
def get_data_manager():
    """取得 DataManager（快取）。"""
    try:
        from core.data_fetcher import DataManager
        return DataManager()
    except Exception as e:
        st.error(f"DataManager 初始化失敗: {e}")
        return None


# =============================================================================
# Sidebar: 股票選擇
# =============================================================================

with st.sidebar:
    st.subheader("設定 (Settings)")

    # Pre-fill from workflow state
    _default_sym = "AAPL"
    try:
        from core.workflow import WorkflowState
        _wf = WorkflowState.get_active_stock()
        if _wf:
            _default_sym = _wf
    except Exception:
        pass

    symbol = st.text_input(
        "股票代號 (Symbol)",
        value=_default_sym,
        help="台股輸入 4-5 位數字（如 2330），美股輸入代號（如 AAPL）"
    )

    days_back = st.slider("回溯天數 (Days Back)", 7, 365, 90)

    st.markdown("---")

    st.markdown("### 資料來源")
    include_news = st.checkbox("新聞 (News)", value=True)
    include_financials = st.checkbox("財報 (Financials)", value=True)
    include_macro = st.checkbox("總經數據 (Macro)", value=True)
    include_price_events = st.checkbox("價格異常偵測", value=True)

    st.markdown("---")

    # 判斷台股或美股
    clean_sym = symbol.upper().strip().replace('.TW', '').replace('.TWO', '')
    is_tw = clean_sym.isdigit() and len(clean_sym) in (4, 5)
    st.info(f"市場: {'台股 (TWSE)' if is_tw else '美股 (US)'}")


# =============================================================================
# Tab Layout
# =============================================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "背景卡片 (Context Card)",
    "時間軸 (Timeline)",
    "財報分析 (Financial Analysis)",
    "總經儀表板 (Macro Dashboard)",
])


# =============================================================================
# Tab 1: 背景卡片
# =============================================================================

with tab1:
    st.subheader(f"{symbol} 背景卡片 (Context Card)")

    if st.button("取得背景資料", key="fetch_card"):
        with st.spinner("取得資料中..."):
            engine = get_context_engine()
            if engine:
                card = engine.get_context_card(symbol)
                st.session_state['context_card'] = card

    if 'context_card' in st.session_state:
        card = st.session_state['context_card']

        # --- 關鍵比率 ---
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 關鍵財務比率")
            ratios = card.get('key_ratios', {})

            if ratios:
                if card.get('market') == 'US':
                    # 美股比率
                    r1, r2, r3 = st.columns(3)
                    with r1:
                        pe = ratios.get('pe_ratio')
                        st.metric("P/E Ratio", f"{pe:.1f}" if pe else "N/A")
                        roe = ratios.get('roe')
                        st.metric("ROE", f"{roe:.1%}" if roe else "N/A")
                    with r2:
                        pb = ratios.get('pb_ratio')
                        st.metric("P/B Ratio", f"{pb:.1f}" if pb else "N/A")
                        margin = ratios.get('profit_margin')
                        st.metric("Profit Margin", f"{margin:.1%}" if margin else "N/A")
                    with r3:
                        de = ratios.get('debt_to_equity')
                        st.metric("Debt/Equity", f"{de:.1f}" if de else "N/A")
                        rec = ratios.get('recommendation', 'N/A')
                        st.metric("Analyst", str(rec))

                    # 分析師目標價
                    target = ratios.get('target_mean_price')
                    if target:
                        st.markdown(
                            f"**分析師目標價** (Target Price): "
                            f"${ratios.get('target_low_price', 'N/A')} ~ "
                            f"${target:.0f} ~ "
                            f"${ratios.get('target_high_price', 'N/A')}"
                        )

                else:
                    # 台股比率
                    rev_info = ratios.get('latest_monthly_revenue')
                    if rev_info:
                        st.metric("最新月營收", f"{rev_info:,.0f}")
                    yoy = ratios.get('revenue_yoy')
                    if yoy:
                        st.metric("營收 YoY", f"{yoy:+.1f}%")
                    mom = ratios.get('revenue_mom')
                    if mom:
                        st.metric("營收 MoM", f"{mom:+.1f}%")
            else:
                st.info("無法取得財務比率資料")

        with col2:
            st.markdown("#### 最近新聞")
            news_list = card.get('recent_news', [])

            if news_list:
                for news in news_list[:5]:
                    headline = news.get('headline', '')
                    url = news.get('url', '')
                    source = news.get('source', '')
                    dt = news.get('datetime', '')

                    if url:
                        st.markdown(f"- [{headline}]({url})")
                    else:
                        st.markdown(f"- {headline}")
                    st.caption(f"   {source} | {dt[:10] if dt else ''}")
            else:
                st.info("暫無相關新聞")

        # --- 台股月營收 ---
        if card.get('monthly_revenue'):
            st.markdown("---")
            st.markdown("#### 最新月營收")
            rev = card['monthly_revenue']
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("營收", f"{rev.get('revenue', 0):,.0f}")
            with c2:
                yoy_val = rev.get('yoy', 0)
                st.metric("年增率 (YoY)", f"{yoy_val:+.1f}%",
                          delta=f"{yoy_val:+.1f}%")
            with c3:
                mom_val = rev.get('mom', 0)
                st.metric("月增率 (MoM)", f"{mom_val:+.1f}%",
                          delta=f"{mom_val:+.1f}%")

        # --- 總經快照 ---
        macro = card.get('macro_snapshot', {})
        if macro:
            st.markdown("---")
            st.markdown("#### 總經環境快照")
            cols = st.columns(len(macro))
            for i, (indicator, data) in enumerate(macro.items()):
                with cols[i]:
                    label_map = {
                        'FED_RATE': '聯邦基金利率',
                        'CPI': 'CPI',
                        'VIX': 'VIX 恐慌指數',
                        'US_10Y': '美國 10 年期公債殖利率',
                    }
                    st.metric(
                        label_map.get(indicator, indicator),
                        f"{data['value']:.2f}",
                    )
                    st.caption(f"更新: {data['date'][:10]}")


# =============================================================================
# Tab 2: 時間軸
# =============================================================================

with tab2:
    st.subheader(f"{symbol} 事件時間軸 (Event Timeline)")

    if st.button("建構時間軸", key="build_timeline"):
        with st.spinner("建構時間軸中（可能需要 30 秒）..."):
            engine = get_context_engine()
            if engine:
                timeline = engine.build_timeline(
                    symbol,
                    days_back=days_back,
                    include_news=include_news,
                    include_financials=include_financials,
                    include_macro=include_macro,
                    include_price_events=include_price_events,
                )
                st.session_state['timeline'] = timeline

    if 'timeline' in st.session_state:
        timeline = st.session_state['timeline']

        st.markdown(f"共 **{len(timeline.events)}** 個事件")

        # 重要度篩選
        min_importance = st.slider("最低重要度 (Min Importance)", 1, 5, 1)
        filtered_events = timeline.filter_by_importance(min_importance)

        # 類型篩選
        event_types = list(set(e.event_type.value for e in filtered_events))
        selected_types = st.multiselect(
            "篩選事件類型",
            event_types,
            default=event_types,
        )

        # 時間軸表格
        events_data = []
        for event in filtered_events:
            if event.event_type.value in selected_types:
                impact_emoji = {
                    'positive': '+',
                    'negative': '-',
                    'neutral': '=',
                }.get(event.impact, '?')

                events_data.append({
                    '日期': event.date.strftime('%Y-%m-%d') if isinstance(event.date, datetime) else str(event.date),
                    '類型': event.event_type.value,
                    '影響': impact_emoji,
                    '重要度': '*' * event.importance,
                    '標題': event.title,
                    '說明': event.description[:80] if event.description else '',
                    '來源': event.source,
                })

        if events_data:
            df_events = pd.DataFrame(events_data)
            st.dataframe(df_events, width="stretch", hide_index=True, height=500)

            # 匯出
            csv = df_events.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "匯出時間軸為 CSV",
                csv,
                file_name=f"{symbol}_timeline_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
        else:
            st.info("無符合條件的事件")

        # 價格 + 事件疊合圖
        if timeline.price_data is not None and not timeline.price_data.empty:
            st.markdown("---")
            st.markdown("#### 價格走勢 + 事件標記")

            price_df = timeline.price_data.copy()
            price_df['date'] = pd.to_datetime(price_df['date'])

            fig = go.Figure()

            # 股價線
            fig.add_trace(go.Scatter(
                x=price_df['date'],
                y=price_df['close'],
                mode='lines',
                name='收盤價',
                line=dict(color='#2196F3', width=2),
            ))

            # 事件標記
            color_map = {
                'positive': 'green',
                'negative': 'red',
                'neutral': 'gray',
            }

            for event in filtered_events:
                if event.event_type.value in selected_types:
                    # 找到最接近的股價
                    event_dt = pd.Timestamp(event.date)
                    closest_idx = (price_df['date'] - event_dt).abs().idxmin()
                    y_val = price_df.loc[closest_idx, 'close']

                    fig.add_trace(go.Scatter(
                        x=[event_dt],
                        y=[y_val],
                        mode='markers+text',
                        name=event.event_type.value,
                        marker=dict(
                            size=8 + event.importance * 2,
                            color=color_map.get(event.impact, 'gray'),
                            symbol='diamond',
                        ),
                        text=[event.title[:20]],
                        textposition='top center',
                        textfont=dict(size=8),
                        hovertext=f"{event.title}<br>{event.description[:60]}",
                        showlegend=False,
                    ))

            fig.update_layout(
                title=f'{symbol} 股價與事件時間軸',
                xaxis_title='日期',
                yaxis_title='價格',
                height=500,
                hovermode='closest',
            )

            st.plotly_chart(fig, width="stretch")


# =============================================================================
# Tab 3: 財報分析
# =============================================================================

with tab3:
    st.subheader(f"{symbol} 財報分析 (Financial Analysis)")

    fin_manager = get_financial_manager()

    if fin_manager:
        report_type = st.radio(
            "選擇報表",
            ["損益表 (Income)", "資產負債表 (Balance Sheet)", "現金流量表 (Cash Flow)"],
            horizontal=True,
        )

        if st.button("取得財報", key="fetch_financials"):
            with st.spinner("取得財報中..."):
                if "損益表" in report_type:
                    df = fin_manager.get_income_statement(symbol)
                elif "資產負債表" in report_type:
                    df = fin_manager.get_balance_sheet(symbol)
                else:
                    df = fin_manager.get_cash_flow(symbol)

                if not df.empty:
                    st.session_state['financial_data'] = df
                    st.success(f"取得 {len(df)} 筆資料")
                else:
                    st.warning("無法取得資料，請確認股票代號是否正確")

        if 'financial_data' in st.session_state:
            df = st.session_state['financial_data']
            st.dataframe(df, width="stretch", hide_index=True, height=400)

            # 匯出
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "匯出財報為 CSV",
                csv,
                file_name=f"{symbol}_financial_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )

        # 台股月營收趨勢圖
        if is_tw:
            st.markdown("---")
            st.markdown("#### 月營收趨勢 (Monthly Revenue Trend)")

            if st.button("取得月營收", key="fetch_revenue"):
                with st.spinner("取得月營收中..."):
                    rev_df = fin_manager.get_monthly_revenue(symbol)
                    if not rev_df.empty:
                        st.session_state['revenue_data'] = rev_df

            if 'revenue_data' in st.session_state:
                rev_df = st.session_state['revenue_data']

                if 'revenue' in rev_df.columns:
                    fig = go.Figure()

                    fig.add_trace(go.Bar(
                        x=rev_df['date'],
                        y=rev_df['revenue'],
                        name='月營收',
                        marker_color='#2196F3',
                    ))

                    if 'revenue_yoy' in rev_df.columns:
                        fig.add_trace(go.Scatter(
                            x=rev_df['date'],
                            y=rev_df['revenue_yoy'],
                            name='YoY %',
                            yaxis='y2',
                            line=dict(color='#FF5722', width=2),
                        ))

                    fig.update_layout(
                        title=f'{symbol} 月營收趨勢',
                        xaxis_title='月份',
                        yaxis_title='營收',
                        yaxis2=dict(title='YoY %', overlaying='y', side='right'),
                        height=400,
                    )

                    st.plotly_chart(fig, width="stretch")
    else:
        st.warning("FinancialReportManager 未初始化")


# =============================================================================
# Tab 4: 總經儀表板
# =============================================================================

with tab4:
    st.subheader("總經儀表板 (Macro Dashboard)")

    news_mgr = get_news_manager()

    if news_mgr:
        # 指標選擇
        available = news_mgr.list_macro_indicators()
        col1, col2 = st.columns([3, 1])

        with col1:
            selected_indicators = st.multiselect(
                "選擇總經指標",
                list(available.keys()),
                default=['CPI', 'FED_RATE', 'UNEMPLOYMENT', 'VIX'],
            )

        with col2:
            macro_years = st.selectbox("期間", [1, 2, 3, 5, 10], index=2)

        if st.button("取得總經數據", key="fetch_macro"):
            with st.spinner("取得總經數據中..."):
                macro_data = {}
                start = (date.today() - timedelta(days=365 * macro_years)).strftime('%Y-%m-%d')

                for indicator in selected_indicators:
                    df = news_mgr.get_macro_indicator(indicator, start_date=start)
                    if not df.empty:
                        macro_data[indicator] = df

                st.session_state['macro_data'] = macro_data

        if 'macro_data' in st.session_state:
            macro_data = st.session_state['macro_data']

            if macro_data:
                # 最新值一覽
                st.markdown("#### 最新數值")
                cols = st.columns(min(len(macro_data), 4))
                for i, (indicator, df) in enumerate(macro_data.items()):
                    with cols[i % len(cols)]:
                        latest = df.iloc[-1]
                        prev = df.iloc[-2] if len(df) > 1 else latest
                        change = latest['value'] - prev['value']

                        label_map = {
                            'CPI': 'CPI 消費者物價指數',
                            'FED_RATE': '聯邦基金利率 (%)',
                            'UNEMPLOYMENT': '失業率 (%)',
                            'VIX': 'VIX 恐慌指數',
                            'US_10Y': '10年期公債殖利率',
                            'YIELD_CURVE': '殖利率曲線 (10Y-2Y)',
                            'CONSUMER_SENTIMENT': '消費者信心指數',
                            'GDP': 'GDP',
                            'M2': 'M2 貨幣供給',
                        }

                        st.metric(
                            label_map.get(indicator, indicator),
                            f"{latest['value']:.2f}",
                            delta=f"{change:+.2f}",
                        )

                # 趨勢圖
                st.markdown("---")
                st.markdown("#### 趨勢圖")

                for indicator, df in macro_data.items():
                    fig = px.line(
                        df, x='date', y='value',
                        title=f"{indicator} ({available.get(indicator, '')})",
                    )
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, width="stretch")

            else:
                st.info("未取得任何資料，請確認 FRED API key 或安裝 pandas-datareader")

        # 新聞搜尋
        st.markdown("---")
        st.markdown("#### 財經新聞搜尋")

        search_col1, search_col2 = st.columns([3, 1])
        with search_col1:
            search_query = st.text_input(
                "搜尋關鍵字",
                value="Fed 利率決議",
                help="輸入中文或英文關鍵字搜尋相關新聞"
            )
        with search_col2:
            search_lang = st.selectbox("語言", ['zh-TW', 'en'], index=0)

        if st.button("搜尋新聞", key="search_news"):
            with st.spinner("搜尋中..."):
                results = news_mgr.search_news(search_query, language=search_lang)

                if results:
                    for news in results:
                        headline = news.get('headline', '')
                        url = news.get('url', '')
                        dt = news.get('datetime', '')

                        if url:
                            st.markdown(f"- [{headline}]({url}) ({dt[:10] if dt else ''})")
                        else:
                            st.markdown(f"- {headline} ({dt[:10] if dt else ''})")
                else:
                    st.info("未找到相關新聞")
    else:
        st.warning("NewsManager 未初始化")


# =============================================================================
# Footer
# =============================================================================

st.markdown("---")
st.caption("量化交易工具 - 基本面與時事整合模組")

with st.sidebar:
    st.markdown("---")
    st.markdown("""
    ### 需要的 API Keys

    - **FinMind** (台股財報): [申請](https://finmindtrade.com/)
    - **Finnhub** (美股新聞): [申請](https://finnhub.io/)
    - **FRED** (總經數據): [申請](https://fred.stlouisfed.org/docs/api/api_key.html)

    設定方式：在 `.env` 中加入
    ```
    FINMIND_API_TOKEN=xxx
    FINNHUB_API_KEY=xxx
    FRED_API_KEY=xxx
    ```
    """)
    st.caption(f"更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
