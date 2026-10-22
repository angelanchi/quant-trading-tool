# -*- coding: utf-8 -*-
"""
Workflow state shared by every page.

    ctx = {
      "template": "full",                    # which workflow template is active
      "symbol":   "2330",                    # the research target used by ①–⑥
      "regime":   {...},                     # written by ①  (risk-budget suggestion)
      "plan":     {...},                     # written by ③ (target/stop/probabilities) and ④ (shares/entry)
    }

The context lives in st.session_state and is mirrored to data/session_ctx.json,
so a browser refresh or app restart keeps the current research target and plan.

Also here: watch-list editing (add / remove / create group) and the on-demand
price download for newly added symbols.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
CTX_FILE = ROOT / "data" / "session_ctx.json"
WATCHLIST_FILE = ROOT / "config" / "watchlists.json"
PRICE_DIR = ROOT / "data" / "prices"

# --------------------------------------------------------------------------- steps & templates
# key -> (title, script path, url path, icon)
STEPS = {
    "regime":      ("① 盤勢", "views/flow_1_regime.py", "regime", ":material/monitoring:"),
    "screening":   ("② 選股", "views/flow_2_screening.py", "screening", ":material/filter_alt:"),
    "pricing":     ("③ 情境定價", "views/flow_3_pricing.py", "pricing", ":material/show_chart:"),
    "risk-sizing": ("④ 風險與部位", "views/flow_4_risk_sizing.py", "risk-sizing", ":material/shield:"),
    "claim-check": ("⑤ 說法驗證", "views/flow_5_claim_check.py", "claim-check", ":material/fact_check:"),
    "journal":     ("⑥ 執行與覆盤", "pages/7_交易紀錄_Trade_Log.py", "journal", ":material/edit_note:"),
}

# key -> (label, ordered steps, one-line purpose)
TEMPLATES = {
    "full":      ("完整流程", ["regime", "screening", "pricing", "risk-sizing", "claim-check", "journal"],
                  "從盤勢到下單紀錄，走完六個步驟。"),
    "premarket": ("每日盤前檢查", ["regime", "risk-sizing"],
                  "看今天市場有多危險，再檢查持股組合的 VaR。"),
    "research":  ("新標的研究", ["screening", "pricing", "risk-sizing", "journal"],
                  "比較標的 → 估算目標價機率 → 算部位 → 記錄交易。"),
    "review":    ("持股覆盤", ["journal", "risk-sizing"],
                  "回顧已做的交易，再看目前組合的風險。"),
}
DEFAULT_CTX = {"template": "full", "symbol": "0050", "regime": {}, "plan": {}}


# --------------------------------------------------------------------------- context
def _load_ctx_file() -> dict:
    try:
        data = json.loads(CTX_FILE.read_text(encoding="utf-8"))
        return {**DEFAULT_CTX, **{k: v for k, v in data.items() if k in DEFAULT_CTX}}
    except Exception:
        return dict(DEFAULT_CTX)


def ctx() -> dict:
    if "ctx" not in st.session_state:
        st.session_state["ctx"] = _load_ctx_file()
    return st.session_state["ctx"]


def save_ctx():
    try:
        CTX_FILE.parent.mkdir(parents=True, exist_ok=True)
        CTX_FILE.write_text(json.dumps(ctx(), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    except Exception:
        pass  # persistence is a convenience, never a reason to break the page


def get_symbol() -> str:
    return ctx().get("symbol") or DEFAULT_CTX["symbol"]


def set_symbol(symbol: str):
    symbol = (symbol or "").strip().upper()
    c = ctx()
    if symbol and symbol != c.get("symbol"):
        c["symbol"] = symbol
        if c.get("plan", {}).get("symbol") != symbol:
            c["plan"] = {}                      # a plan belongs to one symbol
        save_ctx()


def plan() -> dict:
    """The current plan, only if it belongs to the current research target."""
    p = ctx().get("plan") or {}
    return p if p.get("symbol") == get_symbol() else {}


def update_plan(**values):
    c = ctx()
    p = c.get("plan") or {}
    if p.get("symbol") != get_symbol():
        p = {"symbol": get_symbol()}
    changed = any(p.get(k) != v for k, v in values.items())
    if changed:
        p.update(values)
        p["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        c["plan"] = p
        save_ctx()


def set_regime(**values):
    c = ctx()
    if any(c.get("regime", {}).get(k) != v for k, v in values.items()):
        c["regime"] = {**c.get("regime", {}), **values, "updated": datetime.now().strftime("%Y-%m-%d %H:%M")}
        save_ctx()


def reset_plan():
    ctx()["plan"] = {}
    save_ctx()


def template_steps() -> list[str]:
    return TEMPLATES.get(ctx().get("template"), TEMPLATES["full"])[1]


# --------------------------------------------------------------------------- watch lists
def read_watchlists(path: Path = WATCHLIST_FILE) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_watchlists(data: dict, path: Path = WATCHLIST_FILE):
    data["_更新日期"] = datetime.now().strftime("%Y-%m-%d")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        from views._shared import load_watchlists
        load_watchlists.clear()
    except Exception:
        pass


def groups(path: Path = WATCHLIST_FILE) -> dict:
    return {k: v for k, v in read_watchlists(path).items() if isinstance(v, dict) and "symbols" in v}


SYMBOL_RE = re.compile(r"^(\d{4,6}[A-Z]?|[A-Z][A-Z0-9.\-]{0,9})$")


def normalize_symbol(raw: str) -> str:
    s = (raw or "").strip().upper()
    for suffix in (".TWO", ".TW"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    return s


def valid_symbol(sym: str) -> bool:
    return bool(SYMBOL_RE.match(sym or ""))


def add_symbol(sym: str, group_key: str, desc: str = "", new_group_name: str = "",
               path: Path = WATCHLIST_FILE) -> str:
    """Add to a group (creating it when new_group_name is given). Returns the group key used."""
    data = read_watchlists(path)
    if new_group_name.strip():
        group_key = re.sub(r"\s+", "_", new_group_name.strip())
        data.setdefault(group_key, {"name": new_group_name.strip(), "description": "", "symbols": {}})
    if group_key not in data or not isinstance(data[group_key], dict):
        raise KeyError(f"群組不存在：{group_key}")
    data[group_key].setdefault("symbols", {})[sym] = desc.strip() or sym
    write_watchlists(data, path)
    return group_key


def remove_symbol(sym: str, group_key: str, path: Path = WATCHLIST_FILE) -> bool:
    data = read_watchlists(path)
    syms = data.get(group_key, {}).get("symbols", {})
    if sym in syms:
        del syms[sym]
        write_watchlists(data, path)
        return True
    return False


def rename_group(group_key: str, new_name: str, path: Path = WATCHLIST_FILE):
    data = read_watchlists(path)
    if group_key in data and new_name.strip():
        data[group_key]["name"] = new_name.strip()
        write_watchlists(data, path)


def has_price_data(sym: str) -> bool:
    f = PRICE_DIR / f"{sym}.csv"
    return f.exists() and f.stat().st_size > 1000


def fetch_symbol_data(sym: str, timeout: int = 180) -> tuple[bool, str]:
    """Download prices for one symbol with scripts/fetch_market_data.py (stdlib only)."""
    script = ROOT / "scripts" / "fetch_market_data.py"
    try:
        out = subprocess.run([sys.executable, "-X", "utf8", str(script), sym, "--workers", "1"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace",
                             timeout=timeout, cwd=str(ROOT))
        log = (out.stdout or "") + (out.stderr or "")
    except subprocess.TimeoutExpired:
        return False, "下載逾時。"
    except Exception as e:
        return False, f"無法執行下載程式：{e}"
    ok = has_price_data(sym) and f"OK   {sym}" in log
    return ok, log.strip()[-600:]


# --------------------------------------------------------------------------- sidebar
def _symbol_options() -> list[str]:
    seen = []
    for g in groups().values():
        for s in g["symbols"]:
            if s not in seen:
                seen.append(s)
    cur = get_symbol()
    if cur not in seen:
        seen.insert(0, cur)
    return seen


def _label(sym: str) -> str:
    for g in groups().values():
        if sym in g["symbols"]:
            d = g["symbols"][sym]
            return f"{sym} {d.split('—')[0].strip()}" if d and d != sym else sym
    return sym


def render_sidebar():
    """Workflow template, research target, carried plan, and watch-list editing."""
    c = ctx()
    sb = st.sidebar
    sb.markdown("**工作流程**")
    keys = list(TEMPLATES)
    t = sb.selectbox("工作流程範本", keys, index=keys.index(c.get("template", "full")),
                     format_func=lambda k: TEMPLATES[k][0], label_visibility="collapsed", key="tpl_sel")
    if t != c.get("template"):
        c["template"] = t
        save_ctx()
        st.rerun()
    sb.caption(TEMPLATES[t][2])

    sb.markdown("**研究標的**")
    opts = _symbol_options()
    cur = get_symbol()
    choice = sb.selectbox("研究標的", opts, index=opts.index(cur), format_func=_label,
                          label_visibility="collapsed", key=f"side_sym_{cur}")
    if choice != cur:
        set_symbol(choice)
        st.rerun()

    p = plan()
    rg = c.get("regime") or {}
    items = []
    if rg.get("regime"):
        items.append(f"盤勢：{rg['regime']}（建議單筆風險 {rg.get('suggest_risk', 0.01) * 100:.1f}%）")
    if p.get("target"):
        items.append(f"③ 目標 {p['target']:,.2f}／停損 {p.get('stop', 0):,.2f}")
    if p.get("shares"):
        items.append(f"④ {p['shares']:,} 股 @ {p.get('entry', 0):,.2f}")
    with sb.expander("本次決策紀錄", expanded=bool(items)):
        if items:
            for it in items:
                st.markdown(f"- {it}")
            if st.button("清除本次計畫", key="plan_reset"):
                reset_plan()
                st.rerun()
        else:
            st.caption("尚無帶出的結果。完成 ③、④ 後會出現在這裡。")

    with sb.expander("＋ 新增觀測代號"):
        _add_symbol_form()
    with sb.expander("管理觀察清單"):
        _manage_form()


def _add_symbol_form():
    g = groups()
    raw = st.text_input("代號", placeholder="例如 2382、00919、AMD", key="add_sym_raw")
    desc = st.text_input("說明（選填）", placeholder="例如 廣達 — AI 伺服器", key="add_sym_desc")
    opts = list(g) + ["__new__"]
    gk = st.selectbox("加入群組", opts, format_func=lambda k: "＋ 建立新群組" if k == "__new__" else g[k].get("name", k),
                      key="add_sym_group")
    new_name = st.text_input("新群組名稱", key="add_sym_newgroup") if gk == "__new__" else ""
    as_target = st.checkbox("加入後設為研究標的", value=True, key="add_sym_target")
    if st.button("驗證並加入", type="primary", key="add_sym_btn"):
        sym = normalize_symbol(raw)
        if not valid_symbol(sym):
            st.error("代號格式不正確。台股 4–6 碼數字，美股英文代號。")
            return
        if gk == "__new__" and not new_name.strip():
            st.error("請輸入新群組名稱。")
            return
        with st.spinner(f"下載 {sym} 的還原權值價格…"):
            ok, log = (True, "已有資料") if has_price_data(sym) else fetch_symbol_data(sym)
        if not ok:
            st.error(f"找不到 {sym} 的價格資料，未加入。請確認代號是否正確。")
            with st.expander("下載紀錄"):
                st.code(log or "（無輸出）")
            return
        used = add_symbol(sym, None if gk == "__new__" else gk, desc, new_name if gk == "__new__" else "")
        if as_target:
            set_symbol(sym)
        st.success(f"已加入 {sym} → {groups().get(used, {}).get('name', used)}；每週排程也會自動更新它。")
        st.rerun()


def _manage_form():
    g = groups()
    if not g:
        st.caption("尚無群組。")
        return
    gk = st.selectbox("群組", list(g), format_func=lambda k: g[k].get("name", k), key="mg_group")
    syms = list(g[gk]["symbols"])
    if syms:
        rm = st.selectbox("移除代號", syms, format_func=_label, key="mg_rm")
        if st.button("從此群組移除", key="mg_rm_btn"):
            remove_symbol(rm, gk)
            st.rerun()
    new_name = st.text_input("群組改名", value=g[gk].get("name", gk), key=f"mg_name_{gk}")
    if new_name != g[gk].get("name", gk) and st.button("儲存名稱", key="mg_name_btn"):
        rename_group(gk, new_name)
        st.rerun()


# --------------------------------------------------------------------------- step bar / next step
def step_bar(current: str):
    """Shows the active template's steps with the current one highlighted."""
    from views._shared import THEME
    steps = template_steps()
    if current not in steps:
        st.caption(f"此步驟不在「{TEMPLATES[ctx()['template']][0]}」範本中，可從側欄切換範本。")
        return
    p, rg = plan(), ctx().get("regime") or {}
    finished = {"regime": bool(rg.get("regime")), "pricing": bool(p.get("target")),
                "risk-sizing": "shares" in p}          # steps that leave a result in the context
    chips = []
    for i, k in enumerate(steps):
        title = STEPS[k][0]
        on = k == current
        done = finished.get(k, False) and not on
        style = (f"background:{THEME['accent']};color:#fff;" if on else
                 f"background:{THEME['panel']};color:{THEME['accent'] if done else THEME['muted']};")
        chips.append(f"<span style='{style}padding:3px 10px;font-size:.8rem;margin-right:4px;"
                     f"border:1px solid {THEME['rule']};'>{'✓ ' if done else ''}{title}</span>")
    st.markdown(f"<div style='margin:-.2rem 0 .8rem 0'>"
                f"<span style='font-size:.75rem;color:{THEME['muted']};margin-right:8px'>"
                f"{TEMPLATES[ctx()['template']][0]}</span>{''.join(chips)}</div>", unsafe_allow_html=True)


def next_step(current: str, carried: str = ""):
    """Bottom-of-page link to the next step of the active template."""
    steps = template_steps()
    st.divider()
    if carried:
        st.caption(f"已帶到下一步：{carried}")
    if current in steps and steps.index(current) < len(steps) - 1:
        nxt = steps[steps.index(current) + 1]
        st.page_link(STEPS[nxt][1], label=f"下一步：{STEPS[nxt][0]}　→", icon=":material/arrow_forward:")
    elif current in steps:
        st.caption("這是此範本的最後一步。")
