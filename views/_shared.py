# -*- coding: utf-8 -*-
"""
Shared helpers for the CQF decision-flow views.

Data source order (first one that works wins, and the page shows which):
  1. DataManager (FinMind for Taiwan, Finnhub/yfinance for US) — the project's own layer
  2. yfinance directly
  3. DEMO data: simulated GARCH prices, clearly labelled. Lets you learn the models offline.
"""
from __future__ import annotations

import json
import logging
import math
import zlib
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- house style
# One look: sell-side research note — white page, deep navy + light blue, grey scale,
# compact tables, numbered figures with conclusion titles and source lines.
THEME = dict(
    bg="#FFFFFF", panel="#F5F6F7", sidebar="#FAFAFA", text="#111111", muted="#5F6368",
    rule="#BDBDBD", accent="#1F3B5C", accent2="#7399C6", gray="#9AA0A6", light="#C9D3DD",
    red="#B3261E", green="#2E7D32", grid="#ECECEC",
    font="Arial, Helvetica, 'Noto Sans TC', 'Noto Sans CJK TC', 'Microsoft JhengHei', sans-serif",
)
ACCENT, ACCENT2 = THEME["accent"], THEME["accent2"]
GRAY, LIGHT = THEME["gray"], THEME["light"]
RED, GREEN = THEME["red"], THEME["green"]          # semantic: warning / acceptable
UP, DOWN = "#C62828", "#2E7D32"                   # price direction, Taiwan convention: red up, green down
_FIG_N = [0]


def rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alpha})"


