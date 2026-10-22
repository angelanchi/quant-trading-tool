# -*- coding: utf-8 -*-
"""③ 情境定價 — GBM scenarios for a stock; Black-Scholes for options; delta hedging."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.quant import options as op, stochastic as sto, volatility as qv
from views._shared import (chart, rgba, ACCENT, GRAY, LIGHT, RED, GREEN, as_of, cqf_box, fig_layout, key_points,
                           load_prices, log_returns, num, page_header, pct, source_badge, source_note, symbol_picker)
from views._state import get_symbol, next_step, plan, set_regime, set_symbol, step_bar, update_plan, ctx

hdr = st.container()

tab_gbm, tab_bs, tab_hedge = st.tabs(["股價情境（GBM）", "選擇權定價（Black-Scholes）", "Delta 對沖模擬"])

# =================================================================== GBM
with tab_gbm:
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        sym = symbol_picker("gbm")
    with c2:
        horizon = st.slider("情境天數（交易日）", 5, 252, 60)
    with c3:
        n_paths = st.select_slider("模擬路徑數", [200, 1000, 5000], value=1000)

    df, src = load_prices(sym, 5)
    source_badge(src)
    close = df["close"]
    s0 = float(close.iloc[-1])
    r = log_returns(close)
    est = sto.estimate_gbm_params(close.iloc[-756:])
    vbest = qv.best_available_vol(r)

    p1, p2 = st.columns(2)
    with p1:
        sig_src = st.radio("波動 σ 來源", ["GARCH/EWMA 預測", "3 年歷史", "自訂"], horizontal=True)
        sigma = {"GARCH/EWMA 預測": vbest["vol_annual"], "3 年歷史": est.sigma}.get(sig_src)
        if sigma is None:
            sigma = st.number_input("σ（年化）", 0.05, 2.0, float(round(est.sigma, 2)), 0.01)
    with p2:
        mu_src = st.radio("漂移 μ 來源", ["保守 8%", "無風險 1.5%", "3 年歷史", "自訂"], horizontal=True)
        mu = {"保守 8%": 0.08, "無風險 1.5%": 0.015, "3 年歷史": est.mu}.get(mu_src)
        if mu is None:
            mu = st.number_input("μ（年化）", -1.0, 1.0, 0.08, 0.01)
    if mu_src == "3 年歷史":
        st.caption(f"提醒：歷史 μ 的估計誤差很大。{len(r.iloc[-756:])} 天資料下，μ 的標準誤約 {pct(sigma / np.sqrt(3))}。")

    t1, t2 = st.columns(2)
    _p = plan()
    target = t1.number_input("目標價", value=float(_p.get("target") or round(s0 * 1.15, 2)), min_value=0.01,
                             key=f"tgt_{sym}")
    stop = t2.number_input("停損價", value=float(_p.get("stop") or round(s0 * 0.92, 2)), min_value=0.01,
                           key=f"stp_{sym}")

    p_end = sto.prob_terminal_above(s0, target, mu, sigma, horizon)
    p_tgt = sto.prob_touch(s0, target, mu, sigma, horizon)
    p_stp = sto.prob_touch(s0, stop, mu, sigma, horizon)
    gap = sto.ito_gap(mu, sigma, horizon)
    note = source_note(src) + f" GBM：μ = {pct(mu)}，σ = {pct(sigma)}。"
    with hdr:
        page_header(f"③ 情境定價　{sym}", "不要問「會不會漲到目標價」。要問「以它自己的波動，有多大機率」。", as_of(df))
        step_bar("pricing")
    up, dn = target / s0 - 1, stop / s0 - 1
    key_points([
        f"以年化波動 <b>{pct(sigma)}</b> 計算，{horizon} 個交易日內曾觸及目標價（{pct(up)}）的機率為 <b>{pct(p_tgt)}</b>，"
        f"曾觸及停損價（{pct(dn)}）為 <b>{pct(p_stp)}</b>。",
        f"期末仍在目標價之上的機率只有 <b>{pct(p_end)}</b>；碰到不等於守得住。",
        f"報酬／風險距離比 {abs(up / dn):.2f}；" + ("停損比目標更容易先被碰到，需重新設定。" if p_stp > p_tgt
                                               else "目標被碰到的機率高於停損。"),
        f"Itô 修正：平均報酬 {pct(gap['mean_growth'])}，中位數只有 {pct(gap['median_growth'])}（波動拖累 σ²/2）。",
    ])

    update_plan(entry=round(s0, 4), target=round(float(target), 4), stop=round(float(stop), 4), horizon=int(horizon),
                p_target=round(p_tgt, 4), p_stop=round(p_stp, 4), p_end=round(p_end, 4),
                sigma=round(float(sigma), 4), mu=round(float(mu), 4))
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("現價", num(s0))
    k2.metric(f"{horizon} 天後收在目標價之上", pct(p_end))
    k3.metric("期間內曾觸及目標價", pct(p_tgt))
    k4.metric("期間內曾觸及停損價", pct(p_stp))

    paths = sto.simulate_gbm(s0, mu, sigma, horizon, n_paths, seed=42)
    days = np.arange(horizon + 1)
    cone = sto.terminal_quantiles(s0, mu, sigma, days[1:], (0.05, 0.25, 0.5, 0.75, 0.95))
    fut = pd.bdate_range(close.index[-1], periods=horizon + 1)
    hist = close.iloc[-120:]
    fig = go.Figure()
    fig.add_scatter(x=hist.index, y=hist, name="歷史", line=dict(color=GRAY, width=1.2))
    for i in range(min(30, n_paths)):
        fig.add_scatter(x=fut, y=paths[:, i], line=dict(color=LIGHT, width=0.6), showlegend=False, hoverinfo="skip")
    for lo, hi, op_ in (("q05", "q95", 0.12), ("q25", "q75", 0.22)):
        fig.add_scatter(x=fut[1:], y=cone[hi], line=dict(width=0), showlegend=False, hoverinfo="skip")
        fig.add_scatter(x=fut[1:], y=cone[lo], fill="tonexty", fillcolor=rgba(ACCENT, op_),
                        line=dict(width=0), name="90% 區間" if lo == "q05" else "50% 區間")
    fig.add_scatter(x=fut[1:], y=cone["q50"], name="中位數", line=dict(color=ACCENT, width=1.6))
    fig.add_scatter(x=fut[1:], y=cone["mean"], name="平均數", line=dict(color=ACCENT, width=1, dash="dot"))
    fig.add_hline(y=target, line=dict(color=GREEN, dash="dash", width=1.5), layer="above", annotation_text="目標")
    fig.add_hline(y=stop, line=dict(color=RED, dash="dash", width=1.5), layer="above", annotation_text="停損")
    chart(fig_layout(fig, 420, f"{horizon} 日 90% 區間 {num(cone['q05'].iloc[-1])} – {num(cone['q95'].iloc[-1])}；"
                               f"觸停損機率 {pct(p_stp)}", note))
    st.markdown(f"**Itô 修正**：平均報酬 {pct(gap['mean_growth'])}，但中位數只有 {pct(gap['median_growth'])}。"
                f"差距來自波動拖累 σ²/2 = {pct(gap['volatility_drag_annual'])}／年。波動越大，『典型』結果越差。")

    cqf_box(
        "M1 幾何布朗運動與 Itô 引理",
        "假設對數報酬是常態、獨立、固定波動的隨機過程。",
        "它把「目標價」轉成機率，並解釋為什麼高波動股票的中位數表現較差。",
        r"dS=\mu S\,dt+\sigma S\,dW\ \Rightarrow\ S_T=S_0\,e^{(\mu-\frac{\sigma^2}{2})T+\sigma W_T}",
        "core/quant/stochastic.py · prob_terminal_above, prob_touch, terminal_quantiles",
        "觸及停損的機率若高於觸及目標，表示停損太近或目標太遠。GBM 低估跳空與肥尾，結果請當作上限參考。",
    )

# =================================================================== Black-Scholes
with tab_bs:
    st.markdown('<p class="muted">台指選擇權、美股選擇權皆適用（歐式）。輸入市場價可反推隱含波動。</p>', unsafe_allow_html=True)
    a1, a2, a3, a4, a5 = st.columns(5)
    S = a1.number_input("標的價 S", value=100.0, min_value=0.01)
    K = a2.number_input("履約價 K", value=100.0, min_value=0.01)
    days_left = a3.number_input("到期日曆天數", value=30, min_value=1)
    r_ = a4.number_input("利率 r", value=0.015, format="%.3f")
    sig = a5.number_input("波動 σ", value=0.25, min_value=0.01, format="%.3f")
    kind = st.radio("類型", ["call", "put"], horizontal=True, format_func=lambda k: "買權 Call" if k == "call" else "賣權 Put")
    T = days_left / 365
    g = op.bs_greeks(S, K, T, r_, sig, kind=kind)
    cols = st.columns(6)
    for c, (lab, key, d) in zip(cols, [("理論價", "price", 3), ("Delta", "delta", 3), ("Gamma", "gamma", 4),
                                      ("Vega / 1 vol 點", "vega", 3), ("Theta / 日", "theta", 3), ("Rho / 1%", "rho", 3)]):
        c.metric(lab, f"{g[key]:.{d}f}")

    mkt = st.number_input("市場報價（選填，反推隱含波動）", value=0.0, min_value=0.0)
    if mkt > 0:
        iv = op.implied_vol(mkt, S, K, T, r_, kind=kind)
        st.metric("隱含波動 IV", pct(iv) if np.isfinite(iv) else "無解（違反無套利邊界）")

    grid = np.linspace(S * 0.7, S * 1.3, 121)
    vals = [op.bs_price(x, K, T, r_, sig, kind=kind) for x in grid]
    deltas = [op.bs_greeks(x, K, T, r_, sig, kind=kind)["delta"] for x in grid]
    b1, b2 = st.columns(2)
    with b1:
        fig = go.Figure()
        fig.add_scatter(x=grid, y=op.payoff(grid, K, kind), name="到期損益", line=dict(color=GRAY, dash="dot"))
        fig.add_scatter(x=grid, y=vals, name="今日理論價", line=dict(color=ACCENT))
        chart(fig_layout(fig, 300, "價值曲線"))
    with b2:
        fig = go.Figure(go.Scatter(x=grid, y=deltas, line=dict(color=ACCENT), name="Delta"))
        chart(fig_layout(fig, 300, "Delta 隨標的價變化（斜率 = Gamma）"))

    cqf_box(
        "M3 Black-Scholes 與 Greeks",
        "在無套利與連續對沖假設下，選擇權價格是標的價、波動、時間、利率的函數。",
        "Greeks 告訴你部位對每個因子的敏感度，是選擇權風險管理的語言。",
        r"C=S e^{-qT}N(d_1)-K e^{-rT}N(d_2),\quad d_{1,2}=\frac{\ln(S/K)+(r-q\pm\frac{\sigma^2}{2})T}{\sigma\sqrt T}",
        "core/quant/options.py · bs_price, bs_greeks, implied_vol",
        "比較 IV 與 ① 的 GARCH 預測波動：IV 明顯高於預測時，選擇權相對貴。",
    )

# =================================================================== Delta hedging
with tab_hedge:
    st.markdown('<p class="muted">賣出一口買權並做 Delta 對沖。看兩件事：對沖次數與「實際波動 vs 定價波動」。</p>',
                unsafe_allow_html=True)
    h1, h2, h3, h4 = st.columns(4)
    iv_ = h1.number_input("定價用波動（IV）", value=0.20, format="%.2f")
    rv_ = h2.number_input("實際波動", value=0.20, format="%.2f")
    n_reb = h3.select_slider("到期前對沖次數", [4, 12, 26, 52, 252], value=52)
    hd = h4.number_input("到期天數（日曆）", value=91, min_value=7)
    res = op.delta_hedge_simulation(100, 100, hd / 365, 0.015, iv_, rv_, n_rebalance=n_reb, n_paths=3000)
    m1, m2, m3 = st.columns(3)
    m1.metric("收到權利金", num(res["premium"]))
    m2.metric("平均對沖損益", num(res["mean"]))
    m3.metric("損益標準差", num(res["std"]))
    fig = go.Figure(go.Histogram(x=res["pnl"], nbinsx=60, marker_color=ACCENT, opacity=0.8))
    fig.add_vline(x=0, line=dict(color=GRAY))
    chart(fig_layout(fig, 300, "對沖後損益分布（每口，標的 = 100）"))
    st.info("對沖次數加 4 倍，標準差約減半（∝ 1/√N）。實際波動 > 定價波動時，賣方平均虧損：你把波動賣得太便宜。")
    cqf_box(
        "M3 Delta 對沖與波動率套利",
        "持有 −Δ 股標的抵銷選擇權對價格的一階風險。",
        "BS 價格正是「完美連續對沖」的成本。離散對沖留下的誤差，就是真實世界的風險。",
        r"\text{P\&L}\approx\tfrac12\sum_i \Gamma_i S_i^2\left(\sigma_{\text{real}}^2-\sigma_{\text{imp}}^2\right)\Delta t",
        "core/quant/options.py · delta_hedge_simulation",
        "理解為什麼「賣選擇權收租」在波動突然放大時會出現大虧損。",
    )

_pl = plan()
next_step("pricing", (f"目標 {_pl['target']:,.2f}、停損 {_pl['stop']:,.2f}、觸價機率 "
                      f"{_pl['p_target']:.0%} / {_pl['p_stop']:.0%} → ④ 計算股數") if _pl.get("target") else "")
