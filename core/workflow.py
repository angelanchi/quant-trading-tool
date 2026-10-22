# -*- coding: utf-8 -*-
"""
跨頁面工作流管理 (Cross-Page Workflow Manager)

用 Streamlit session_state 在不同頁面之間傳遞分析上下文，
讓使用者在分析一檔股票時能自然地跳轉到回測、產業、風險等頁面。

使用方式：
    from core.workflow import WorkflowState, render_action_bar

    # 在 Watchlist 頁設定當前股票
    WorkflowState.set_active_stock('2330')

    # 在任何頁面讀取
    symbol = WorkflowState.get_active_stock()

    # 在頁面底部渲染快捷操作列
    render_action_bar()
"""

import streamlit as st
from typing import Optional


class WorkflowState:
    """
    管理跨頁面的共用狀態。

    所有狀態存在 st.session_state 裡，頁面切換不會消失。
    """

    # --- Active Stock ---
    @staticmethod
    def set_active_stock(symbol: str, name: str = ""):
        """設定當前正在分析的股票。"""
        st.session_state["wf_active_symbol"] = symbol
        st.session_state["wf_active_name"] = name

    @staticmethod
    def get_active_stock() -> Optional[str]:
        """取得當前正在分析的股票代碼。"""
        return st.session_state.get("wf_active_symbol")

    @staticmethod
    def get_active_name() -> str:
        return st.session_state.get("wf_active_name", "")

    # --- Active Sector ---
    @staticmethod
    def set_active_sector(sector_key: str):
        st.session_state["wf_active_sector"] = sector_key

    @staticmethod
    def get_active_sector() -> Optional[str]:
        return st.session_state.get("wf_active_sector")

    # --- Backtest Result passthrough ---
    @staticmethod
    def set_backtest_symbols(symbols: list):
        """設定要回測的股票清單。"""
        st.session_state["wf_backtest_symbols"] = symbols

    @staticmethod
    def get_backtest_symbols() -> list:
        return st.session_state.get("wf_backtest_symbols", [])

    # --- Portfolio symbols ---
    @staticmethod
    def set_portfolio_symbols(symbols: list):
        st.session_state["wf_portfolio_symbols"] = symbols

    @staticmethod
    def get_portfolio_symbols() -> list:
        return st.session_state.get("wf_portfolio_symbols", [])

    # --- Breadcrumb trail ---
    @staticmethod
    def push_breadcrumb(page_name: str, page_file: str):
        """記錄使用者的頁面瀏覽路徑。"""
        if "wf_breadcrumbs" not in st.session_state:
            st.session_state["wf_breadcrumbs"] = []
        trail = st.session_state["wf_breadcrumbs"]
        # Avoid duplicate consecutive entries
        if not trail or trail[-1]["page"] != page_name:
            trail.append({"page": page_name, "file": page_file})
            # Keep last 10
            st.session_state["wf_breadcrumbs"] = trail[-10:]

    @staticmethod
    def get_breadcrumbs() -> list:
        return st.session_state.get("wf_breadcrumbs", [])

    # --- Helpers ---
    @staticmethod
    def is_taiwan_stock(symbol: str) -> bool:
        if not symbol:
            return False
        clean = symbol.strip().replace(".TW", "").replace(".TWO", "")
        return clean.isdigit() and len(clean) in (4, 5)


def render_active_stock_badge():
    """在頁面頂部渲染當前分析股票的 badge。"""
    symbol = WorkflowState.get_active_stock()
    if symbol:
        name = WorkflowState.get_active_name()
        label = f"{symbol} {name}" if name else symbol
        st.caption(f"🎯 目前分析: **{label}**")


def render_action_bar(current_page: str = ""):
    """
    在頁面底部渲染快捷操作列，方便跳轉到相關頁面。

    Args:
        current_page: 當前頁面名稱，用來隱藏自己的按鈕
    """
    symbol = WorkflowState.get_active_stock()
    if not symbol:
        return

    st.divider()
    st.write(f"**📌 {symbol} 快捷操作：**")

    # Define available actions
    actions = [
        ("📋", "觀察清單", "pages/2_觀察清單_Watchlist.py", "watchlist"),
        ("🔍", "個股分析", "pages/3_個股分析_Stock_Analysis.py", "stock_analysis"),
        ("🏭", "產業分析", "pages/1_產業分析_Sector.py", "sector"),
        ("📈", "回測策略", "pages/4_策略回測_Backtesting.py", "backtest"),
        ("💼", "投資組合", "pages/5_投資組合_Portfolio.py", "portfolio"),
        ("⚠️", "風險分析", "pages/6_風險分析_Risk.py", "risk"),
        ("🔔", "設定警報", "pages/8_警報系統_Alerts.py", "alerts"),
    ]

    # Filter out current page
    actions = [a for a in actions if a[3] != current_page]

    # Render as columns
    cols = st.columns(len(actions))
    for i, (icon, label, page_file, key) in enumerate(actions):
        with cols[i]:
            if st.button(f"{icon} {label}", key=f"nav_{key}", use_container_width=True):
                st.switch_page(page_file)
