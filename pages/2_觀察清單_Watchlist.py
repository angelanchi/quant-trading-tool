# -*- coding: utf-8 -*-
"""
觀察清單 (Watchlist) — 選股入口

功能：
- 瀏覽所有觀察群組與股票
- 即時報價總覽（一張表看所有持股現況）
- 新增/刪除股票
- 點選股票 → 跳轉到「個股分析」頁做深入分析

設計理念：
    這一頁只做「選股」和「總覽」，不做深入分析。
    深入分析統一在「3_個股分析」頁面完成。
"""

import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys
import logging

sys.path.insert(0, str(Path(__file__).parent.parent))
logger = logging.getLogger(__name__)


from views._shared import (chart, page_header, key_points, ACCENT, ACCENT2, GRAY, LIGHT,  # house style
                           RED, GREEN, UP, DOWN)

WATCHLIST_PATH = Path(__file__).parent.parent / "config" / "watchlists.json"


# =============================================================================
# Helpers
# =============================================================================
def load_watchlists() -> dict:
    try:
        with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except Exception as e:
        st.error(f"無法載入觀察清單: {e}")
        return {}


def save_watchlists(watchlists: dict):
    save_data = {
        "_說明": "觀察清單設定檔 - 可依個人需求自由增刪股票",
        "_更新日期": datetime.now().strftime("%Y-%m-%d"),
    }
    save_data.update(watchlists)
    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    try:  # let the decision-flow pages see the change immediately
        from views._shared import load_watchlists as _lw
        _lw.clear()
    except Exception:
        pass


def get_quick_price(symbol: str) -> dict:
    """快速取得最新收盤價（不做完整歷史下載）。台股自動嘗試上櫃 (.TWO)。"""
    import yfinance as yf
    import time as _time

    is_tw = symbol.isdigit() or (len(symbol) == 5 and symbol[:4].isdigit())
    # 台股：先試 .TW（上市），失敗再試 .TWO（上櫃）
    candidates = [f"{symbol}.TW", f"{symbol}.TWO"] if is_tw else [symbol]

    for yf_sym in candidates:
        try:
            ticker = yf.Ticker(yf_sym)
            hist = ticker.history(period="5d")
            if hist is not None and not hist.empty:
                close = hist["Close"].iloc[-1]
                prev = hist["Close"].iloc[-2] if len(hist) >= 2 else close
                change = (close / prev - 1) * 100
                return {"price": close, "change": change}
        except Exception:
            pass
        _time.sleep(0.5)  # rate limit 保護
    return {}


# =============================================================================
# Main Page
# =============================================================================
page_header("觀察清單", "管理觀察中的標的與分組，並快速跳到個股分析。")
st.caption("瀏覽你的持股和觀察標的，點選任意股票跳轉到深入分析。")

watchlists = load_watchlists()
if not watchlists:
    st.warning("尚未建立觀察清單，請編輯 config/watchlists.json")
    st.stop()

# =============================================================================
# Sidebar: 新增/管理股票
# =============================================================================
with st.sidebar:
    st.subheader("管理觀察清單")

    group_names = {k: v.get("name", k) for k, v in watchlists.items()}

    # 新增股票
    st.write("**新增股票：**")
    target_group = st.selectbox(
        "加入到群組",
        options=list(watchlists.keys()),
        format_func=lambda x: group_names.get(x, x),
        key="add_group",
    )
    new_symbol = st.text_input("股票代碼", placeholder="例如：2330 或 NVDA")
    new_desc = st.text_input("說明（選填）", placeholder="例如：台積電")

    if st.button("新增", width="stretch"):
        if new_symbol.strip():
            sym = new_symbol.strip().upper()
            desc = new_desc.strip() if new_desc.strip() else sym
            watchlists[target_group]["symbols"][sym] = desc
            save_watchlists(watchlists)
            st.success(f"已新增 {sym}")
            st.rerun()
        else:
            st.warning("請輸入股票代碼")

    st.markdown("---")
    st.write("**匯出觀察清單：**")
    all_rows = []
    for gk, gd in watchlists.items():
        gn = gd.get("name", gk)
        for sym, desc in gd.get("symbols", {}).items():
            all_rows.append({"群組": gn, "代碼": sym, "說明": desc})
    if all_rows:
        csv = pd.DataFrame(all_rows).to_csv(index=False).encode("utf-8-sig")
        st.download_button("匯出 CSV", csv, file_name=f"觀察清單_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")


# =============================================================================
# Main content: 各群組 + 股票卡片
# =============================================================================

# Quick quote toggle
fetch_prices = st.checkbox("載入即時報價（需要 yfinance，會較慢）", value=False, key="fetch_prices")

for group_key, group_data in watchlists.items():
    group_name = group_data.get("name", group_key)
    symbols = group_data.get("symbols", {})

    if not symbols:
        continue

    st.subheader(f"{group_name}")

    # Build table data
    rows = []
    for sym, desc in symbols.items():
        row = {"代碼": sym, "說明": desc[:30]}

        if fetch_prices:
            quote = get_quick_price(sym)
            if quote:
                row["現價"] = f"{quote['price']:.2f}"
                row["漲跌%"] = f"{quote['change']:+.2f}%"
            else:
                row["現價"] = "—"
                row["漲跌%"] = "—"

        rows.append(row)

    df = pd.DataFrame(rows)

    # Display as interactive table
    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        column_config={
            "代碼": st.column_config.TextColumn("代碼", width="small"),
            "說明": st.column_config.TextColumn("說明", width="medium"),
        },
    )

    # Button row: select any stock to deep-dive
    cols = st.columns(min(len(symbols), 6))
    for i, sym in enumerate(list(symbols.keys())[:6]):
        with cols[i]:
            if st.button(f"{sym}", key=f"goto_{group_key}_{sym}", width="stretch"):
                try:
                    from core.workflow import WorkflowState
                    WorkflowState.set_active_stock(sym, symbols[sym])
                except Exception:
                    pass
                st.switch_page("pages/3_個股分析_Stock_Analysis.py")

    # Delete stock
    with st.expander(f"刪除 {group_name} 中的股票", expanded=False):
        del_sym = st.selectbox(
            "選擇要刪除的股票",
            options=list(symbols.keys()),
            format_func=lambda s: f"{s} — {symbols.get(s, '')[:20]}",
            key=f"del_{group_key}",
        )
        if st.button("刪除", key=f"del_btn_{group_key}"):
            if del_sym in watchlists[group_key]["symbols"]:
                del watchlists[group_key]["symbols"][del_sym]
                save_watchlists(watchlists)
                st.success(f"已刪除 {del_sym}")
                st.rerun()

    st.markdown("---")


# =============================================================================
# Summary stats
# =============================================================================
total_stocks = sum(len(g.get("symbols", {})) for g in watchlists.values())
st.caption(f"共 {len(watchlists)} 個群組，{total_stocks} 檔股票　|　編輯 config/watchlists.json 可批次管理")