def apply_style():
    """Inject the house CSS. Called once per rerun from app.py; also resets figure numbering."""
    t = THEME
    _FIG_N[0] = 0
    st.markdown(
        f"""
        <style>
        html, body, .stApp {{font-family:{t['font']};}}
        .stApp {{background:{t['bg']};}}
        .block-container {{padding-top:4.6rem; max-width:1240px;}}
        h1, h2, h3, h1 *, h2 *, h3 * {{font-family:{t['font']} !important;}}
        h1, h2, h3 {{color:{t['text']}; font-weight:600;}}
        h1 {{font-size:1.75rem; padding-bottom:.25rem; border-bottom:none;}}
        h2, h3 {{border-bottom:1px solid {t['rule']}; padding-bottom:.2rem;}}
        [data-testid="stSidebar"] {{background:{t['sidebar']};}}
        div[data-testid="stMetric"] {{background:{t['panel']}; border:none; border-left:3px solid {t['accent']};
            border-radius:0; padding:.45rem .8rem; box-shadow:none;}}
        div[data-testid="stMetricLabel"] p {{font-size:.75rem; color:{t['muted']}; font-weight:700;}}
        div[data-testid="stMetricValue"] {{font-size:1.55rem; font-weight:700;}}
        .flow-step {{border:1px solid {t['rule']}; border-radius:0; padding:.9rem 1rem; background:{t['panel']};
            height:100%; border-top:3px solid {t['accent']};}}
        .flow-step b {{font-size:1.05rem; color:{t['text']};}}
        .muted {{color:{t['muted']}; font-size:.92rem;}}
        .tag {{display:inline-block; padding:1px 8px; border-radius:0; background:{rgba(t['accent2'], 0.12)};
            color:{t['accent']}; font-size:.75rem; margin-right:4px; letter-spacing:.03em;}}
        div[data-testid="stAlert"] {{border-radius:0;}}
        .standfirst {{color:{t['muted']}; font-size:.98rem; margin-top:-.4rem;}}
        .keypoints {{border:1px solid {t['rule']}; border-left:4px solid {t['accent']}; background:{t['panel']};
            padding:.7rem 1rem .4rem 1rem; margin:.4rem 0 1rem 0;}}
        .keypoints .kp-title {{font-weight:700; font-size:.8rem; letter-spacing:.06em; color:{t['accent']};
            margin-bottom:.2rem;}}
        .keypoints ul {{margin:0 0 .3rem 1.1rem; padding:0;}}
        .keypoints li {{margin:.18rem 0; font-size:.93rem; line-height:1.45; color:{t['text']};}}
        .keypoints li b {{color:{t['accent']};}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str = "", as_of: str | None = None):
    """Research-note masthead: product line + date rule, title, one-line standfirst."""
    t = THEME
    today = date.today().strftime("%Y-%m-%d")
    right = f"{today}" + (f"　·　資料截至 {as_of}" if as_of else "")
    st.markdown(
        f"""<div style="display:flex;justify-content:space-between;align-items:flex-end;
            border-bottom:2px solid {t['accent']};padding-bottom:4px;margin-bottom:.6rem;
            font-size:.78rem;letter-spacing:.04em;color:{t['muted']};">
            <span><b style="color:{t['accent']}">CQF 交易面板</b>　|　量化研究筆記</span><span>{right}</span></div>""",
        unsafe_allow_html=True)
    st.title(title)
    if subtitle:
        st.markdown(f'<p class="standfirst">{subtitle}</p>', unsafe_allow_html=True)


def key_points(points: list[str], title: str = "重點摘要"):
    """Boxed bullet summary that opens every research note."""
    items = "".join(f"<li>{p}</li>" for p in points if p)
    st.markdown(f"""<div class="keypoints"><div class="kp-title">{title}</div><ul>{items}</ul></div>""",
                unsafe_allow_html=True)


def source_note(src: str) -> str:
    """Turn a load_prices() label into a chart footnote."""
    if not src:
        return ""
    if src.startswith("DEMO"):
        return "資料來源：DEMO 模擬資料（GARCH 模擬），僅供學習。"
    body = src.replace("本機快取 · ", "").replace(" · 更新至 ", "，截至 ")
    return f"資料來源：{body}；CQF 交易面板計算。"


def as_of(df) -> str | None:
    try:
        return df.index[-1].strftime("%Y-%m-%d")
    except Exception:
        return None


def _numbered(title: str) -> str:
    _FIG_N[0] += 1
    return f"<b><span style='color:{THEME['accent']}'>圖 {_FIG_N[0]}</span>　{title}</b>"


def _base_layout(fig: go.Figure, title: str | None):
    t = THEME
    fig.update_layout(
        template="simple_white", paper_bgcolor=t["bg"], plot_bgcolor=t["bg"],
        font=dict(family=t["font"], size=12, color=t["text"]),
        colorway=[t["accent"], t["accent2"], t["gray"], t["light"], UP, DOWN],
        legend=dict(orientation="h", y=1.0, yanchor="bottom", x=1, xanchor="right", title=None,
                    font=dict(color=t["muted"], size=11)),
        hovermode="x unified",
    )
    if title:
        fig.update_layout(title=dict(text=_numbered(title), x=0, y=0.98, yanchor="top",
                                     font=dict(size=14, color=t["text"])))
    fig.update_xaxes(showgrid=False, linecolor=t["rule"], tickcolor=t["rule"], color=t["muted"])
    fig.update_yaxes(showgrid=True, gridcolor=t["grid"], linecolor=t["rule"], color=t["muted"], zeroline=False)


def fig_layout(fig: go.Figure, height: int = 360, title: str | None = None,
               source: str | None = None) -> go.Figure:
    """House layout for figures built in views/: numbered conclusion title + optional source line."""
    _base_layout(fig, title)
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=60 if title else 30, b=10),
                      meta={"styled": True, **({"source": source} if source else {})})
    return fig


def style_figure(fig: go.Figure) -> go.Figure:
    """
    Apply the house style to a figure built elsewhere (legacy toolbox pages): background,
    fonts, grid, palette, Taiwan-convention candlestick colours and a numbered title.
    Explicit trace colours set by the page are kept.
    """
    if isinstance(fig.layout.meta, dict) and fig.layout.meta.get("styled"):
        return fig
    title = fig.layout.title.text if fig.layout.title and fig.layout.title.text else None
    hover = fig.layout.hovermode                     # keep the page's own hover behaviour
    _base_layout(fig, title)
    fig.update_layout(margin=dict(l=10, r=10, t=70 if title else 30, b=10), hovermode=hover or "x unified")
    if "yaxis2" in fig.layout and fig.layout.yaxis2.domain is not None:
        # subplot grids carry their own panel titles at the top: move the legend below the chart
        fig.update_layout(legend=dict(y=-0.06, yanchor="top", x=0, xanchor="left"), margin=dict(b=60))
        fig.update_annotations(font=dict(size=12, color=THEME["text"]))
    fig.update_traces(increasing_line_color=UP, increasing_fillcolor=UP,
                      decreasing_line_color=DOWN, decreasing_fillcolor=DOWN, selector=dict(type="candlestick"))
    return fig


def chart(fig: go.Figure, **kwargs):
    """st.plotly_chart with the house style + the figure's source line as a caption."""
    kwargs.pop("use_container_width", None)
    style_figure(fig)
    st.plotly_chart(fig, **{"width": "stretch", **kwargs})
    meta = fig.layout.meta
    src = meta.get("source") if isinstance(meta, dict) else None
    if src:
        st.markdown(f'<div style="color:{THEME["muted"]};font-size:0.74rem;margin:-0.8rem 0 1rem 0;">{src}</div>',
                    unsafe_allow_html=True)


def pct(x: float, digits: int = 1) -> str:
    return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 100:.{digits}f}%"


