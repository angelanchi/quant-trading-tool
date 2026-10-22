# -*- coding: utf-8 -*-
"""CQF 實驗室 · M6 固定收益 — bond price, duration, convexity, Vasicek."""
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from core.quant import fixed_income as fi
from views._shared import chart, ACCENT, GRAY, LIGHT, cqf_box, fig_layout, num, pct

from views._shared import page_header  # noqa: E402

page_header("固定收益 M6", "債券價格對利率的敏感度：Duration 是一階，Convexity 是二階。")

tab_b, tab_v = st.tabs(["債券與利率風險", "Vasicek 利率模型"])

with tab_b:
    c = st.columns(5)
    face = c[0].number_input("面額", value=100.0)
    cpn = c[1].number_input("票面利率", value=0.04, format="%.3f")
    ytm = c[2].number_input("殖利率 YTM", value=0.045, format="%.3f")
    yrs = c[3].number_input("年期", value=10.0, min_value=0.5, step=0.5)
    freq = c[4].selectbox("每年付息", [1, 2, 4], index=1)
    rk = fi.bond_risk(face, cpn, ytm, yrs, freq)
    m = st.columns(5)
    m[0].metric("價格", num(rk["price"], 3))
    m[1].metric("Macaulay Duration", f"{rk['macaulay_duration']:.2f} 年")
    m[2].metric("Modified Duration", f"{rk['modified_duration']:.2f}")
    m[3].metric("Convexity", f"{rk['convexity']:.1f}")
    m[4].metric("DV01", num(rk["dv01"], 4), help="殖利率變動 1bp 的價格變動")

    dys = np.linspace(-0.03, 0.03, 61)
    true = [fi.bond_price(face, cpn, ytm + d, yrs, freq) / rk["price"] - 1 for d in dys]
    dur = [fi.price_change_approx(rk, d)["duration_only"] for d in dys]
    cvx = [fi.price_change_approx(rk, d)["with_convexity"] for d in dys]
    fig = go.Figure()
    fig.add_scatter(x=dys, y=true, name="實際價格變化", line=dict(color=ACCENT, width=2))
    fig.add_scatter(x=dys, y=dur, name="只用 Duration", line=dict(color=GRAY, dash="dot"))
    fig.add_scatter(x=dys, y=cvx, name="Duration + Convexity", line=dict(color=LIGHT, dash="dash"))
    fig.update_xaxes(tickformat=".1%", title="殖利率變動")
    fig.update_yaxes(tickformat=".0%", title="價格變化")
    chart(fig_layout(fig, 360, "利率變動越大，越需要 Convexity 修正"))

with tab_v:
    c = st.columns(4)
    r0 = c[0].number_input("目前短率 r0", value=0.02, format="%.3f")
    a = c[1].number_input("回歸速度 a", value=0.3, min_value=0.01)
    b = c[2].number_input("長期水準 b", value=0.035, format="%.3f")
    s = c[3].number_input("波動 σ", value=0.01, format="%.3f")
    curve = fi.vasicek_yield_curve(r0, a, b, s)
    paths = fi.simulate_vasicek(r0, a, b, s, years=5, n_paths=100, steps_per_year=52)
    l, r = st.columns(2)
    with l:
        fig = go.Figure(go.Scatter(x=curve.index, y=curve.values, mode="lines+markers", line=dict(color=ACCENT)))
        fig.update_yaxes(tickformat=".2%")
        fig.update_xaxes(title="到期（年）")
        chart(fig_layout(fig, 320, "模型隱含零息殖利率曲線"))
    with r:
        t = np.arange(paths.shape[0]) / 52
        fig = go.Figure()
        for i in range(40):
            fig.add_scatter(x=t, y=paths[:, i], line=dict(color=LIGHT, width=0.6), showlegend=False, hoverinfo="skip")
        fig.add_scatter(x=t, y=paths.mean(axis=1), name="平均", line=dict(color=ACCENT))
        fig.add_hline(y=b, line=dict(color=GRAY, dash="dot"), annotation_text="長期水準 b")
        fig.update_yaxes(tickformat=".1%")
        chart(fig_layout(fig, 320, "短率模擬：均值回歸"))
    st.caption(f"負利率機率（5 年後）：{pct(float((paths[-1] < 0).mean()))}。Vasicek 允許負利率，這是它的已知缺點（CIR 模型可避免）。")

cqf_box(
    "M6 債券定價與利率模型",
    "Duration 衡量價格對殖利率的一階敏感度；Vasicek 描述會回到長期水準的短期利率。",
    "股票投資人也受利率影響：折現率上升會壓低成長股估值。",
    r"\frac{\Delta P}{P}\approx -D_{mod}\,\Delta y+\tfrac12 C\,(\Delta y)^2,\qquad dr=a(b-r)\,dt+\sigma\,dW",
    "core/quant/fixed_income.py",
    "觀察 ① 的大盤波動時，對照美債殖利率變化；長存續期資產對升息最敏感。",
)
