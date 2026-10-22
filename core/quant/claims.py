# -*- coding: utf-8 -*-
"""
說法驗證器 Claim checker — turn any return promise into a probability.

Question: "Someone says stock X will make +R% within N trading days."
Under GBM with the stock's own volatility we can ask:
  1. P(end the period at or above +R%)          (terminal probability)
  2. P(touch +R% at any time within N days)      (first-passage — the optimistic case)
  3. How many standard deviations is the move?   z = ln(1+R) / (sigma sqrt(T))
  4. Annualised equivalent                       (1+R)^(252/N) - 1
  5. Sharpe needed if +R% were the EXPECTED outcome
  6. Probability of repeating it k times in a row  p^k

This does not prove anyone is dishonest. It shows how far a promise sits from
what the stock's own volatility makes plausible.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict

from .stochastic import prob_terminal_above, prob_touch

TRADING_DAYS = 252


@dataclass
class ClaimAssessment:
    claimed_return: float
    horizon_days: int
    sigma_annual: float
    mu_annual: float
    z_score: float
    prob_end_above: float
    prob_touch: float
    annualized_equivalent: float
    required_sharpe: float
    prob_repeat: float
    repeats: int
    verdict: str

    def to_dict(self) -> dict:
        return asdict(self)


def assess_claim(claimed_return: float, horizon_days: int, sigma_annual: float,
                 mu_annual: float = 0.08, rf: float = 0.015, repeats: int = 3) -> ClaimAssessment:
    if horizon_days <= 0 or sigma_annual <= 0:
        raise ValueError("horizon and sigma must be positive")
    t = horizon_days / TRADING_DAYS
    target = 1 + claimed_return
    z = math.log(target) / (sigma_annual * math.sqrt(t))
    p_end = prob_terminal_above(1.0, target, mu_annual, sigma_annual, horizon_days)
    p_touch = prob_touch(1.0, target, mu_annual, sigma_annual, horizon_days)
    ann = target ** (TRADING_DAYS / horizon_days) - 1
    drift_needed = math.log(target) / t + 0.5 * sigma_annual ** 2
    req_sharpe = (drift_needed - rf) / sigma_annual
    p_rep = p_end ** repeats

    if p_end < 0.01:
        verdict = "極不可能：低於 1%，等同多次標準差以外的事件"
    elif p_end < 0.05:
        verdict = "不太可能：低於 5%，不應當作『預期』報酬"
    elif p_end < 0.25:
        verdict = "有可能但偏樂觀：只是機率分布的右尾"
    else:
        verdict = "在該股波動範圍內：仍不代表會發生"
    return ClaimAssessment(claimed_return, horizon_days, sigma_annual, mu_annual, z, p_end,
                           p_touch, ann, req_sharpe, p_rep, repeats, verdict)


# Checklist of behavioural red flags commonly listed in Taiwan anti-fraud
# (165) and securities-regulator investor education material.
RED_FLAGS = [
    ("guaranteed_return", "承諾具體報酬率或「穩賺」", "合法投顧不得保證獲利"),
    ("short_horizon_big_return", "短天期高報酬（例：數日 30% 以上）", "見上方機率計算"),
    ("tiered_by_capital", "依投入資金分級／分陣營，資金越多越早進場", "晚進場者常成為出貨對象"),
    ("coordinated_buying", "要求成員在指定時間一起買進同一標的", "可能涉及操縱股價（證交法 §155）"),
    ("report_funds_to_assistant", "要求向助理回報資金、帳戶或持股", "個資與資金被鎖定的前兆"),
    ("deadline_pressure", "「名額有限」「啟動後不再接受加入」", "製造急迫感，壓縮查證時間"),
    ("private_platform", "要求下載特定 App 或匯款到個人／非券商帳戶", "最常見的直接詐騙手法"),
    ("unverifiable_authority", "強調外商經歷、高額獲利截圖，但查無執照", "可於投信投顧公會查詢"),
    ("withdrawal_friction", "出金需繳保證金、稅金或手續費", "出金受阻是詐騙平台典型特徵"),
]


def red_flag_score(answers: dict) -> dict:
    hit = [f for f in RED_FLAGS if answers.get(f[0])]
    n = len(hit)
    level = "高風險" if n >= 3 else ("需警覺" if n >= 1 else "未見明顯紅旗")
    return {"count": n, "level": level, "flags": hit}
