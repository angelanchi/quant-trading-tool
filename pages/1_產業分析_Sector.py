# -*- coding: utf-8 -*-
"""
產業分析 (Sector Analysis) Page

功能：
- Tab 1: 產業輪動追蹤 — 哪個產業資金正在流入
- Tab 2: 供應鏈上下游分析 — 上中下游連動
- Tab 3: 同產業個股比較 — 產業內相對強弱
- Tab 4: 產業新聞與政策 — 即時新聞追蹤
"""

import streamlit as st
import pandas as pd
import ast
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


from views._shared import (chart, page_header, key_points, ACCENT, ACCENT2, GRAY, LIGHT,  # house style
                           RED, GREEN, UP, DOWN)

# =============================================================================
# Cached Resources
# =============================================================================
@st.cache_resource
def get_sector_manager():
    from core.sector_analysis import SectorAnalysisManager
    return SectorAnalysisManager()


# =============================================================================
# Main Page
# =============================================================================
page_header("產業分析", "產業輪動、供應鏈上下游與同業比較。")

# Show active stock badge if available
try:
    from core.workflow import WorkflowState, render_active_stock_badge
    render_active_stock_badge()
except Exception:
    pass

manager = get_sector_manager()
sector_map = manager.sector_map

tab1, tab2, tab3, tab4 = st.tabs([
    "產業輪動",
    "供應鏈分析",
    "同業比較",
    "產業新聞",
])


# =============================================================================
# Tab 1: Sector Rotation
# =============================================================================
with tab1:
    st.subheader("產業輪動追蹤 (Sector Rotation)")
    st.write("追蹤資金在不同產業間的流動，找出目前最受資金青睞的產業。")

    st.caption(
        "動量分數 = 1W報酬(30%) + 1M報酬(30%) + 3M報酬(15%) + "
        "量能變化(10%) + 廣度指標(15%)。50 分為中性。"
    )

    if st.button("掃描所有產業", width="stretch", key="rotation_scan"):
        with st.spinner("正在分析各產業動量... (需下載多檔股票資料)"):
            try:
                rotation_results = manager.rotation.track_all_sectors()
                df = manager.rotation.to_dataframe(rotation_results)

                if not df.empty:
                    st.session_state["rotation_df"] = df
                    st.session_state["rotation_raw"] = rotation_results
                else:
                    st.warning("未取得任何產業資料")
            except Exception as e:
                st.error(f"分析失敗: {e}")

    if "rotation_df" in st.session_state:
        df = st.session_state["rotation_df"]
        st.dataframe(df, width="stretch", hide_index=True)

        # Bar chart
        raw = st.session_state.get("rotation_raw", [])
        if raw:
            import plotly.graph_objects as go

            chart_data = sorted(raw, key=lambda x: x.momentum_score, reverse=True)
            names = [r.sector_name for r in chart_data]
            scores = [r.momentum_score for r in chart_data]
            colors = [
                UP if s >= 60 else GRAY if s >= 45 else DOWN
                for s in scores
            ]

            fig = go.Figure(go.Bar(
                x=scores,
                y=names,
                orientation="h",
                marker_color=colors,
                text=[f"{s:.0f}" for s in scores],
                textposition="auto",
            ))
            fig.update_layout(
                title="產業動量分數排名",
                xaxis_title="動量分數",
                yaxis=dict(autorange="reversed"),
                height=400,
            )
            chart(fig)

            # Insights
            st.write("**快速解讀：**")
            hot = [r for r in chart_data if r.momentum_score >= 60]
            cold = [r for r in chart_data if r.momentum_score < 40]

            if hot:
                st.success(f"資金流入產業: {', '.join(r.sector_name for r in hot)}")
            if cold:
                st.warning(f"資金流出產業: {', '.join(r.sector_name for r in cold)}")
            if not hot and not cold:
                st.info("各產業動量差異不大，目前處於盤整格局。")


