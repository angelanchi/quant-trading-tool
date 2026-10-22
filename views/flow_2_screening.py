# -*- coding: utf-8 -*-
"""② 選股 Screening — CAPM alpha/beta, volatility, momentum; ML as a sanity check."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.quant import capm, volatility as qv, tw_signals as tw
from views._shared import (chart, kpi, ACCENT, ACCENT2, GRAY, LIGHT, benchmark_for, cqf_box, fig_layout, key_points,
                           load_prices, load_watchlists, log_returns, page_header, pct, source_badge, source_note,
                           symbol_label, symbol_picker)
from views._state import get_symbol, next_step, plan, set_regime, set_symbol, step_bar, update_plan, ctx

hdr = st.container()

groups = load_watchlists()
c1, c2, c3 = st.columns([2, 1, 1])
with c1:
    chosen = st.multiselect("觀察清單", list(groups), default=list(groups)[:2],
                            format_func=lambda k: groups[k].get("name", k))
with c2:
    years = st.slider("回看（年）", 2, 10, 3)
with c3:
    rf = st.number_input("無風險利率（年）", 0.0, 0.10, 0.015, 0.005, format="%.3f")

symbols = list(dict.fromkeys(s for g in chosen for s in groups[g]["symbols"]))
if not symbols:
    st.stop()


@st.cache_data(ttl=3600, show_spinner=False)
def screen(symbols: tuple, years: int, rf: float) -> tuple[pd.DataFrame, list]:
    rows, sources = [], set()
    for s in symbols:
        try:
            df, src = load_prices(s, years)
            bdf, bsrc = load_prices(benchmark_for(s), years)
            sources.update([src, bsrc])
            r, rb = log_returns(df["close"]), log_returns(bdf["close"])
            cp = capm.capm_regression(r, rb, rf)
            v = qv.best_available_vol(r)
            cyc = tw.cycle_position(df["close"])
            last1y = r.iloc[-252:]
            sharpe = (last1y.mean() * 252 - rf) / (last1y.std() * np.sqrt(252))
            rows.append({"代號": s, "名稱": symbol_label(s).replace(s, "").strip(),
                         "基準": benchmark_for(s), "β": cp.beta, "α 年化": cp.alpha_annual,
                         "α t 值": cp.alpha_t, "R²": cp.r_squared, "系統風險占比": cp.systematic_share,
                         "預測波動": v["vol_annual"], "1 年 Sharpe": sharpe,
                         "動能 12-1": cyc["momentum_12_1"], "52 週位置": cyc["pct_of_52w_range"],
                         "距 200MA": cyc["dist_ma200"]})
        except Exception as e:
            rows.append({"代號": s, "名稱": f"錯誤：{e}"})
    df = pd.DataFrame(rows)
    for c in df.columns.difference(["代號", "名稱", "基準"]):
        df[c] = pd.to_numeric(df[c], errors="coerce")   # None -> NaN so na_rep shows "—"
    return df, sorted(sources)


with st.spinner(f"計算 {len(symbols)} 檔…"):
    table, sources = screen(tuple(symbols), years, rf)
last_dates = sorted({x.split("更新至 ")[-1] for x in sources if "更新至" in x})
with hdr:
    page_header("② 選股", "把觀察清單放進同一把尺：市場風險（β）、超額報酬（α）是否顯著、波動與動能。",
                last_dates[-1] if last_dates else None)
    step_bar("screening")
if any(x.startswith("DEMO") for x in sources):
    source_badge("DEMO")
note = ("資料來源：" + "、".join(sorted({x.split(" · ")[1] if " · " in x else x for x in sources}))
        + "；基準 0050（台股）/ SPY 或 VOO（美股）；CQF 交易面板計算。")

ok_ = table.dropna(subset=["β"]) if "β" in table else pd.DataFrame()
if not ok_.empty:
    ok_ = ok_[ok_["代號"] != ok_["基準"]]
    n_sig = int((ok_["α t 值"].abs() > 2).sum())
    hb = ok_.loc[ok_["β"].idxmax()]
    hv = ok_.loc[ok_["預測波動"].idxmax()]
    hm = ok_.loc[ok_["動能 12-1"].idxmax()] if ok_["動能 12-1"].notna().any() else None
    key_points([
        (f"{len(ok_)} 檔中沒有任何一檔的 α 在統計上顯著（|t| > 2）；報酬主要來自承擔市場風險 β。" if n_sig == 0 else
         f"{len(ok_)} 檔中只有 <b>{n_sig}</b> 檔的 α 在統計上顯著（|t| > 2）；其餘報酬主要來自承擔市場風險 β。"),
        f"市場敏感度最高：<b>{hb['代號']} {hb['名稱']}</b>，β = {hb['β']:.2f}（大盤漲跌 1%，平均跟著 {hb['β']:.2f}%）。",
        f"預測波動最高：<b>{hv['代號']} {hv['名稱']}</b>，年化 {pct(hv['預測波動'])}；放進組合前先到 ④ 算部位。",
        (f"12-1 動能最強：<b>{hm['代號']} {hm['名稱']}</b>，{pct(hm['動能 12-1'])}；動能高也代表回檔風險高。"
         if hm is not None else ""),
        "含意：α 不顯著的標的，不要用「選股能力」解釋過去的報酬。",
    ])

fmt = {"β": "{:.2f}", "α 年化": "{:.1%}", "α t 值": "{:.2f}", "R²": "{:.2f}", "系統風險占比": "{:.0%}",
       "預測波動": "{:.1%}", "1 年 Sharpe": "{:.2f}", "動能 12-1": "{:.1%}", "52 週位置": "{:.0%}", "距 200MA": "{:.1%}"}
st.markdown("**表 1　觀察清單風險與報酬拆解**")
disp = table.copy()
for col, f in fmt.items():   # pre-format: st.dataframe would show NaN as "None"
    if col in disp:
        disp[col] = table[col].map(lambda v, f=f: "—" if pd.isna(v) else f.format(v))
st.dataframe(disp, width="stretch", hide_index=True)
st.caption(note)
pick_c1, pick_c2 = st.columns([3, 1])
with pick_c1:
    _cands = [x for x in table["代號"].tolist()]
    _cur = get_symbol()
    _pick = st.selectbox("選定研究標的（帶到 ③ ④ ⑥）", _cands, index=_cands.index(_cur) if _cur in _cands else 0,
                         format_func=lambda x: symbol_label(x), key=f"scr_pick_{_cur}")
with pick_c2:
    st.write("")
    if st.button("設為研究標的", type="primary", disabled=_pick == _cur):
        set_symbol(_pick)
        st.rerun()
st.caption("α t 值的絕對值 > 2 才算統計上可信。多數個股的 α 不顯著：報酬大多只是承擔市場風險（β）的回報。")

ok = table.dropna(subset=["β", "α 年化"]) if "β" in table else pd.DataFrame()
if not ok.empty:
    sig = ok["α t 值"].abs() > 2
    fig = go.Figure()
    fig.add_scatter(x=ok.loc[~sig, "β"], y=ok.loc[~sig, "α 年化"], mode="markers+text", text=ok.loc[~sig, "代號"],
                    textposition="top center", name="α 不顯著", marker=dict(color=ACCENT2, size=10, opacity=0.7))
    fig.add_scatter(x=ok.loc[sig, "β"], y=ok.loc[sig, "α 年化"], mode="markers+text", text=ok.loc[sig, "代號"],
                    textposition="top center", name="α 顯著 |t|>2", marker=dict(color=ACCENT, size=12))
    fig.add_hline(y=0, line=dict(color=GRAY, width=1))
    fig.add_vline(x=1, line=dict(color=GRAY, width=1, dash="dot"))
    fig.update_yaxes(tickformat=".0%", title="α（年化）")
    fig.update_xaxes(title="β（對基準）")
    chart(fig_layout(fig, 400, f"{int(sig.sum())} / {len(ok)} 檔 α 顯著：多數報酬來自市場風險 β", note))

cqf_box(
    "M2 CAPM 與單一指數模型",
    "把個股報酬拆成「跟著大盤動的部分（β）」和「大盤解釋不了的部分（α + 殘差）」。",
    "β 決定你實際承擔多少市場風險；α 只有在 t 值夠大時才不是運氣。",
    r"R_i-r_f=\alpha+\beta\,(R_m-r_f)+\varepsilon,\quad \sigma_i^2=\beta^2\sigma_m^2+\sigma_\varepsilon^2",
    "core/quant/capm.py · capm_regression",
    "β > 1.3 的標的在 ① 高波動體制時要降部位；α 不顯著就不要當成「選股能力」。",
)

# ---------------------------------------------------------------- ML sanity check
st.divider()
st.subheader("機器學習檢查：方向可以預測嗎？")
st.markdown('<p class="muted">用過去的特徵預測未來 N 日漲跌。只用時間順序切分，並與「最強的常數猜法」比較。</p>',
            unsafe_allow_html=True)
m1, m2, m3 = st.columns([2, 1, 1])
with m1:
    ml_sym = symbol_picker("ml")
with m2:
    horizon = st.selectbox("預測天數", [1, 5, 20], index=1)
with m3:
    model = st.selectbox("模型", ["logistic", "random_forest"],
                         format_func=lambda m: {"logistic": "邏輯迴歸", "random_forest": "隨機森林"}[m])

if st.button("執行 walk-forward 驗證", type="primary"):
    try:
        from core.quant import ml
        df, src = load_prices(ml_sym, 10)
        source_badge(src)
        with st.spinner("訓練 5 個時間切分…"):
            rep = ml.walk_forward_classify(df["close"], horizon=horizon, model=model)
        a, b, c, d = st.columns(4)
        a.metric("樣本外準確率", pct(rep.accuracy))
        b.metric("嚴格基準", pct(max(rep.baseline_accuracy, rep.hindsight_baseline)))
        kpi(c, "優勢", pct(rep.edge))
        d.metric("p 值（非重疊樣本）", f"{rep.significance():.3f}")
        (st.success if rep.verdict().startswith("有") else st.info)(rep.verdict())
        st.dataframe(rep.folds.style.format({"accuracy": "{:.1%}", "baseline": "{:.1%}"}),
                     width="stretch", hide_index=True)
        curve = ml.strategy_curve(df["close"], rep)
        fig = go.Figure()
        fig.add_scatter(x=curve.index, y=curve["buy_hold"], name="買進持有", line=dict(color=GRAY, width=1.2))
        fig.add_scatter(x=curve.index, y=curve["strategy"], name="模型說漲才持有", line=dict(color=ACCENT, width=1.6))
        chart(fig_layout(fig, 300, f"樣本外：模型準確率 {pct(rep.accuracy)} vs 嚴格基準 "
                                   f"{pct(max(rep.baseline_accuracy, rep.hindsight_baseline))}",
                                   source_note(src) + "未扣交易成本。"))
        st.caption("特徵重要性：" + "、".join(f"{k} {v:.2f}" for k, v in rep.importance.head(5).items()))
    except ImportError:
        st.error("需要 scikit-learn：python -m pip install scikit-learn")
    except ValueError as e:
        st.error(str(e))

cqf_box(
    "M4 監督式學習與交叉驗證",
    "用特徵（動能、波動、RSI…）訓練分類器，判斷未來 N 日漲或跌。",
    "金融資料雜訊大。隨機切分會偷看未來，造成虛假的高準確率。",
    r"\text{TimeSeriesSplit: train}=[0,t),\ \text{gap}=h,\ \text{test}=[t+h,\,t+h+n)",
    "core/quant/ml.py · walk_forward_classify",
    "模型打不贏基準時，不要用它下單；把它當成「市場接近隨機漫步」的證據。",
)

next_step("screening", f"研究標的 {symbol_label(get_symbol())}")