def prob(x: float) -> str:
    """Probability with an honest floor instead of a misleading 0.00%."""
    if x is None or not math.isfinite(x):
        return "—"
    return "< 0.01%" if x < 1e-4 else f"{x * 100:.2f}%"


def money(v, symbol=None, d: int = 2) -> str:
    """
    Currency-aware amount. Taiwan symbols (or no symbol) -> "1,234.00 元"; US -> "US$ 1,234.00".
    `symbol` may be a list: mixed Taiwan/US lists are labelled 混合幣別 (amounts are not converted).
    """
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "—"
    syms = symbol if isinstance(symbol, (list, tuple, set)) else ([symbol] if symbol else [])
    kinds = {is_tw(str(x)) for x in syms if x}
    if kinds == {False}:
        return f"US$ {v:,.{d}f}"
    if kinds == {True, False}:
        return f"{v:,.{d}f}（混合幣別）"
    return f"{v:,.{d}f} 元"


def num(x: float, digits: int = 2) -> str:
    return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:,.{digits}f}"


def kpi(col, label: str, value: str, note: str | None = None, help: str | None = None):
    """Metric card with a neutral note underneath (st.metric's delta would add a misleading arrow)."""
    col.metric(label, value, help=help)
    if note:
        col.caption(note)


# --------------------------------------------------------------------------- CQF box
def cqf_box(module: str, what: str, why: str, formula: str, code: str, use: str):
    """Fixed note format: 這是什麼 / 為什麼重要 / 公式 / 程式位置 / 在面板怎麼用."""
    with st.expander(f"CQF 概念 · {module}", expanded=False):
        st.markdown(f"**這是什麼**　{what}")
        st.markdown(f"**為什麼重要**　{why}")
        st.markdown("**公式**")
        st.latex(formula)
        st.markdown(f"**程式位置**　`{code}`")
        st.markdown(f"**在面板怎麼用**　{use}")


# --------------------------------------------------------------------------- symbols
def is_tw(symbol: str) -> bool:
    s = symbol.upper().replace(".TWO", "").replace(".TW", "")
    return s[:4].isdigit()


