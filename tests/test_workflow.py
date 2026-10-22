# -*- coding: utf-8 -*-
"""Workflow state: watch-list editing (on a temp file) and the ③ → ④ → ⑥ hand-over."""
import json
import shutil
from pathlib import Path

import pytest

from views import _state as S

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def wl(tmp_path):
    p = tmp_path / "watchlists.json"
    p.write_text(json.dumps({"_說明": "x", "g1": {"name": "群組一", "symbols": {"2330": "台積電"}}},
                            ensure_ascii=False), encoding="utf-8")
    return p


def test_symbol_normalise_and_validate():
    assert S.normalize_symbol(" 2330.tw ") == "2330"
    assert S.normalize_symbol("brk.b") == "BRK.B"
    for ok in ["2330", "00878", "00632R", "NVDA", "BRK.B"]:
        assert S.valid_symbol(ok), ok
    for bad in ["", "23", "台積電", "NV DA", "1234567"]:
        assert not S.valid_symbol(bad), bad


def test_add_remove_rename(wl):
    S.add_symbol("2454", "g1", "聯發科", path=wl)
    assert "2454" in S.groups(wl)["g1"]["symbols"]
    used = S.add_symbol("AMD", None, "", new_group_name="美股 半導體", path=wl)
    assert used == "美股_半導體" and S.groups(wl)[used]["symbols"]["AMD"] == "AMD"
    assert S.remove_symbol("2330", "g1", path=wl)
    assert not S.remove_symbol("2330", "g1", path=wl)
    S.rename_group("g1", "新名稱", path=wl)
    data = json.loads(wl.read_text(encoding="utf-8"))
    assert data["g1"]["name"] == "新名稱" and data["_說明"] == "x"
    with pytest.raises(KeyError):
        S.add_symbol("TSLA", "nope", path=wl)


def test_templates_reference_known_steps():
    for label, steps, _ in S.TEMPLATES.values():
        assert steps and all(k in S.STEPS for k in steps)


def test_plan_flows_pricing_to_sizing_to_journal(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    # keep the real context file untouched
    monkeypatch.setattr(S, "CTX_FILE", tmp_path / "ctx.json")
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=300)
    at.session_state["ctx"] = {"template": "research", "symbol": "0050", "regime": {"regime": "高波動",
                                                                                     "suggest_risk": 0.005},
                               "plan": {}}
    at.run()
    assert not at.exception

    at.switch_page("views/flow_3_pricing.py").run()
    assert not at.exception
    p = at.session_state["ctx"]["plan"]
    assert p["symbol"] == "0050" and p["target"] > p["entry"] > p["stop"] > 0
    assert 0 <= p["p_stop"] <= 1

    at.switch_page("views/flow_4_risk_sizing.py").run()
    assert not at.exception
    radio = [r for r in at.radio if r.label == "停損方式"][0]
    assert radio.value == "沿用 ③ 停損"
    slider = [s for s in at.slider if s.label.startswith("單筆最大虧損")][0]
    assert slider.value == pytest.approx(0.5)                    # from ① high-vol regime
    p = at.session_state["ctx"]["plan"]
    assert p["shares"] >= 0 and p["stop_mode"] == "沿用 ③ 停損"

    at.switch_page("pages/7_交易紀錄_Trade_Log.py").run()
    assert not at.exception
    sym_box = [t for t in at.text_input if t.label == "股票代碼"][0]
    assert sym_box.value == "0050"
    qty = [n for n in at.number_input if n.label == "股數"][0]
    assert qty.value == (p["shares"] or 100)
    note = [t for t in at.text_area if t.label == "備註"][0]
    assert "③ 目標" in note.value and "④" in note.value


def test_changing_symbol_resets_plan(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr(S, "CTX_FILE", tmp_path / "ctx.json")
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=300)
    at.session_state["ctx"] = {"template": "full", "symbol": "0050", "regime": {},
                               "plan": {"symbol": "0050", "target": 1.0, "stop": 0.5}}
    at.run()
    side = [s for s in at.sidebar.selectbox if s.key.startswith("side_sym_")][0]
    other = [o for o in side.options if not o.startswith("0050")][0]
    side.set_value(other.split()[0]).run()
    assert at.session_state["ctx"]["symbol"] == other.split()[0]
    assert at.session_state["ctx"]["plan"] == {}
