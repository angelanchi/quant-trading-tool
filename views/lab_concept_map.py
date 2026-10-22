# -*- coding: utf-8 -*-
"""CQF 實驗室 · 概念地圖 — every CQF topic → where it lives in the panel and in the code."""
import pandas as pd
import streamlit as st

from views._shared import page_header  # noqa: E402

page_header("CQF 概念地圖", "讀 CQF 教材時，用這張表找到對應的面板與程式碼，邊讀邊操作。")

rows = [
    ("M1", "布朗運動、隨機漫步", "③ 情境定價", "core/quant/stochastic.py", "simulate_gbm"),
    ("M1", "Itô 引理、波動拖累 σ²/2", "③ 情境定價", "core/quant/stochastic.py", "ito_gap"),
    ("M1", "首次通過時間（反射原理）", "③ ⑤", "core/quant/stochastic.py", "prob_touch"),
    ("M2", "波動群聚、EWMA、GARCH(1,1)", "① 盤勢", "core/quant/volatility.py", "fit_garch11"),
    ("M2", "VaR、ES、Cornish-Fisher", "④ 風險與部位", "core/quant/var.py", "var_*"),
    ("M2", "VaR 回測：Kupiec、Christoffersen", "④ 風險與部位", "core/quant/var.py", "backtest_var"),
    ("M2", "CAPM、β、Jensen α", "② 選股", "core/quant/capm.py", "capm_regression"),
    ("M2", "Markowitz、效率前緣、Black-Litterman", "工具箱 · 投資組合最佳化", "core/optimizer.py", "PortfolioOptimizer"),
    ("M2", "風險貢獻分解", "④ 風險與部位", "views/flow_4_risk_sizing.py", "—"),
    ("M2", "Kelly 準則", "④ 風險與部位", "core/quant/sizing.py", "kelly_fraction"),
    ("M3", "Black-Scholes、Put-Call parity", "③ 情境定價", "core/quant/options.py", "bs_price"),
    ("M3", "Greeks、隱含波動", "③ 情境定價", "core/quant/options.py", "bs_greeks, implied_vol"),
    ("M3", "Delta 對沖、波動套利", "③ 情境定價", "core/quant/options.py", "delta_hedge_simulation"),
    ("M3", "協整、配對交易", "工具箱 · 策略回測", "strategies/pairs_trading.py", "—"),
    ("M4", "特徵工程、分類、時序交叉驗證", "② 選股", "core/quant/ml.py", "walk_forward_classify"),
    ("M4", "過擬合與 walk-forward", "工具箱 · 策略回測", "core/walk_forward.py", "—"),
    ("M6", "債券價格、Duration、Convexity", "CQF 實驗室", "core/quant/fixed_income.py", "bond_risk"),
    ("M6", "Vasicek 短率模型", "CQF 實驗室", "core/quant/fixed_income.py", "vasicek_zcb"),
    ("實務", "台股交易成本", "④ 風險與部位", "core/quant/costs.py", "TWCostModel"),
    ("實務", "結算日事件研究", "① 盤勢", "core/quant/tw_signals.py", "event_study"),
]
df = pd.DataFrame(rows, columns=["CQF 模組", "主題", "面板位置", "程式檔", "函式"])
mods = st.multiselect("篩選模組", sorted(df["CQF 模組"].unique()), default=sorted(df["CQF 模組"].unique()))
st.dataframe(df[df["CQF 模組"].isin(mods)], hide_index=True, width="stretch")

st.subheader("建議的閱讀與操作順序（尚未入學）")
st.markdown(
    """
1. **機率與對數報酬** → ③ 看價格錐，改 σ，觀察中位數與平均數的差距。
2. **波動率** → ① 比較 GARCH 與 20 日實現波動，理解 α、β、半衰期。
3. **風險度量** → ④ 計算持股 VaR，再看回測是否通過。
4. **CAPM** → ② 看哪些 α 的 t 值真的大於 2。
5. **選擇權** → ③ 用 Hull 範例（S=42, K=40, r=10%, σ=20%, T=0.5）驗證 Call = 4.76。
6. **機器學習** → ② 跑 walk-forward，學會接受「沒有預測力」的結果。
"""
)
st.caption("測試：tests/test_quant.py 以教科書數值驗證每個公式。執行：python -m pytest tests/test_quant.py -v")
