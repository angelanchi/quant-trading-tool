# -*- coding: utf-8 -*-
"""
價格警報 (Alerts) Page

功能 (Features):
- 建立價格警報 (Price alerts)
- 建立漲跌幅警報 (Percentage change alerts)
- 建立回撤警報 (Drawdown alerts)
- 管理警報 (Enable/disable/delete)
- 檢查最近觸發的警報 (Recent triggered alerts)
- 匯出/匯入警報配置 (Export/import alerts)
"""

import streamlit as st
import pandas as pd
import json
import ast
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


from views._shared import (chart, money, page_header, key_points, ACCENT, ACCENT2, GRAY, LIGHT,  # house style
                           RED, GREEN, UP, DOWN)

# Initialize session state
if 'alert_manager' not in st.session_state:
    try:
        from core.alerts import AlertManager, AlertPriority
        st.session_state.alert_manager = AlertManager()
    except Exception as e:
        st.error(f"無法初始化 AlertManager: {e}")
        st.stop()

if 'watchlists' not in st.session_state:
    try:
        with open(Path(__file__).parent.parent / "config" / "watchlists.json", "r", encoding="utf-8") as f:
            watchlists_data = json.load(f)
            symbols = []
            for wl in watchlists_data.values():
                if isinstance(wl, dict) and "symbols" in wl:
                    symbols.extend(wl["symbols"].keys())
            st.session_state.watchlists = sorted(list(set(symbols)))
    except Exception as e:
        st.session_state.watchlists = ["2330", "TSLA", "NVDA", "0050"]


def get_alert_manager():
    """Get AlertManager instance from session state."""
    return st.session_state.alert_manager


def get_symbols_list():
    """Get list of available symbols from watchlists."""
    return st.session_state.watchlists


def priority_to_chinese(priority_str):
    """Convert priority enum to Chinese."""
    priority_map = {
        "low": "低",
        "medium": "中",
        "high": "高",
        "critical": "緊急"
    }
    return priority_map.get(priority_str, priority_str)


def priority_from_chinese(priority_cn):
    """Convert Chinese priority to enum value."""
    priority_map = {
        "低": "low",
        "中": "medium",
        "高": "high",
        "緊急": "critical"
    }
    return priority_map.get(priority_cn, "medium")


def display_alerts_table():
    """Display all configured alerts in a table."""
    manager = get_alert_manager()
    alerts = list(manager.alerts.values())

    if not alerts:
        st.info("目前沒有設定任何警報")
        return

    # Create table data
    table_data = []
    for alert in alerts:
        status = "✓ 啟用" if alert.enabled else "✗ 停用"
        priority = priority_to_chinese(alert.priority.value)

        # Format condition based on type
        condition_str = ""
        alert_type_str = ""

        if alert.alert_type.value == "price_above":
            alert_type_str = "價格突破↑"
            condition_str = f"≥ {money(alert.condition.get('price'), alert.symbol)}"
        elif alert.alert_type.value == "price_below":
            alert_type_str = "價格跌破↓"
            condition_str = f"≤ {money(alert.condition.get('price'), alert.symbol)}"
        elif alert.alert_type.value == "price_change_pct":
            alert_type_str = "漲跌幅"
            change = alert.condition.get('change_pct', 0)
            direction = alert.condition.get('direction', 'any')
            direction_map = {"up": "上漲", "down": "下跌", "any": "任何"}
            condition_str = f"{direction_map.get(direction, direction)} {change:.1%}"
        elif alert.alert_type.value == "drawdown":
            alert_type_str = "回撤"
            condition_str = f"≤ {alert.condition.get('max_drawdown', 'N/A'):.1%}"
        else:
            alert_type_str = alert.alert_type.value
            condition_str = str(alert.condition)

        last_triggered = "-"
        if alert.last_triggered:
            last_triggered = alert.last_triggered.strftime("%Y-%m-%d %H:%M")

        table_data.append({
            "ID": alert.id,
            "名稱": alert.name,
            "股票": alert.symbol,
            "類型": alert_type_str,
            "條件": condition_str,
            "優先級": priority,
            "狀態": status,
            "觸發次數": alert.trigger_count,
            "最後觸發": last_triggered
        })

    df = pd.DataFrame(table_data)
    st.dataframe(df, width="stretch", hide_index=True)

    # Action buttons for each alert
    st.subheader("管理警報 (Manage Alerts)")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.write("**啟用/停用警報:**")
        alert_to_toggle = st.selectbox(
            "選擇警報",
            options=[a.id for a in alerts],
            format_func=lambda x: f"{x}: {next(a.name for a in alerts if a.id == x)}"
        )

        col_toggle1, col_toggle2 = st.columns(2)
        with col_toggle1:
            if st.button("✓ 啟用 (Enable)", key="enable_btn"):
                if manager.enable_alert(alert_to_toggle):
                    st.success("警報已啟用")
                    st.rerun()

        with col_toggle2:
            if st.button("✗ 停用 (Disable)", key="disable_btn"):
                if manager.disable_alert(alert_to_toggle):
                    st.success("警報已停用")
                    st.rerun()

    with col2:
        st.write("**刪除警報:**")
        alert_to_delete = st.selectbox(
            "選擇要刪除的警報",
            options=[a.id for a in alerts],
            format_func=lambda x: f"{x}: {next(a.name for a in alerts if a.id == x)}",
            key="delete_select"
        )

        if st.button("刪除 (Delete)", key="delete_btn"):
            if manager.remove_alert(alert_to_delete):
                st.success("警報已刪除")
                st.rerun()

    with col3:
        st.write("**警報統計:**")
        total = len(alerts)
        enabled = sum(1 for a in alerts if a.enabled)
        disabled = total - enabled
        st.write(f"總計: {total} | 啟用: {enabled} | 停用: {disabled}")