# =============================================================================
# Tab 2: Supply Chain Analysis
# =============================================================================
with tab2:
    st.subheader("供應鏈上下游分析 (Supply Chain)")
    st.write("分析供應鏈各層的表現與連動關係。")

    chains = sector_map.supply_chains
    if chains:
        chain_options = {k: v.get("name", k) for k, v in chains.items() if not k.startswith("_")}

        selected_chain = st.selectbox(
            "選擇供應鏈",
            options=list(chain_options.keys()),
            format_func=lambda x: chain_options[x],
            key="chain_select",
        )

        if st.button("分析供應鏈", width="stretch", key="chain_analyze"):
            with st.spinner(f"分析 {chain_options[selected_chain]}..."):
                try:
                    analysis = manager.supply_chain.analyze_chain(selected_chain)

                    if analysis:
                        st.session_state["chain_result"] = analysis
                    else:
                        st.warning("分析結果為空")
                except Exception as e:
                    st.error(f"分析失敗: {e}")

        if "chain_result" in st.session_state:
            analysis = st.session_state["chain_result"]
            st.write(f"**{analysis.get('chain_name', '')}** — 共 {analysis.get('total_stocks', 0)} 檔股票")

            # Per-layer summary
            position_names = {
                "upstream": "上游",
                "midstream": "↔ 中游",
                "downstream": "下游",
                "reference_us": "美股參考",
            }

            cols = st.columns(4)
            for i, (pos, name) in enumerate(position_names.items()):
                layer = analysis.get("layers", {}).get(pos)
                if layer:
                    with cols[i]:
                        st.metric(
                            label=name,
                            value=f"{layer['avg_return_1w']:.2%}",
                            delta=f"1M: {layer['avg_return_1m']:.2%}",
                            help=f"類別: {', '.join(layer['categories'])}",
                            delta_color="inverse",
                        )

            # Detailed table
            detail_df = manager.supply_chain.chain_summary_df(analysis)
            if not detail_df.empty:
                st.write("**個股明細：**")
                st.dataframe(detail_df, width="stretch", hide_index=True)

            # Correlation
            corr = analysis.get("correlation", {})
            if corr:
                st.write("**層間相關性：**")
                corr_names = {
                    "upstream_vs_midstream": "上游 ↔ 中游",
                    "upstream_vs_downstream": "上游 ↔ 下游",
                    "midstream_vs_downstream": "中游 ↔ 下游",
                }
                for key, value in corr.items():
                    label = corr_names.get(key, key)
                    strength = "強" if abs(value) > 0.7 else "中" if abs(value) > 0.4 else "弱"
                    st.write(f"  {label}: **{value:.3f}** ({strength}相關)")

    else:
        st.info("尚未設定供應鏈資料，請編輯 config/sectors.json。")


# =============================================================================
# Tab 3: Peer Comparison
# =============================================================================
with tab3:
    st.subheader("同產業個股比較 (Peer Comparison)")
    st.write("比較同一產業內的個股，找出相對最強勢的標的。")

    sector_options = {k: v.name for k, v in sector_map.sectors.items() if k != "ETF_指數"}

    selected_sector = st.selectbox(
        "選擇產業",
        options=list(sector_options.keys()),
        format_func=lambda x: f"{sector_options[x]} ({len(sector_map.get_sector(x).symbols)} 檔)",
        key="peer_sector",
    )

    if selected_sector:
        sector = sector_map.get_sector(selected_sector)
        if sector:
            st.caption(f"{sector.description}")
            with st.expander("成分股列表", expanded=False):
                for sym, desc in sector.symbols.items():
                    st.write(f"- **{sym}**: {desc}")

    if st.button("開始比較", width="stretch", key="peer_compare"):
        with st.spinner(f"比較 {sector_options[selected_sector]} 內個股..."):
            try:
                peer_results = manager.peers.compare_sector(selected_sector)
                if peer_results:
                    df = manager.peers.to_dataframe(peer_results)
                    st.session_state["peer_df"] = df
                    st.session_state["peer_results"] = peer_results
                else:
                    st.warning("比較結果為空")
            except Exception as e:
                st.error(f"比較失敗: {e}")

    if "peer_df" in st.session_state:
        df = st.session_state["peer_df"]
        st.dataframe(df, width="stretch", hide_index=True)

        # Relative strength bar chart
        peer_results = st.session_state.get("peer_results", [])
        if peer_results:
            import plotly.graph_objects as go

            symbols = [r.symbol for r in peer_results]
            rs_values = [r.relative_strength * 100 for r in peer_results]
            colors = [UP if v > 0 else DOWN for v in rs_values]

            fig = go.Figure(go.Bar(
                x=symbols,
                y=rs_values,
                marker_color=colors,
                text=[f"{v:+.1f}%" for v in rs_values],
                textposition="auto",
            ))
            fig.update_layout(
                title="相對強弱 (vs 產業平均 1M 報酬)",
                yaxis_title="相對強弱 (%)",
                height=400,
            )
            chart(fig)

            # Quick insight
            strongest = peer_results[0] if peer_results else None
            weakest = peer_results[-1] if len(peer_results) > 1 else None

            col1, col2 = st.columns(2)
            with col1:
                if strongest:
                    st.success(f"最強勢: **{strongest.symbol}** ({strongest.name}) — "
                              f"1M {strongest.change_1m:.2%}, RSI {strongest.rsi_14:.0f}")
            with col2:
                if weakest:
                    st.warning(f"最弱勢: **{weakest.symbol}** ({weakest.name}) — "
                              f"1M {weakest.change_1m:.2%}, RSI {weakest.rsi_14:.0f}")