def benchmark_for(symbol: str) -> str:
    """0050 for Taiwan. SPY for US; VOO (same S&P 500 index) if only VOO is cached locally."""
    if is_tw(symbol):
        return "0050"
    if not (ROOT / "data" / "prices" / "SPY.csv").exists() and (ROOT / "data" / "prices" / "VOO.csv").exists():
        return "VOO"
    return "SPY"


@st.cache_data(ttl=3600)
def load_watchlists() -> dict:
    try:
        raw = json.loads((ROOT / "config" / "watchlists.json").read_text(encoding="utf-8"))
    except Exception:
        return {"預設": {"name": "預設", "symbols": {"0050": "", "2330": "", "SPY": ""}}}
    return {k: v for k, v in raw.items() if isinstance(v, dict) and "symbols" in v}


def all_watchlist_symbols() -> list[str]:
    seen = []
    for g in load_watchlists().values():
        for s in g["symbols"]:
            if s not in seen:
                seen.append(s)
    return seen


def symbol_label(symbol: str) -> str:
    for g in load_watchlists().values():
        if symbol in g["symbols"]:
            desc = g["symbols"][symbol]
            return f"{symbol} {desc.split('—')[0].strip()}" if desc else symbol
    return symbol


# --------------------------------------------------------------------------- data
def _demo_prices(symbol: str, years: int) -> pd.DataFrame:
    """GARCH(1,1)-simulated prices so that vol clustering is visible. Deterministic per symbol."""
    n = int(years * 252) + 260
    seed = zlib.crc32(symbol.encode())  # stable across runs (hash() is salted)
    rng = np.random.default_rng(seed)
    omega, alpha, beta = 3e-6, 0.08, 0.90
    s2 = omega / (1 - alpha - beta)
    r = np.empty(n)
    for t in range(n):
        r[t] = 0.0003 + math.sqrt(s2) * rng.standard_normal()
        s2 = omega + alpha * (r[t] - 0.0003) ** 2 + beta * s2
    idx = pd.bdate_range(end=pd.Timestamp(date.today()), periods=n)
    bench = "0050" if is_tw(symbol) else "SPY"
    if symbol != bench:
        # stock = beta * market + idiosyncratic, so CAPM numbers are meaningful in DEMO mode
        m = np.log(_demo_prices(bench, years)["close"]).diff().fillna(0).values[-n:]
        beta = 0.6 + (seed % 900) / 1000            # 0.6 – 1.5, stable per symbol
        r = beta * m + 0.8 * (r - 0.0003) + 0.0001
    close = 100 * np.exp(np.cumsum(r))
    df = pd.DataFrame({"close": close}, index=idx)
    df["open"] = df["close"].shift(1).fillna(df["close"])
    spread = np.abs(rng.normal(0, 0.006, n))
    df["high"] = df[["open", "close"]].max(axis=1) * (1 + spread)
    df["low"] = df[["open", "close"]].min(axis=1) * (1 - spread)
    df["volume"] = rng.integers(1_000, 10_000, n) * 1000
    return df


def _from_datamanager(symbol, start, end) -> pd.DataFrame:
    from core.data_fetcher import DataManager
    dm = DataManager()
    df = dm.fetch_prices(symbol, start, end)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()[["open", "high", "low", "close", "volume"]]


def _from_yfinance(symbol, start, end) -> pd.DataFrame:
    import yfinance as yf
    candidates = [f"{symbol}.TW", f"{symbol}.TWO"] if is_tw(symbol) and "." not in symbol else [symbol]
    for c in candidates:
        df = yf.download(c, start=start, end=end + timedelta(days=1), auto_adjust=True, progress=False)
        if df is not None and not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.columns = [str(x).lower() for x in df.columns]
            df.index = pd.to_datetime(df.index).tz_localize(None)
            return df[["open", "high", "low", "close", "volume"]]
    return pd.DataFrame()


PRICE_DIR = ROOT / "data" / "prices"


