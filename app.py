# -*- coding: utf-8 -*-
"""
CQF 交易面板 — main entry.  Run:  streamlit run app.py

Navigation (st.navigation, Streamlit >= 1.40):
  決策流程   views/  ① 盤勢 → ② 選股 → ③ 情境定價 → ④ 風險部位 → ⑤ 說法驗證 → ⑥ 執行覆盤
  工具箱     pages/  original pages, unchanged
  CQF 實驗室 views/  fixed income (M6), concept map
See docs/CQF_PANEL_REDESIGN.md for the design rationale.
"""
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# Load .env before any module reads os.environ
try:
    from dotenv import load_dotenv
    if (ROOT / ".env").exists():
        load_dotenv(ROOT / ".env", override=False)
except ImportError:
    pass

st.set_page_config(page_title="CQF 交易面板", layout="wide", initial_sidebar_state="expanded")

from views._shared import apply_style  # noqa: E402

apply_style()

from views._state import STEPS, TEMPLATES, ctx, render_sidebar  # noqa: E402

P = st.Page


def step_page(key: str) -> st.Page:
    title, path, url, icon = STEPS[key]
    return P(path, url_path=url, title=title, icon=icon)


# Decision flow = the steps of the active template (sidebar), in template order;
# the remaining steps stay reachable under 其他步驟.
tpl_label, tpl_steps, _ = TEMPLATES.get(ctx().get("template"), TEMPLATES["full"])
flow = [P("views/home.py", title="總覽", icon=":material/home:", default=True)] + [step_page(k) for k in tpl_steps]
others = [step_page(k) for k in STEPS if k not in tpl_steps]
toolbox = [
    P("pages/0_每日總覽_Daily_Overview.py", title="每日總覽"),
    P("pages/1_產業分析_Sector.py", title="產業分析"),
    P("pages/2_觀察清單_Watchlist.py", title="觀察清單"),
    P("pages/3_個股分析_Stock_Analysis.py", title="個股分析"),
    P("pages/4_策略回測_Backtesting.py", title="策略回測"),
    P("pages/5_投資組合_Portfolio.py", title="投資組合最佳化"),
    P("pages/6_風險分析_Risk.py", title="風險分析（舊版）"),
    P("pages/8_警報系統_Alerts.py", title="警報系統"),
    P("pages/9_資料管理_Data.py", title="資料管理"),
    P("pages/10_總績效_Dashboard.py", title="總績效"),
]
lab = [
    P("views/lab_fixed_income.py", url_path="fixed-income", title="固定收益 M6", icon=":material/account_balance:"),
    P("views/lab_concept_map.py", url_path="concept-map", title="CQF 概念地圖", icon=":material/school:"),
]

sections = {f"決策流程 · {tpl_label}": flow}
if others:
    sections["其他步驟"] = others
sections.update({"工具箱": toolbox, "CQF 實驗室": lab})
nav = st.navigation(sections)
render_sidebar()
nav.run()