# =============================================================================
# Tab 4: Sector News
# =============================================================================
with tab4:
    st.subheader("產業新聞與政策追蹤 (Sector News)")

    news_mode = st.radio(
        "新聞模式",
        ["單一產業", "政策面", "自訂關鍵字"],
        horizontal=True,
        key="news_mode",
    )

    if news_mode == "單一產業":
        news_sector_options = {
            k: v.name for k, v in sector_map.sectors.items()
            if k in manager.news.SECTOR_KEYWORDS
        }

        news_sector = st.selectbox(
            "選擇產業",
            options=list(news_sector_options.keys()),
            format_func=lambda x: news_sector_options[x],
            key="news_sector",
        )
        search_keywords = None
        is_policy = False

    elif news_mode == "政策面":
        news_sector = None
        search_keywords = None
        is_policy = True

    else:
        news_sector = None
        is_policy = False
        custom_kw = st.text_input(
            "輸入搜尋關鍵字",
            placeholder="例: AI 晶片 出口管制",
            key="news_custom_kw",
        )
        search_keywords = [custom_kw] if custom_kw else None

    if st.button("搜尋新聞", width="stretch", key="news_search"):
        with st.spinner("搜尋新聞中..."):
            try:
                if is_policy:
                    news_list = manager.news.get_policy_news()
                elif search_keywords:
                    news_list = []
                    for kw in search_keywords:
                        news_list.extend(manager.news._fetch_google_news(kw, max_results=10))
                elif news_sector:
                    news_list = manager.news.get_sector_news(news_sector)
                else:
                    news_list = []

                st.session_state["sector_news"] = news_list

            except Exception as e:
                st.error(f"搜尋失敗: {e}")

    if "sector_news" in st.session_state:
        news_list = st.session_state["sector_news"]

        if news_list:
            st.write(f"找到 **{len(news_list)}** 則新聞")

            for i, item in enumerate(news_list):
                title = item.get("title", "無標題")
                url = item.get("url", "")
                source = item.get("source", "")
                pub = item.get("published", "")
                kw = item.get("keyword", "")

                with st.container():
                    col_n1, col_n2 = st.columns([4, 1])
                    with col_n1:
                        if url:
                            st.markdown(f"**{i+1}.** [{title}]({url})")
                        else:
                            st.write(f"**{i+1}.** {title}")
                    with col_n2:
                        st.caption(f"{source}")
                    if pub or kw:
                        st.caption(f"{pub}  |  {kw}")
                    st.divider()
        else:
            st.info("沒有找到相關新聞。")


# =============================================================================
# Validation
# =============================================================================
try:
    with open(__file__, "r", encoding="utf-8") as f:
        code = f.read()
    ast.parse(code)
except SyntaxError as e:
    st.error(f"檔案語法錯誤: {e}")