def _local_manifest() -> dict:
    try:
        return json.loads((PRICE_DIR / "_manifest.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _from_local_csv(symbol: str, start: date) -> tuple[pd.DataFrame, str]:
    """Cache written by scripts/fetch_market_data.py (adjusted prices where available)."""
    f = PRICE_DIR / f"{symbol}.csv"
    if not f.exists():
        return pd.DataFrame(), ""
    df = pd.read_csv(f, parse_dates=["date"]).set_index("date").sort_index()
    df = df[df.index >= pd.Timestamp(start)][["open", "high", "low", "close", "volume"]]
    meta = _local_manifest().get(symbol, {})
    label = f"本機快取 · {meta.get('source', 'CSV')} · 更新至 {df.index[-1]:%Y-%m-%d}" if len(df) else ""
    return df, label


@st.cache_data(ttl=3600, show_spinner=False)
def load_prices(symbol: str, years: int = 5, allow_demo: bool = True) -> tuple[pd.DataFrame, str]:
    """Return (OHLCV frame indexed by date, source label)."""
    end = date.today()
    start = end - timedelta(days=int(years * 365.25) + 10)
    try:
        df, label = _from_local_csv(symbol, start)
        if len(df) > 60:
            return df, label
    except Exception as e:
        logger.info(f"local csv failed for {symbol}: {e}")
    for name, fn in (("FinMind/Finnhub", _from_datamanager), ("yfinance", _from_yfinance)):
        try:
            df = fn(symbol, start, end)
            if df is not None and len(df) > 60:
                df = df[~df.index.duplicated()].dropna(subset=["close"])
                return df, name
        except Exception as e:  # network, token, rate-limit …
            logger.info(f"{name} failed for {symbol}: {e}")
    if allow_demo:
        return _demo_prices(symbol, years), "DEMO 模擬資料"
    return pd.DataFrame(), "無資料"


def source_badge(source: str):
    if source.startswith("DEMO"):
        st.warning("目前使用 **DEMO 模擬資料**（GARCH 模擬）。資料源連不上時的備援。數字只供學習模型，不可用於交易決策。", icon="⚠️")
    else:
        st.caption(f"資料來源：{source}")


def symbol_picker(key: str, default: str | None = None, label: str = "標的", follow_ctx: bool = True) -> str:
    """
    Symbol selector bound to the workflow's research target (views/_state.py):
    it opens on the current target, and choosing another symbol here makes that the
    new target for every step. follow_ctx=False gives an independent picker.
    """
    from views._state import get_symbol, set_symbol
    syms = all_watchlist_symbols()
    cur = get_symbol() if follow_ctx else (default or (syms[0] if syms else "0050"))
    opts = syms + ([cur] if cur not in syms else []) + ["自訂…"]
    choice = st.selectbox(label, opts, index=opts.index(cur), key=f"{key}_sel_{cur}",
                          format_func=lambda s: s if s == "自訂…" else symbol_label(s))
    if choice == "自訂…":
        choice = st.text_input("輸入代號（台股 4 碼 / 美股代號）", value=cur, key=f"{key}_txt").strip().upper()
    if follow_ctx and choice and choice != cur:
        set_symbol(choice)
        st.rerun()
    return choice


@st.cache_data(ttl=3600)
def risk_free_rate(default: float = 0.015, tw: bool = True) -> tuple[float, str]:
    """Latest US 3M T-bill from the FRED cache for US assets; Taiwan uses a fixed default
    (Taiwan 1Y deposit rate ~1.5–1.8%; not in FRED)."""
    if tw:
        return default, "台灣：固定 1.5%（近似一年定存）"
    try:
        df = pd.read_csv(ROOT / "data" / "macro" / "DGS3MO.csv")
        return float(df["value"].iloc[-1]), f"美國 3 個月國庫券 {df['date'].iloc[-1]}（FRED）"
    except Exception:
        return default, "預設 1.5%"


def log_returns(close: pd.Series) -> pd.Series:
    return np.log(close.astype(float)).diff().dropna()
