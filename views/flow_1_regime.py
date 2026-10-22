# -*- coding: utf-8 -*-
"""① 盤勢 Market regime — how dangerous is the market right now?"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.quant import volatility as qv, tw_signals as tw
from views._shared import (chart, ACCENT, ACCENT2, GRAY, LIGHT, as_of, cqf_box, fig_layout, is_tw, key_points, kpi,
                           load_prices, log_returns, page_header, pct, source_badge, source_note)
from views._state import get_symbol, next_step, plan, set_regime, set_symbol, step_bar, update_plan, ctx

hdr = st.container()          # masthead is filled after data loads, but renders first
c1, c2 = st.columns([2, 1])
with c1:
    market = st.selectbox("市場代表", ["0050", "VOO", "QQQ", "自訂…"],
                          format_func=lambda s: {"0050": "0050 台股大盤代理", "VOO": "VOO 美股大盤（S&P 500）",
                                                 "QQQ": "QQQ 美股科技"}.get(s, s))
    if market == "自訂…":
        market = st.text_input("代號", "2330").strip().upper()
with c2:
    years = st.slider("歷史長度（年）", 3, 15, 8)

df, src = load_prices(market, years)
close = df["close"]
r = log_returns(close)
note = source_note(src)

with st.spinner("擬合 GARCH(1,1)…"):
    best = qv.best_available_vol(r)
cond_vol = np.sqrt(best["series_var"] * 252)
rv20 = qv.realized_vol(r, 20)
regime = qv.vol_regime(best["vol_annual"], cond_vol)
cyc = tw.cycle_position(close)
g = best["garch"]
study = tw.event_study(r, tw.third_wednesdays(r.index[0], r.index[-1]))
nxt = tw.next_settlement()

# ---------------------------------------------------------------- masthead + key points
with hdr:
    page_header(f"① 盤勢　{market}", "先看市場整體。波動高時，同樣的部位風險更大。", as_of(df))
    step_bar("regime")
source_badge(src)

high_vol = regime["regime"] in ("高波動", "極端")
set_regime(market=market, regime=regime["regime"], percentile=round(regime["percentile"], 1),
           vol=round(best["vol_annual"], 4), suggest_risk=0.005 if high_vol else 0.01, as_of=as_of(df))
pts = [
    f"明日預測波動 <b>{pct(best['vol_annual'])}</b>（{best['model']}），位於自身歷史第 "
    f"<b>{regime['percentile']:.0f}</b> 百分位，屬於「{regime['regime']}」。",
    f"價格{'高於' if cyc['above_ma200'] else '低於'} 200 日均線 <b>{pct(abs(cyc['dist_ma200']))}</b>，"
    f"距 52 週高點 {pct(cyc['drawdown_from_52w_high'])}。",
]
if g is not None:
    ts = g.term_structure_annual()
    direction = "回升" if ts.iloc[-1] > ts.iloc[0] else "回落"
    pts.append(f"GARCH 預期未來一年平均波動{direction}至 <b>{pct(ts.iloc[-1])}</b>，長期水準 {pct(g.long_run_vol_annual)}；"
               f"衝擊半衰期約 {g.half_life_days:.0f} 個交易日。")
if np.isfinite(study.get("p_value", np.nan)):
    pts.append(f"結算日｜報酬｜為平日的 <b>{study['ratio']:.2f} 倍</b>（p = {study['p_value']:.2f}，"
               f"{'顯著' if study['significant_5pct'] else '不顯著'}）。")
pts.append("含意：" + ("波動偏高，④ 的單筆風險預算建議由 1% 降至 0.5%。" if high_vol
                     else "波動未偏高，④ 維持一般風險預算（約 1%）。"))
key_points(pts)

# ---------------------------------------------------------------- KPIs
k1, k2, k3, k4 = st.columns(4)
k1.metric("明日預測波動（年化）", pct(best["vol_annual"]), help=f"模型：{best['model']}")
kpi(k2, "波動體制", regime["regime"], f"歷史第 {regime['percentile']:.0f} 百分位")
kpi(k3, "距 52 週高點", pct(cyc["drawdown_from_52w_high"]))
kpi(k4, "相對 200 日均線", pct(cyc["dist_ma200"]), "均線之上" if cyc["above_ma200"] else "均線之下")

# ---------------------------------------------------------------- charts
ma200 = close.rolling(200).mean()
fig = go.Figure()
fig.add_scatter(x=close.index, y=close, name="收盤（還原）", line=dict(color=ACCENT, width=1.4))
fig.add_scatter(x=ma200.index, y=ma200, name="200 日均線", line=dict(color=ACCENT2, width=1.2))
trend = f"價格{'位於' if cyc['above_ma200'] else '跌破'} 200 日均線{'之上' if cyc['above_ma200'] else ''} {pct(abs(cyc['dist_ma200']))}"
chart(fig_layout(fig, 300, trend, note))

fig = go.Figure()
fig.add_scatter(x=rv20.index, y=rv20, name="20 日實現波動", line=dict(color=LIGHT, width=1))
fig.add_scatter(x=cond_vol.index, y=cond_vol, name=f"{best['model']} 條件波動", line=dict(color=ACCENT, width=1.5))
fig.update_yaxes(tickformat=".0%")
chart(fig_layout(fig, 300, f"目前波動 {pct(best['vol_annual'])}，位於歷史第 {regime['percentile']:.0f} 百分位",
                           note))

if g is not None:
    a, b = st.columns([1, 1])
    with a:
        fig = go.Figure(go.Scatter(x=[str(h) for h in ts.index], y=ts.values, mode="lines+markers",
                                   line=dict(color=ACCENT), name="GARCH 預測"))
        fig.add_hline(y=g.long_run_vol_annual, line=dict(color=GRAY, dash="dot"),
                      annotation_text="長期平均", annotation_position="bottom right")
        fig.update_yaxes(tickformat=".1%")
        fig.update_xaxes(title="未來交易日數")
        chart(fig_layout(fig, 300, f"波動預期{direction}至長期 {pct(g.long_run_vol_annual)}",
                                   "資料來源：GARCH(1,1) 擬合；CQF 交易面板計算。"))
    with b:
        st.markdown("**表 1　GARCH(1,1) 參數**")
        st.table(pd.DataFrame({
            "值": [f"{g.alpha:.3f}", f"{g.beta:.3f}", f"{g.persistence:.3f}",
                  f"{g.half_life_days:.0f} 天", pct(g.long_run_vol_annual)],
            "意義": ["新衝擊的影響", "舊波動的記憶", "持續性 α+β（<1 才會回到平均）",
                   "衝擊衰減一半所需時間", "長期平均波動"]},
            index=["α", "β", "α+β", "半衰期", "長期波動"]))
        st.caption(note)

# ---------------------------------------------------------------- settlement study
st.subheader("結算日效應：用資料驗證")
st.markdown('<p class="muted">常聽說「結算日波動大」。這裡用歷史資料檢查它是否成立。</p>', unsafe_allow_html=True)
s1, s2, s3 = st.columns(3)
kpi(s1, "下次台指期結算（約）", nxt.strftime("%Y-%m-%d"),
    f"{np.busday_count(pd.Timestamp.today().date(), nxt.date())} 個工作天後")
if np.isfinite(study.get("p_value", np.nan)):
    kpi(s2, "結算日 |報酬| ÷ 平日", f"{study['ratio']:.2f} 倍", f"樣本 {study['n_events']} 次")
    kpi(s3, "Welch t 檢定 p 值", f"{study['p_value']:.3f}", "顯著 (p<0.05)" if study["significant_5pct"] else "不顯著")
    if study["significant_5pct"]:
        st.success("此標的在結算日的波動顯著較大。結算週可考慮降低部位或放寬停損。")
    else:
        st.info("此標的的結算日波動與平日沒有顯著差異。「結算日必有大波動」在這段資料中不成立。")
if not is_tw(market):
    st.caption("注意：結算日是台指期規則；美股標的的檢定僅供對照。")
st.caption("結算日以每月第三個星期三近似，遇假日順延到下一交易日。未納入台灣國定假日表。")

cqf_box(
    "M2 波動率模型（GARCH）",
    "用昨天的報酬與昨天的波動，預測今天的波動。",
    "常態分布、固定波動的模型會低估危機時的風險。VaR、部位大小、選擇權定價都依賴波動預測。",
    r"\sigma_t^2=\omega+\alpha\,r_{t-1}^2+\beta\,\sigma_{t-1}^2,\quad \bar\sigma^2=\frac{\omega}{1-\alpha-\beta}",
    "core/quant/volatility.py · fit_garch11, best_available_vol",
    "波動體制高於 75 百分位時，在 ④ 把每筆風險預算調低；體制回落再恢復。",
)

next_step("regime", f"盤勢「{regime['regime']}」→ ④ 單筆風險預設 {'0.5%' if high_vol else '1%'}")
