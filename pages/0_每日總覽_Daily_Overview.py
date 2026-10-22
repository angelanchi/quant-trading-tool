# -*- coding: utf-8 -*-
"""
每日晨報 (Daily Report) Page — Phase 4

功能：
- 一鍵執行完整掃描（基本面 + 情緒 + 多因子）
- 顯示即時掃描結果
- 查看歷史報告
- 多因子排名互動表格
"""

import streamlit as st
import pandas as pd
import json
import ast
from datetime import datetime, date
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


from views._shared import (chart, page_header, key_points, ACCENT, ACCENT2, GRAY, LIGHT,  # house style
                           RED, GREEN, UP, DOWN)

# =============================================================================
# Helper: Load symbols from watchlists
# =============================================================================
@st.cache_data(ttl=3600)
def load_symbols():
    """Load symbols from watchlists.json."""
    try:
        wl_path = Path(__file__).parent.parent / "config" / "watchlists.json"
        with open(wl_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        symbols = []
        for key, group in data.items():
            if key.startswith("_"):
                continue
            if isinstance(group, dict) and "symbols" in group:
                symbols.extend(group["symbols"].keys())
        return sorted(set(symbols))
    except Exception:
        return ["2330", "AAPL", "NVDA"]


# =============================================================================
# Cached scanner instances
# =============================================================================
@st.cache_resource
def get_fundamental_checker():
    from core.fundamental_alerts import FundamentalAlertChecker
    return FundamentalAlertChecker()


@st.cache_resource
def get_sentiment_analyzer():
    from core.sentiment import SentimentAnalyzer
    return SentimentAnalyzer()


@st.cache_resource
def get_multi_factor_model():
    from core.multi_factor import MultiFactorModel
    return MultiFactorModel()


# =============================================================================
# Main Page
# =============================================================================
page_header("每日晨報", "基本面、情緒與多因子掃描的每日摘要。")

today_str = date.today().strftime("%Y-%m-%d")
weekday_zh = ["一", "二", "三", "四", "五", "六", "日"]
weekday = weekday_zh[date.today().weekday()]
st.caption(f"{today_str} 週{weekday}")

tab1, tab2, tab3 = st.tabs([
    "即時掃描",
    "多因子排名",
    "歷史報告",
])


# =============================================================================
# Tab 1: Live Scan
# =============================================================================
with tab1:
    st.subheader("一鍵掃描 (One-Click Scan)")

    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        run_sentiment = st.checkbox("包含新聞情緒分析", value=True, key="dr_sentiment")
    with col_opt2:
        run_mf = st.checkbox("包含多因子評分", value=True, key="dr_mf")

    symbols = load_symbols()
    st.write(f"將掃描 **{len(symbols)}** 檔股票")

    if st.button("開始每日掃描", width="stretch", type="primary", key="dr_scan"):

        # --- 1. Fundamental Scan ---
        st.write("**1/3 基本面掃描...**")
        progress = st.progress(0)
        try:
            from core.fundamental_alerts import generate_scan_report

            checker = get_fundamental_checker()
            fund_result = checker.scan_watchlist(symbols)
            progress.progress(33)

            alerts = fund_result.get("alerts", [])
            by_symbol = fund_result.get("by_symbol", {})
            macro_alerts = by_symbol.get("MACRO", [])
            stock_alerts = [a for a in alerts if a.symbol != "MACRO"]

            col1, col2, col3 = st.columns(3)
            critical = [a for a in stock_alerts if a.severity == "critical"]
            warnings = [a for a in stock_alerts if a.severity == "warning"]

            with col1:
                st.metric("🔴 Critical", len(critical))
            with col2:
                st.metric("🟡 Warning", len(warnings))
            with col3:
                st.metric("✓ 掃描股票", fund_result.get("total_symbols", 0))

            if stock_alerts:
                alert_data = []
                for a in stock_alerts:
                    icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(a.severity, "⚪")
                    alert_data.append({
                        "嚴重度": f"{icon} {a.severity}",
                        "股票": a.symbol,
                        "說明": a.message,
                    })
                st.dataframe(pd.DataFrame(alert_data), width="stretch", hide_index=True)

            if macro_alerts:
                st.write("**總經警報：**")
                for a in macro_alerts:
                    icon = {"critical": "🔴", "warning": "🟡"}.get(a.severity, "🔵")
                    st.write(f"{icon} {a.message}")

        except Exception as e:
            st.error(f"基本面掃描失敗: {e}")
            fund_result = {}

        # --- 2. Sentiment Scan ---
        if run_sentiment:
            st.write("**2/3 新聞情緒掃描...**")
            try:
                analyzer = get_sentiment_analyzer()
                sentiment_results = {}
                for i, sym in enumerate(symbols):
                    try:
                        sent = analyzer.get_stock_sentiment(sym, days_back=3)
                        sentiment_results[sym] = sent
                    except Exception:
                        sentiment_results[sym] = {"label": "unknown", "avg_score": 0}

                progress.progress(66)

                # Show sentiment summary
                pos = [s for s, v in sentiment_results.items() if v.get("label") == "positive"]
                neg = [s for s, v in sentiment_results.items() if v.get("label") == "negative"]

                col_s1, col_s2, col_s3 = st.columns(3)
                with col_s1:
                    st.metric("正面情緒", len(pos))
                with col_s2:
                    st.metric("負面情緒", len(neg))
                with col_s3:
                    st.metric("中性/未知", len(symbols) - len(pos) - len(neg))

                if pos:
                    st.success(f"正面情緒股票: {', '.join(pos)}")
                if neg:
                    st.warning(f"負面情緒股票: {', '.join(neg)}")

            except Exception as e:
                st.error(f"情緒掃描失敗: {e}")
                sentiment_results = {}
        else:
            sentiment_results = {}
            progress.progress(66)

        # --- 3. Multi-Factor Ranking ---
        if run_mf:
            st.write("**3/3 多因子評分...**")
            try:
                model = get_multi_factor_model()
                ranking_df = model.rank_watchlist(symbols)
                progress.progress(100)

                if ranking_df is not None and not ranking_df.empty:
                    st.write("**Top 10 推薦：**")
                    display_cols = ["代碼", "總分", "技術面", "基本面", "情緒面", "評等"]
                    available_cols = [c for c in display_cols if c in ranking_df.columns]
                    top10 = ranking_df.head(10)[available_cols]

                    col_rename = {
                        "代碼": "股票",
                        "評等": "評級",
                    }
                    top10 = top10.rename(columns=col_rename)
                    st.dataframe(top10, width="stretch", hide_index=True)

                    # Store in session for Tab 2
                    st.session_state["mf_ranking"] = ranking_df
                else:
                    st.info("多因子評分無結果")

            except Exception as e:
                st.error(f"多因子評分失敗: {e}")
        else:
            progress.progress(100)

        st.success("✓ 每日掃描完成！")


# =============================================================================
# Tab 2: Multi-Factor Detail
# =============================================================================
with tab2:
    st.subheader("多因子評分排名 (Multi-Factor Ranking)")

    if "mf_ranking" in st.session_state and st.session_state["mf_ranking"] is not None:
        df = st.session_state["mf_ranking"]

        # Filters
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            min_score = st.slider("最低總分篩選", 0, 100, 0, key="mf_min")
        with col_f2:
            sort_by = st.selectbox(
                "排序依據",
                ["總分", "技術面", "基本面", "情緒面"],
                key="mf_sort",
            )

        filtered = df[df["總分"] >= min_score].sort_values(sort_by, ascending=False)

        col_rename = {
            "代碼": "股票",
            "評等": "評級",
        }
        display_cols = ["代碼", "總分", "技術面", "基本面", "情緒面", "評等"]
        display_cols = [c for c in display_cols if c in filtered.columns]
        st.dataframe(
            filtered[display_cols].rename(columns=col_rename),
            width="stretch",
            hide_index=True,
        )

        st.caption(f"共 {len(filtered)} / {len(df)} 檔股票")
    else:
        st.info("請先在「即時掃描」分頁執行掃描，才會有多因子排名資料。")

        # Standalone run
        if st.button("單獨執行多因子評分", key="mf_standalone"):
            try:
                model = get_multi_factor_model()
                syms = load_symbols()
                with st.spinner(f"評分中... ({len(syms)} 檔)"):
                    ranking = model.rank_watchlist(syms)
                if ranking is not None and not ranking.empty:
                    st.session_state["mf_ranking"] = ranking
                    st.rerun()
                else:
                    st.warning("評分結果為空")
            except Exception as e:
                st.error(f"評分失敗: {e}")


# =============================================================================
# Tab 3: Historical Reports
# =============================================================================
with tab3:
    st.subheader("歷史報告 (Past Reports)")

    reports_dir = Path(__file__).parent.parent / "reports"

    if reports_dir.exists():
        report_files = sorted(reports_dir.glob("daily_*.txt"), reverse=True)

        if report_files:
            selected_file = st.selectbox(
                "選擇報告",
                options=report_files,
                format_func=lambda p: p.stem.replace("daily_", "").replace("_", " "),
                key="hist_select",
            )

            if selected_file:
                with open(selected_file, "r", encoding="utf-8") as f:
                    content = f.read()
                st.code(content, language="text")

                st.download_button(
                    "下載此報告",
                    data=content,
                    file_name=selected_file.name,
                    mime="text/plain",
                    key="hist_download",
                )
        else:
            st.info("尚無歷史報告。請先執行掃描。")
    else:
        st.info("reports 資料夾不存在。第一次執行掃描腳本後會自動建立。")


# =============================================================================
# Validation
# =============================================================================
try:
    with open(__file__, "r", encoding="utf-8") as f:
        code = f.read()
    ast.parse(code)
except SyntaxError as e:
    st.error(f"檔案語法錯誤: {e}")
