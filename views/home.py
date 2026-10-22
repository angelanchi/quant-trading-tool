# -*- coding: utf-8 -*-
"""Home: the decision flow at a glance."""
import streamlit as st

from views._shared import page_header  # noqa: E402

page_header("CQF 交易面板", "每一個買賣決定，都走同一條流程。每一步都用一個 CQF 模型，並顯示它的假設。")

from views._shared import key_points, symbol_label  # noqa: E402
from views._state import STEPS, TEMPLATES, ctx, get_symbol, plan  # noqa: E402

_c = ctx()
_label, _steps, _purpose = TEMPLATES.get(_c.get("template"), TEMPLATES["full"])
_pl = plan()
key_points([
    f"目前工作流程：<b>{_label}</b>（{' → '.join(STEPS[k][0] for k in _steps)}）。{_purpose}",
    f"研究標的：<b>{symbol_label(get_symbol())}</b>。在任何步驟更換標的，其他步驟會一起更新。",
    ("已帶出的計畫：" + "、".join(x for x in [
        f"目標 {_pl['target']:,.2f}" if _pl.get("target") else "",
        f"停損 {_pl['stop']:,.2f}" if _pl.get("stop") else "",
        f"{_pl['shares']:,} 股" if _pl.get("shares") else ""] if x)) if _pl else "尚未建立計畫：從第一步開始。",
    "左側欄可切換範本、更換研究標的、新增觀測代號（自動下載資料）。",
], title="目前進度")
st.page_link(STEPS[_steps[0]][1], label=f"開始：{STEPS[_steps[0]][0]}　→", icon=":material/play_arrow:")
st.write("")

steps = [
    ("① 盤勢", "現在市場有多危險？", "GARCH 波動體制、週期位置、結算日", "M1 M2", "views/flow_1_regime.py"),
    ("② 選股", "哪些標的值得看？", "CAPM α/β、波動、動能、ML 驗證", "M2 M4", "views/flow_2_screening.py"),
    ("③ 情境定價", "目標價有多可能？", "GBM 價格錐、觸價機率、BS/Greeks", "M1 M3", "views/flow_3_pricing.py"),
    ("④ 風險與部位", "該買多少？", "部位大小、交易成本、VaR 回測", "M2", "views/flow_4_risk_sizing.py"),
    ("⑤ 說法驗證", "別人說的報酬可信嗎？", "把承諾轉成發生機率", "M1 M2", "views/flow_5_claim_check.py"),
    ("⑥ 執行與覆盤", "做了什麼？對不對？", "交易紀錄與事後比對", "全模組", "pages/7_交易紀錄_Trade_Log.py"),
]
cols = st.columns(3)
for i, (name, q, models, mod, path) in enumerate(steps):
    with cols[i % 3]:
        st.markdown(
            f'<div class="flow-step"><b>{name}</b><br><span class="muted">{q}</span><br>'
            f'<span style="font-size:0.88rem">{models}</span><br><span class="tag">CQF {mod}</span></div>',
            unsafe_allow_html=True)
        st.page_link(path, label=f"前往 {name}")
    if i == 2:
        st.write("")
        cols = st.columns(3)

st.divider()
st.subheader("CQF 覆蓋度")
st.markdown(
    """
| CQF 模組 | 面板位置 | 狀態 |
|---|---|---|
| M1 隨機過程、Itô | ③ 情境定價、⑤ 說法驗證 | GBM 精確解、觸價機率 |
| M2 風險與回報 | ① ② ④ | GARCH、CAPM、VaR 回測、Kelly；最佳化在「工具箱」 |
| M3 股票與選擇權 | ③ 情境定價 | Black-Scholes、Greeks、隱含波動、Delta 對沖 |
| M4 資料科學 | ② 選股 | Walk-forward 分類，與嚴格基準比較 |
| M5 深度學習 | — | 刻意未做：日頻樣本不足，先通過 M4 驗證 |
| M6 固定收益 | CQF 實驗室 | 債券、Duration、Convexity、Vasicek |
"""
)
st.caption("設計說明：docs/CQF_PANEL_REDESIGN.md　·　原有頁面在左側「工具箱」，功能不變。")

st.divider()
st.subheader("資料狀態")
from views._shared import _local_manifest  # noqa: E402

man = _local_manifest()
if man:
    import pandas as pd  # noqa: E402
    tbl = pd.DataFrame(man).T.reset_index().rename(columns={"index": "代號", "source": "來源", "rows": "筆數",
                                                              "first": "起", "last": "迄", "fetched": "下載時間"})
    st.dataframe(tbl, hide_index=True, width="stretch")
else:
    st.info("尚未下載真實資料。面板目前會嘗試即時 API，失敗時改用 DEMO 模擬資料。")

if st.button("更新真實資料（Yahoo 還原權值 + FinMind 備援 + FRED 利率）"):
    import subprocess  # noqa: E402
    import sys  # noqa: E402
    from pathlib import Path  # noqa: E402

    script = Path(__file__).resolve().parent.parent / "scripts" / "fetch_market_data.py"
    with st.spinner("下載中，約 1–3 分鐘…"):
        out = subprocess.run([sys.executable, "-X", "utf8", str(script)], capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
    st.code((out.stdout or "") + (out.stderr or ""), language="text")
    st.cache_data.clear()
    st.success("完成。所有頁面已改用新資料。")
st.caption("也可在終端機執行：run.bat fetch")
