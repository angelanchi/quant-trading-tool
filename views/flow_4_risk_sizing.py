# -*- coding: utf-8 -*-
"""④ 風險與部位 — position sizing, costs, Kelly, portfolio VaR with backtests."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.quant import costs as qc, sizing as qs, var as qvar, volatility as qv
from views._shared import (chart, kpi, ACCENT, ACCENT2, GRAY, LIGHT, RED, cqf_box, fig_layout, is_tw, key_points,
                           load_prices, load_watchlists, log_returns, num, page_header, pct, source_badge,
                           source_note, symbol_label, symbol_picker)
from views._state import get_symbol, next_step, plan, set_regime, set_symbol, step_bar, update_plan, ctx

page_header("④ 風險與部位", "先決定「最多願意虧多少」，再算出可以買多少。不是反過來。")
step_bar("risk-sizing")

tab_pos, tab_var = st.tabs(["單筆部位大小", "投資組合 VaR 與回測"])

# =================================================================== position sizing
with tab_pos:
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        sym = symbol_picker("size")
    capital = c2.number_input("總資金", value=1_000_000, step=50_000, min_value=10_000)
    _rg = ctx().get("regime") or {}
    _default_risk = float(_rg.get("suggest_risk", 0.01)) * 100
    risk_pct = c3.slider("單筆最大虧損（% 總資金）", 0.25, 3.0, _default_risk, 0.25,
                         help=f"預設值來自 ① 盤勢：{_rg.get('regime', '未執行')}") / 100

    df, src = load_prices(sym, 3)
    source_badge(src)
    entry = float(df["close"].iloc[-1])
    r = log_returns(df["close"])
    vb = qv.best_available_vol(r)

    d1, d2, d3, d4 = st.columns(4)
    _p = plan()
    _modes = (["沿用 ③ 停損"] if _p.get("stop") else []) + ["波動停損", "ATR 停損", "手動"]
    stop_mode = d1.radio("停損方式", _modes, key=f"stopmode_{sym}")
    k = d2.slider("幾個標準差 / ATR", 1.0, 4.0, 2.0, 0.5)
    hold = d3.slider("預計持有（交易日）", 1, 60, 10)
    if is_tw(sym):
        lot = d4.radio("交易單位", [1000, 1], format_func=lambda x: "整股 1000" if x == 1000 else "零股 1")
    else:
        lot = 1
    if stop_mode == "沿用 ③ 停損":
        stop = float(_p["stop"])
    elif stop_mode == "波動停損":
        stop = qs.vol_stop(entry, vb["vol_annual"], k, hold)
    elif stop_mode == "ATR 停損":
        stop = entry - k * float(qs.atr(df).iloc[-1])
    else:
        stop = st.number_input("停損價", value=round(entry * 0.93, 2))
    max_w = st.slider("單一標的最大權重", 0.05, 1.0, 0.25, 0.05)

    try:
        pos = qs.fixed_fractional_shares(capital, risk_pct, entry, stop, lot_size=lot, max_weight=max_w)
        update_plan(entry=round(entry, 4), stop=round(float(stop), 4), shares=int(pos["shares"]),
                    loss_at_stop=round(pos["loss_at_stop"], 2), risk_pct=risk_pct, capital=capital,
                    stop_mode=stop_mode)
        tw_model = qc.TWCostModel()
        is_etf = qc.is_tw_etf(sym)
        rt = (tw_model.round_trip(entry, entry, pos["shares"], is_etf=is_etf)
              if is_tw(sym) and pos["shares"] > 0 else None)
        key_points([
            f"{sym} 以 {stop_mode}設在 <b>{num(stop)}</b>（{pct(stop / entry - 1)}），單筆風險 {pct(risk_pct, 2)} 的資金"
            f" → 建議 <b>{pos['shares']:,} 股</b>，占總資金 {pct(pos['weight'])}。",
            f"觸及停損的最大虧損約 <b>{num(pos['loss_at_stop'], 0)}</b> 元（未含跳空）。",
            (f"台股來回交易成本約 {num(rt['total_cost'], 0)} 元（{pct(rt['cost_pct_of_buy'], 2)}），"
             f"至少要漲 {pct(tw_model.breakeven_move(entry, pos['shares'], is_etf), 2)} 才打平。" if rt else ""),
            f"預測年化波動 {pct(vb['vol_annual'])}（{vb['model']}）。" + ("股數被最大權重上限截斷。" if pos["capped_by_max_weight"] else ""),
        ])
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("進場價（最新收盤）", num(entry))
        kpi(k2, "停損價", num(stop), pct(stop / entry - 1))
        kpi(k3, "建議股數", f"{pos['shares']:,}", f"權重 {pct(pos['weight'])}")
        kpi(k4, "觸停損虧損", num(pos["loss_at_stop"], 0), pct(-pos["loss_at_stop"] / capital, 2))
        if pos["capped_by_max_weight"]:
            st.caption("股數被「單一標的最大權重」限制。")
        if pos["shares"] == 0:
            st.warning("風險預算不足一個交易單位。可改零股，或放寬停損與風險比例。")
        if rt:
            st.markdown(
                f"**台股交易成本**（手續費 6 折、{'ETF 稅 0.1%' if is_etf else '證交稅 0.3%'}）："
                f"來回約 {num(rt['total_cost'], 0)} 元 = {pct(rt['cost_pct_of_buy'], 2)}。"
                f"至少要漲 {pct(tw_model.breakeven_move(entry, pos['shares'], is_etf), 2)} 才打平。")
    except ValueError as e:
        st.error(str(e))

    st.divider()
    st.subheader("Kelly：最多該押多少？")
    kc1, kc2 = st.columns([1, 2])
    with kc1:
        mu_k = st.number_input("你預期的年化報酬 μ", value=0.10, format="%.2f")
        rf_k = st.number_input("無風險利率", value=0.015, format="%.3f")
        frac = st.select_slider("Kelly 比例", [0.25, 0.5, 1.0], value=0.5,
                                format_func=lambda x: {0.25: "1/4", 0.5: "1/2", 1.0: "全"}[x])
        f_star = qs.kelly_fraction(mu_k, vb["vol_annual"], rf_k)
        st.metric("全 Kelly 槓桿", f"{f_star:.2f} 倍")
        st.metric(f"建議（{frac:g} Kelly）", f"{max(f_star * frac, 0):.2f} 倍")
    with kc2:
        curve = qs.kelly_curve(mu_k, vb["vol_annual"], rf_k)
        fig = go.Figure(go.Scatter(x=curve["fraction"], y=curve["growth"], line=dict(color=ACCENT)))
        fig.add_vline(x=f_star, line=dict(color=GRAY, dash="dot"), annotation_text="f*")
        fig.add_hline(y=rf_k, line=dict(color=LIGHT), annotation_text="無風險")
        fig.update_xaxes(title="槓桿（部位 ÷ 資金）")
        fig.update_yaxes(title="長期年化成長率", tickformat=".0%")
        s2 = vb["vol_annual"] ** 2
        f_zero = ((mu_k - rf_k) + np.sqrt((mu_k - rf_k) ** 2 + 2 * rf_k * s2)) / s2  # g(f) = 0
        chart(fig_layout(fig, 320, f"槓桿超過 {f_zero:.1f} 倍，長期成長率轉為負值",
                                   f"假設：μ = {pct(mu_k)}，σ = {pct(vb['vol_annual'])}（{vb['model']}）。"))
    st.caption(f"σ 使用 {vb['model']} 預測 {pct(vb['vol_annual'])}。μ 的估計誤差很大，實務上用 1/4–1/2 Kelly。")

    cqf_box(
        "M2 部位大小與 Kelly 準則",
        "固定風險法：停損距離決定股數。Kelly：最大化長期對數成長的槓桿。",
        "多數散戶虧損來自部位過大，不是選錯股票。",
        r"\text{shares}=\frac{\text{capital}\times\text{risk\%}}{\text{entry}-\text{stop}},\qquad f^*=\frac{\mu-r}{\sigma^2}",
        "core/quant/sizing.py · fixed_fractional_shares, kelly_fraction；core/quant/costs.py",
        "① 顯示高波動時，風險比例從 1% 降到 0.5%；股數會自動變少。",
    )

# =================================================================== portfolio VaR
with tab_var:
    groups = load_watchlists()
    g = st.selectbox("投資組合（觀察清單）", list(groups), format_func=lambda k: groups[k].get("name", k))
    syms = list(groups[g]["symbols"])
    w_in = st.text_input("權重（逗號分隔，留空 = 等權）", "")
    try:
        w = np.array([float(x) for x in w_in.split(",")]) if w_in.strip() else np.ones(len(syms))
        assert len(w) == len(syms)
    except Exception:
        st.error(f"需要 {len(syms)} 個數字。改用等權。")
        w = np.ones(len(syms))
    w = w / w.sum()
    cl = st.radio("信賴水準", [0.95, 0.99], index=1, horizontal=True, format_func=lambda x: f"{x:.0%}")
    value = st.number_input("組合市值", value=1_000_000, step=100_000)

    rets, srcs = {}, set()
    for s in syms:
        d, sname = load_prices(s, 6)
        srcs.add(sname)
        rets[s] = log_returns(d["close"])
    R = pd.DataFrame(rets).dropna()
    if any(x.startswith("DEMO") for x in srcs):
        source_badge("DEMO")
    port = pd.Series(np.log((np.exp(R) - 1) @ w + 1), index=R.index, name="port")

    vb = qv.best_available_vol(port)
    note = "資料來源：" + "、".join(sorted({x.split(" · ")[1] if " · " in x else x for x in srcs})) + "；CQF 交易面板計算。"
    bt_h = qvar.backtest_var(port, qvar.rolling_var_forecasts(port, cl, "historical"), cl)
    v_hist, v_norm = qvar.var_historical(port, cl), qvar.var_normal(port, cl)
    cov = R.cov().values * 252
    sig_p = float(np.sqrt(w @ cov @ w))
    contrib = w * (cov @ w) / sig_p
    top = int(np.argmax(contrib))
    key_points([
        f"{cl:.0%} 一日 VaR（歷史法）<b>{pct(v_hist, 2)}</b>，約 <b>{num(v_hist * value, 0)}</b> 元；"
        f"超過時平均虧損（ES）{pct(qvar.es_historical(port, cl), 2)}。",
        f"常態假設的 VaR 為 {pct(v_norm, 2)}，{'低估' if v_norm < v_hist else '高於'}歷史法；"
        f"超額峰態 {port.kurt():.1f}，代表肥尾。",
        f"歷史法回測：實際突破 <b>{bt_h['kupiec']['exceptions']}</b> 次，預期 {bt_h['kupiec']['expected']:.0f} 次，"
        f"Kupiec {'拒絕' if bt_h['kupiec']['reject_at_5pct'] else '通過'}（p = {bt_h['kupiec']['p_value']:.3f}）。",
        f"風險貢獻最大：<b>{symbol_label(syms[top])}</b>，資金 {pct(w[top])}、風險 {pct(contrib[top] / sig_p)}。",
    ])
    table = pd.DataFrame({
        "方法": ["歷史模擬", "常態參數", "Cornish-Fisher（偏態/峰態修正）", f"{vb['model']} 條件"],
        "1 日 VaR": [qvar.var_historical(port, cl), qvar.var_normal(port, cl), qvar.var_cornish_fisher(port, cl),
                    qvar.var_from_sigma(vb["vol_annual"] / np.sqrt(252), cl)],
    })
    table["金額"] = table["1 日 VaR"] * value
    st.markdown("**表 1　一日 VaR：四種方法比較**")
    st.dataframe(table.style.format({"1 日 VaR": "{:.2%}", "金額": "{:,.0f}"}), hide_index=True, width="stretch")
    st.caption(f"ES（超過 VaR 時的平均虧損，歷史法）：{pct(qvar.es_historical(port, cl), 2)}。"
               f"偏態 {port.skew():.2f}、超額峰態 {port.kurt():.2f}（常態 = 0）。")

    # risk contribution
    rc = pd.DataFrame({"權重": w, "風險貢獻": contrib / sig_p}, index=[symbol_label(s) for s in syms])
    fig = go.Figure()
    fig.add_bar(y=rc.index, x=rc["權重"], name="資金權重", orientation="h", marker_color=ACCENT2)
    fig.add_bar(y=rc.index, x=rc["風險貢獻"], name="風險貢獻", orientation="h", marker_color=ACCENT)
    fig.update_xaxes(tickformat=".0%")
    chart(fig_layout(fig, 90 + 32 * len(syms), f"{symbol_label(syms[top])} 以 {pct(w[top])} 資金貢獻 "
                               f"{pct(contrib[top] / sig_p)} 風險", note))

    st.subheader("VaR 回測：模型誠實嗎？")
    method = st.radio("回測哪個模型", ["historical", "normal", "ewma"], horizontal=True,
                      format_func=lambda m: {"historical": "歷史 250 日", "normal": "常態 250 日", "ewma": "EWMA"}[m])
    fc = qvar.rolling_var_forecasts(port, cl, method)
    bt = qvar.backtest_var(port, fc, cl)
    fr, hits = bt["frame"], bt["hits"]
    fig = go.Figure()
    fig.add_scatter(x=fr.index, y=fr["r"], name="每日報酬", mode="lines", line=dict(color=LIGHT, width=0.8))
    fig.add_scatter(x=fr.index, y=-fr["var"], name="−VaR", line=dict(color=ACCENT, width=1.2))
    ex = fr[hits == 1]
    fig.add_scatter(x=ex.index, y=ex["r"], name="突破", mode="markers", marker=dict(color=RED, size=5))
    fig.update_yaxes(tickformat=".0%")
    k, c = bt["kupiec"], bt["christoffersen"]
    chart(fig_layout(fig, 340, f"實際突破 {k['exceptions']} 次 vs 預期 {k['expected']:.0f} 次："
                               f"{'模型低估風險' if k['exceptions'] > k['expected'] and k['reject_at_5pct'] else '模型大致誠實'}",
                               note))
    b1, b2, b3, b4 = st.columns(4)
    kpi(b1, "突破次數", f"{k['exceptions']}", f"預期 {k['expected']:.1f}")
    kpi(b2, "Kupiec p 值（次數）", f"{k['p_value']:.3f}", "拒絕" if k["reject_at_5pct"] else "通過")
    kpi(b3, "Christoffersen p 值（群聚）", f"{c['p_value']:.3f}", "拒絕" if c["reject_at_5pct"] else "通過")
    b4.metric("Basel 燈號（近 250 日）", bt["traffic_light_last_250"])

    cqf_box(
        "M2 VaR、Expected Shortfall 與回測",
        "在給定信賴水準下，一天內最大可能虧損；ES 是超過 VaR 時的平均虧損。",
        "VaR 只是一個模型輸出。不回測，就不知道它是否低估了風險。",
        r"\text{VaR}_{\alpha}=-\,q_{1-\alpha}(r),\quad LR_{POF}=-2\ln\frac{(1-p)^{n-x}p^x}{(1-\hat p)^{n-x}\hat p^{x}}\sim\chi^2_1",
        "core/quant/var.py · rolling_var_forecasts, backtest_var",
        "若 Kupiec 或 Christoffersen 拒絕，換用條件模型（EWMA/GARCH）或改用 ES 管控部位。",
    )

_pl = plan()
next_step("risk-sizing", (f"{_pl.get('symbol')}：{_pl['shares']:,} 股 @ {_pl.get('entry', 0):,.2f}，停損 "
                          f"{_pl.get('stop', 0):,.2f} → ⑥ 交易表單已預填") if _pl.get("shares") else "")