def display_recent_events():
    """Display recent triggered alert events."""
    manager = get_alert_manager()
    events = manager.get_recent_events(limit=20)

    if not events:
        st.info("目前沒有觸發的警報")
        return

    # Create events table
    events_data = []
    for event in reversed(events):  # Show newest first
        priority = priority_to_chinese(event.alert.priority.value)
        triggered_at = event.triggered_at.strftime("%Y-%m-%d %H:%M:%S")

        events_data.append({
            "時間": triggered_at,
            "警報名稱": event.alert.name,
            "股票": event.alert.symbol,
            "優先級": priority,
            "訊息": event.message,
            "當前值": str(event.current_value)
        })

    df = pd.DataFrame(events_data)
    st.dataframe(df, width="stretch", hide_index=True)


# ============================================================================
# Main Page Layout
# ============================================================================

page_header("警報系統", "價格突破、漲跌幅與回撤警報。")

# ============================================================================
# Sidebar: Create New Alert
# ============================================================================

with st.sidebar:
    st.header("新增警報 (New Alert)")

    # Symbol input
    symbol = st.text_input(
        "股票代碼 (Symbol)",
        placeholder="例: 2330, TSLA, NVDA",
        help="請輸入股票代碼"
    )

    # Alert type selection
    alert_type = st.selectbox(
        "警報類型 (Alert Type)",
        options=["price_breakout", "change_pct", "drawdown"],
        format_func=lambda x: {
            "price_breakout": "價格突破 (Price Above/Below)",
            "change_pct": "漲跌幅 (% Change)",
            "drawdown": "回撤警報 (Drawdown)"
        }[x]
    )

    alert_name = st.text_input(
        "警報名稱 (Alert Name)",
        placeholder="可選，留空則自動命名",
        value=""
    )

    priority_cn = st.selectbox(
        "優先等級 (Priority)",
        options=["低", "中", "高", "緊急"],
        index=1
    )
    priority = priority_from_chinese(priority_cn)

    # Conditional inputs based on alert type
    if alert_type == "price_breakout":
        st.subheader("價格突破設定 (Price Settings)")
        target_price = st.number_input(
            "目標價格 (Target Price)",
            value=100.0,
            step=0.01,
            format="%.2f"
        )

        direction = st.radio(
            "方向 (Direction)",
            options=["above", "below"],
            format_func=lambda x: "向上突破 ↑" if x == "above" else "向下跌破 ↓",
            horizontal=True
        )

    elif alert_type == "change_pct":
        st.subheader("漲跌幅設定 (Change Settings)")
        change_pct = st.number_input(
            "漲跌幅閾值 (Threshold %)",
            value=5.0,
            step=0.1,
            format="%.1f",
            help="例：5.0 表示 5% 變化"
        )
        change_pct = change_pct / 100.0

        change_direction = st.radio(
            "方向 (Direction)",
            options=["up", "down", "any"],
            format_func=lambda x: {
                "up": "上漲 ↑",
                "down": "下跌 ↓",
                "any": "任何方向 ↔"
            }[x],
            horizontal=True
        )

        timeframe = st.selectbox(
            "時間範圍 (Timeframe)",
            options=["1D", "1W", "1M", "3M"],
            index=0
        )

    elif alert_type == "drawdown":
        st.subheader("回撤設定 (Drawdown Settings)")
        max_drawdown_pct = st.number_input(
            "最大回撤 (Max Drawdown %)",
            value=-10.0,
            step=0.1,
            format="%.1f",
            help="負數表示回撤幅度，例：-10 表示 -10%"
        )
        max_drawdown = max_drawdown_pct / 100.0

    # Create alert button
    st.divider()
    if st.button("新增警報 (Create Alert)", width="stretch"):
        manager = get_alert_manager()

        if not symbol:
            st.error("請輸入股票代碼")
        else:
            try:
                from core.alerts import AlertPriority

                priority_enum = AlertPriority(priority)
                alert_name_final = alert_name if alert_name else None

                if alert_type == "price_breakout":
                    alert = manager.create_price_alert(
                        symbol=symbol,
                        price=target_price,
                        direction=direction,
                        name=alert_name_final,
                        priority=priority_enum
                    )
                    st.success(f"✓ 已建立價格突破警報: {alert.id}")

                elif alert_type == "change_pct":
                    alert = manager.create_change_alert(
                        symbol=symbol,
                        change_pct=change_pct,
                        direction=change_direction,
                        timeframe=timeframe,
                        name=alert_name_final,
                        priority=priority_enum
                    )
                    st.success(f"✓ 已建立漲跌幅警報: {alert.id}")

                elif alert_type == "drawdown":
                    alert = manager.create_drawdown_alert(
                        symbol=symbol,
                        max_drawdown=max_drawdown,
                        name=alert_name_final,
                        priority=priority_enum
                    )
                    st.success(f"✓ 已建立回撤警報: {alert.id}")

                st.rerun()

            except Exception as e:
                st.error(f"建立警報失敗: {e}")


