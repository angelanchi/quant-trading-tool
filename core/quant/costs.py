# -*- coding: utf-8 -*-
"""
Transaction costs (Taiwan / US). A strategy that ignores costs is not a strategy.

Taiwan (as of 2026, verify with your broker):
  commission  0.1425% each side x broker discount, minimum NT$20 (board lot)
  securities transaction tax (sell side only):
      stocks 0.3%, ETFs 0.1%, day-trade stocks 0.15%
US: most brokers charge $0 commission; SEC/TAF fees are tiny and ignored here.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TWCostModel:
    commission_rate: float = 0.001425
    discount: float = 0.6           # e.g. 6-fold online discount
    min_fee: float = 20.0
    tax_stock: float = 0.003
    tax_etf: float = 0.001
    tax_daytrade: float = 0.0015

    def commission(self, value: float) -> float:
        return max(value * self.commission_rate * self.discount, self.min_fee) if value > 0 else 0.0

    def tax(self, value: float, is_etf: bool = False, day_trade: bool = False) -> float:
        rate = self.tax_etf if is_etf else (self.tax_daytrade if day_trade else self.tax_stock)
        return value * rate

    def round_trip(self, price_in: float, price_out: float, shares: int,
                   is_etf: bool = False, day_trade: bool = False) -> dict:
        buy_v, sell_v = price_in * shares, price_out * shares
        c_buy, c_sell = self.commission(buy_v), self.commission(sell_v)
        tax = self.tax(sell_v, is_etf, day_trade)
        total = c_buy + c_sell + tax
        gross = sell_v - buy_v
        return {"buy_commission": c_buy, "sell_commission": c_sell, "tax": tax,
                "total_cost": total, "gross_pnl": gross, "net_pnl": gross - total,
                "cost_pct_of_buy": total / buy_v if buy_v else 0.0}

    def breakeven_move(self, price: float, shares: int, is_etf: bool = False) -> float:
        """Percentage rise needed just to cover costs (approx., ignores min-fee kinks)."""
        v = price * shares
        c = self.commission(v)
        r = self.commission_rate * self.discount
        t = self.tax_etf if is_etf else self.tax_stock
        # sell value V' must satisfy V' (1 - r - t) - V - c = 0
        return float((v + c) / (v * (1 - r - t)) - 1) if v else float("nan")


def is_tw_symbol(symbol: str) -> bool:
    s = symbol.upper().replace(".TWO", "").replace(".TW", "")
    return s[:4].isdigit()


def is_tw_etf(symbol: str) -> bool:
    s = symbol.upper().replace(".TWO", "").replace(".TW", "")
    return s.startswith("00")
