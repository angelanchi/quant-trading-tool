# -*- coding: utf-8 -*-
"""⑤ 說法驗證 — turn any return promise into a probability, plus a red-flag checklist."""
import numpy as np
import plotly.graph_objects as go
import streamlit as st
from scipy.stats import norm

from core.quant import claims, volatility as qv
from views._shared import (chart, rgba, prob, ACCENT, GRAY, RED, cqf_box, fig_layout, key_points, load_prices,
                           log_returns, page_header, pct, source_badge, source_note, symbol_picker)
from views._state import get_symbol, next_step, plan, set_regime, set_symbol, step_bar, update_plan, ctx

page_header("⑤ 說法驗證", "老師、社團、新聞說「幾天賺幾成」？先把它換算成機率，再決定要不要相信。")
step_bar("claim-check")

c1, c2, c3 = st.columns(3)
claim = c1.number_input("宣稱報酬（%）", value=30.0, step=5.0) / 100
days = c2.number_input("宣稱天數（交易日）", value=5, min_value=1, max_value=756)
repeats = c3.number_input("宣稱連續成功幾次", value=3, min_value=1, max_value=20)

s1, s2 = st.columns([2, 1])
with s1:
    mode = st.radio("波動來源", ["用某檔標的的實際波動", "自訂"], horizontal=True)
with s2:
    mu = st.number_input("假設年化漂移 μ", value=0.08, format="%.2f",
                         help="偏樂觀的長期股票報酬。改大不會讓短期高報酬變得可信。")
if mode == "自訂":
    sigma = st.slider("年化波動 σ", 0.10, 1.50, 0.40, 0.05)
    sym_txt = "自訂波動"
    src = ""
else:
    sym = symbol_picker("claim")
    df, src = load_prices(sym, 3)
    source_badge(src)
    sigma = qv.best_available_vol(log_returns(df["close"]))["vol_annual"]
    sym_txt = f"{sym} 的預測波動"

a = claims.assess_claim(claim, int(days), sigma, mu, repeats=int(repeats))
ann_txt = f"{a.annualized_equivalent * 100:,.0f}%" if a.annualized_equivalent < 1e6 else "超過 1 億 %"
key_points([
    f"宣稱「{days} 個交易日 {pct(claim, 0)}」，相當於 <b>{a.z_score:.1f} 個標準差</b>的移動（σ = {pct(sigma)}，{sym_txt}）。",
    f"期末達標機率 <b>{prob(a.prob_end_above)}</b>；即使只要盤中碰到一次，機率也只有 {prob(a.prob_touch)}。",
    f"換算年化報酬 {ann_txt}；若這是「預期」報酬，需要 Sharpe {a.required_sharpe:,.1f}（頂尖基金長期約 1–2）。",
    f"連續 {a.repeats} 次都達標的機率：<b>{prob(a.prob_repeat)}</b>。",
    f"判讀：{a.verdict}。",
])

k1, k2, k3, k4 = st.columns(4)
k1.metric("期末達標機率", prob(a.prob_end_above))
k2.metric("期間內曾經碰到", prob(a.prob_touch), help="最樂觀的解讀：只要盤中碰到一次就算。")
k3.metric("相當於幾個標準差", f"{a.z_score:.1f} σ")
k4.metric(f"連續 {a.repeats} 次都達標", prob(a.prob_repeat))

(st.error if a.prob_end_above < 0.05 else st.info)(f"**判讀**：{a.verdict}")

e1, e2 = st.columns(2)
e1.metric("換算年化報酬", f"{a.annualized_equivalent * 100:,.0f}%" if a.annualized_equivalent < 1e6 else "> 1 億 %")
e2.metric("若這是「預期」報酬，需要的 Sharpe", f"{a.required_sharpe:,.1f}",
          help="長期 Sharpe 2 以上已是頂尖。大盤長期約 0.3–0.5。")

# distribution of N-day log returns
t = days / 252
m = (mu - 0.5 * sigma ** 2) * t
s = sigma * np.sqrt(t)
x = np.linspace(m - 4.5 * s, max(m + 4.5 * s, np.log(1 + claim) * 1.1), 400)
fig = go.Figure()
fig.add_scatter(x=np.exp(x) - 1, y=norm.pdf(x, m, s), fill="tozeroy", line=dict(color=ACCENT),
                fillcolor=rgba(ACCENT, 0.12), name=f"{days} 日報酬分布")
fig.add_vline(x=claim, line=dict(color=RED, dash="dash", width=2), layer="above", annotation_text="宣稱報酬")
fig.update_xaxes(tickformat=".0%", title=f"{days} 個交易日報酬（σ = {pct(sigma)}，{sym_txt}）")
fig.update_yaxes(showticklabels=False)
chart(fig_layout(fig, 330, f"宣稱報酬位於分布右尾 {a.z_score:.1f}σ 處，期末達標機率 {prob(a.prob_end_above)}",
                           (source_note(src) if src else "假設：自訂波動。") + " 分布為 GBM 對數常態假設。"))

st.caption("GBM 低估肥尾，真實極端事件機率可能高幾倍。但即使放大 10 倍，『穩定、重複』達成仍不合理。"
           "單一股票短期大漲確實會發生；可疑的是「事前保證」與「每次都中」。")

st.divider()
st.subheader("行為紅旗檢查")
st.markdown('<p class="muted">數學只回答「多不可能」。下列行為特徵回答「是否該保持距離」。</p>', unsafe_allow_html=True)
answers = {}
cols = st.columns(2)
for i, (key, text, note) in enumerate(claims.RED_FLAGS):
    with cols[i % 2]:
        answers[key] = st.checkbox(text, help=note, key=f"rf_{key}")
score = claims.red_flag_score(answers)
if score["count"] >= 3:
    st.error(f"**{score['level']}**：勾選 {score['count']} 項。不要匯款、不要下載對方指定的 App、不要提供帳戶資料。"
             "可撥 165 反詐騙諮詢專線，並到中華民國證券投資信託暨顧問商業同業公會網站查詢投顧執照。")
elif score["count"] >= 1:
    st.warning(f"**{score['level']}**：勾選 {score['count']} 項。先查證對方的合法執照與資金流向。")
else:
    st.success(score["level"])

cqf_box(
    "M1 機率思維 · M2 風險調整報酬",
    "用標的自己的波動，把「幾天賺幾成」換成 GBM 下的發生機率與所需 Sharpe。",
    "報酬承諾必須和風險一起看。沒有波動數字的報酬承諾無法評估。",
    r"z=\frac{\ln(1+R)}{\sigma\sqrt{T}},\quad P(S_T\ge S_0(1+R))=N\!\left(\frac{(\mu-\frac{\sigma^2}{2})T-\ln(1+R)}{\sigma\sqrt T}\right)",
    "core/quant/claims.py · assess_claim, RED_FLAGS",
    "任何外部建議先過這一頁。機率低於 5% 的承諾，不要當成預期報酬。",
)

next_step("claim-check")