# ============================================================================
# Main Content: Display Alerts and Events
# ============================================================================

# Tab layout for different sections
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "目前警報清單",
    "最近觸發的警報",
    "手動檢查",
    "匯出/匯入",
    "基本面掃描",
])

# Tab 1: Current Alerts List
with tab1:
    st.subheader("目前警報清單 (Current Alerts)")
    display_alerts_table()

# Tab 2: Recent Events
with tab2:
    st.subheader("最近觸發的警報 (Recent Alert Events)")
    display_recent_events()

# Tab 3: Manual Check
with tab3:
    st.subheader("手動檢查警報 (Manual Alert Check)")
    st.write("輸入目前股價，手動檢查是否觸發相應警報。")

    col1, col2 = st.columns(2)

    with col1:
        check_symbol = st.text_input(
            "股票代碼 (Symbol)",
            placeholder="例: 2330, TSLA",
            key="check_symbol"
        )

    with col2:
        check_price = st.number_input(
            "目前股價 (Current Price)",
            value=100.0,
            step=0.01,
            format="%.2f",
            key="check_price"
        )

    if st.button("檢查警報 (Check)", width="stretch"):
        manager = get_alert_manager()

        # Check price alerts
        manager.check_price_alerts(check_symbol, check_price)

        # Get alerts for this symbol
        alerts_for_symbol = manager.get_alerts_for_symbol(check_symbol)

        if not alerts_for_symbol:
            st.info(f"股票 {check_symbol} 沒有設定警報")
        else:
            st.success(f"已檢查 {check_symbol} 的 {len(alerts_for_symbol)} 個警報")

            # Show check results
            results_data = []
            for alert in alerts_for_symbol:
                if not alert.enabled:
                    status = "已停用"
                    triggered = "-"
                else:
                    if alert.alert_type.value == "price_above":
                        triggered = "是" if check_price >= alert.condition['price'] else "否"
                    elif alert.alert_type.value == "price_below":
                        triggered = "是" if check_price <= alert.condition['price'] else "否"
                    else:
                        triggered = "需評估"
                    status = "啟用"

                results_data.append({
                    "警報名稱": alert.name,
                    "類型": alert.alert_type.value,
                    "條件": str(alert.condition),
                    "狀態": status,
                    "是否觸發": triggered
                })

            df_results = pd.DataFrame(results_data)
            st.dataframe(df_results, width="stretch", hide_index=True)

# Tab 4: Import/Export
with tab4:
    st.subheader("匯出/匯入警報 (Export/Import Alerts)")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**匯出警報設定 (Export):**")

        manager = get_alert_manager()
        alerts_json = manager.export_alerts()

        st.text_area(
            "警報 JSON",
            value=alerts_json,
            height=300,
            key="export_area",
            disabled=True
        )

        st.download_button(
            label="下載警報 JSON",
            data=alerts_json,
            file_name=f"alerts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

    with col2:
        st.write("**匯入警報設定 (Import):**")

        import_json = st.text_area(
            "貼上警報 JSON",
            height=300,
            placeholder='例: [{"id": "alert_1", "name": "Example", ...}]',
            key="import_area"
        )

        if st.button("匯入警報 (Import)", width="stretch"):
            if not import_json.strip():
                st.error("請貼上有效的 JSON 內容")
            else:
                try:
                    manager.import_alerts(import_json)
                    st.success("✓ 警報已匯入")
                    st.rerun()
                except json.JSONDecodeError as e:
                    st.error(f"JSON 格式錯誤: {e}")
                except Exception as e:
                    st.error(f"匯入失敗: {e}")


# Tab 5: Fundamental Scanning
with tab5:
    st.subheader("基本面掃描 (Fundamental Scan)")
    st.write("掃描觀察清單中的股票，檢查基本面警報（營收衰退、VIX 飆升、殖利率倒掛等）。")

    # --- Threshold customization ---
    with st.expander("自訂門檻 (Custom Thresholds)", expanded=False):
        col_t1, col_t2, col_t3 = st.columns(3)
        with col_t1:
            revenue_decline = st.number_input(
                "月營收 YoY 衰退門檻 (%)", value=-10.0, step=1.0,
                help="低於此值觸發 warning（預設 -10%）"
            )
            revenue_surge = st.number_input(
                "月營收 YoY 暴增門檻 (%)", value=30.0, step=5.0,
                help="高於此值觸發 info（預設 30%）"
            )
        with col_t2:
            vix_warning = st.number_input(
                "VIX 警戒值", value=25.0, step=1.0,
                help="VIX > 此值觸發 warning"
            )
            vix_critical = st.number_input(
                "VIX 極端值", value=35.0, step=1.0,
                help="VIX > 此值觸發 critical"
            )
        with col_t3:
            pe_high = st.number_input(
                "P/E 偏高門檻", value=40.0, step=5.0,
            )
            pe_low = st.number_input(
                "P/E 偏低門檻", value=8.0, step=1.0,
            )

    # --- Symbol selection ---
    scan_mode = st.radio(
        "掃描範圍",
        ["觀察清單全部", "自選股票"],
        horizontal=True,
        key="fund_scan_mode",
    )

    if scan_mode == "自選股票":
        custom_symbols = st.text_input(
            "輸入股票代碼（逗號分隔）",
            placeholder="2330, 2454, AAPL, NVDA",
            key="fund_custom_symbols",
        )
        scan_symbols = [s.strip() for s in custom_symbols.split(",") if s.strip()] if custom_symbols else []
    else:
        scan_symbols = get_symbols_list()

    include_macro = st.checkbox("同時掃描總經指標（VIX、殖利率曲線）", value=True, key="fund_macro")

    # --- Run scan ---
    if st.button("開始掃描 (Run Scan)", width="stretch", key="fund_scan_btn"):
        if not scan_symbols:
            st.warning("請至少輸入一檔股票")
        else:
            try:
                from core.fundamental_alerts import (
                    FundamentalAlertChecker,
                    AlertThresholds,
                    generate_scan_report,
                )

                thresholds = AlertThresholds(
                    revenue_yoy_decline_pct=revenue_decline,
                    revenue_yoy_surge_pct=revenue_surge,
                    vix_warning=vix_warning,
                    vix_critical=vix_critical,
                    pe_high=pe_high,
                    pe_low=pe_low,
                )
                checker = FundamentalAlertChecker(thresholds=thresholds)

                with st.spinner(f"掃描中... ({len(scan_symbols)} 檔股票)"):
                    result = checker.scan_watchlist(scan_symbols)

                # --- Display results ---
                all_alerts = result.get('alerts', [])
                macro_alerts = result.get('macro_alerts', [])
                errors = result.get('errors', {})

                # Summary metrics
                col_s1, col_s2, col_s3, col_s4 = st.columns(4)
                with col_s1:
                    st.metric("掃描股票數", result.get('total_scanned', 0))
                with col_s2:
                    critical_count = sum(1 for a in all_alerts if a.severity == 'critical')
                    st.metric("🔴 Critical", critical_count)
                with col_s3:
                    warning_count = sum(1 for a in all_alerts if a.severity == 'warning')
                    st.metric("🟡 Warning", warning_count)
                with col_s4:
                    info_count = sum(1 for a in all_alerts if a.severity == 'info')
                    st.metric("🔵 Info", info_count)

                # Alerts table
                if all_alerts:
                    st.write("**個股警報：**")
                    alerts_data = []
                    for a in all_alerts:
                        severity_icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(a.severity, "⚪")
                        alerts_data.append({
                            "嚴重度": f"{severity_icon} {a.severity}",
                            "股票": a.symbol,
                            "類型": a.alert_type.value,
                            "說明": a.message,
                            "數值": f"{a.value:.2f}" if a.value is not None else "-",
                        })
                    df_alerts = pd.DataFrame(alerts_data)
                    st.dataframe(df_alerts, width="stretch", hide_index=True)
                else:
                    st.success("所有股票基本面正常，沒有觸發任何警報！")

                # Macro alerts
                if include_macro and macro_alerts:
                    st.write("**總經指標警報：**")
                    macro_data = []
                    for a in macro_alerts:
                        severity_icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(a.severity, "⚪")
                        macro_data.append({
                            "嚴重度": f"{severity_icon} {a.severity}",
                            "類型": a.alert_type.value,
                            "說明": a.message,
                            "數值": f"{a.value:.2f}" if a.value is not None else "-",
                        })
                    df_macro = pd.DataFrame(macro_data)
                    st.dataframe(df_macro, width="stretch", hide_index=True)

                # Errors
                if errors:
                    with st.expander(f"取得失敗的股票 ({len(errors)})", expanded=False):
                        for sym, err in errors.items():
                            st.write(f"- **{sym}**: {err}")

                # Full text report
                with st.expander("完整文字報告", expanded=False):
                    report_text = generate_scan_report(result)
                    st.code(report_text, language="text")

                    st.download_button(
                        "下載報告",
                        data=report_text,
                        file_name=f"fundamental_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain",
                        key="fund_download",
                    )

            except ImportError as e:
                st.error(f"模組載入失敗: {e}\n請確認 core/fundamental_alerts.py 已正確安裝。")
            except Exception as e:
                st.error(f"掃描失敗: {e}")


# ============================================================================
# Validation: Parse this file's syntax
# ============================================================================

# Validate this file's syntax
try:
    with open(__file__, 'r', encoding='utf-8') as f:
        code = f.read()
    ast.parse(code)
except SyntaxError as e:
    st.error(f"檔案語法錯誤: {e}")
