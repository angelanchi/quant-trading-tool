# -*- coding: utf-8 -*-
"""
Fundamental Alerts Module (基本面警報模組)

擴充原有的 AlertManager，新增基本面觸發條件：

1. 月營收警報（台股）：YoY 連續衰退、突然暴增/暴跌
2. VIX 恐慌警報：恐慌指數突破門檻
3. 總經轉折警報：殖利率曲線倒掛、CPI 超預期
4. EPS Surprise 警報：財報公布後 EPS 大幅優於/差於預期
5. 綜合體檢警報：一鍵掃描整個觀察清單的基本面狀態

這個模組設計為「可獨立使用」也可以「插入現有 AlertManager」。

Usage:
    from core.fundamental_alerts import FundamentalAlertChecker

    checker = FundamentalAlertChecker()

    # 掃描單檔股票
    alerts = checker.check_stock('2330')

    # 掃描整個觀察清單
    report = checker.scan_watchlist(['2330', '2454', 'AAPL', 'NVDA'])

    # 整合進現有 AlertManager
    from core.alerts import AlertManager
    am = AlertManager()
    checker.register_with_alert_manager(am)
"""

from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# 基本面警報類型
# =============================================================================

class FundamentalAlertType(Enum):
    """基本面警報類型。"""
    # 營收相關（台股）
    REVENUE_YOY_DECLINE = "revenue_yoy_decline"          # 月營收 YoY 衰退
    REVENUE_YOY_SURGE = "revenue_yoy_surge"              # 月營收 YoY 暴增
    REVENUE_CONSECUTIVE_DECLINE = "revenue_consecutive"   # 連續 N 月衰退

    # 總經相關
    VIX_SPIKE = "vix_spike"                              # VIX 恐慌指數飆升
    VIX_EXTREME = "vix_extreme"                          # VIX 極端值
    YIELD_CURVE_INVERSION = "yield_curve_inversion"      # 殖利率曲線倒掛
    FED_RATE_CHANGE = "fed_rate_change"                  # 利率變動

    # 財報相關（美股）
    EPS_BEAT = "eps_beat"                                # EPS 優於預期
    EPS_MISS = "eps_miss"                                # EPS 差於預期
    EARNINGS_UPCOMING = "earnings_upcoming"              # 財報即將公布

    # 估值相關
    PE_EXTREME_HIGH = "pe_extreme_high"                  # P/E 過高
    PE_EXTREME_LOW = "pe_extreme_low"                    # P/E 過低

    # 綜合
    HEALTH_CHECK = "health_check"                        # 整體體檢結果


@dataclass
class FundamentalAlert:
    """一則基本面警報。"""
    alert_type: FundamentalAlertType
    symbol: str
    severity: str       # 'info', 'warning', 'critical'
    title: str
    message: str
    value: Any = None
    threshold: Any = None
    timestamp: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'alert_type': self.alert_type.value,
            'symbol': self.symbol,
            'severity': self.severity,
            'title': self.title,
            'message': self.message,
            'value': self.value,
            'threshold': self.threshold,
            'timestamp': self.timestamp.isoformat(),
            'data': self.data,
        }

    def __str__(self):
        icon = {'info': 'ℹ️', 'warning': '⚠️', 'critical': '🚨'}.get(self.severity, '?')
        return f"[{icon} {self.severity.upper()}] {self.symbol}: {self.title}"


# =============================================================================
# 門檻設定（可自訂）
# =============================================================================

@dataclass
class AlertThresholds:
    """
    警報門檻設定。

    你可以根據自己的風險偏好調整這些數值。
    """
    # 月營收
    revenue_yoy_decline_pct: float = -10.0    # YoY 衰退超過 -10% 觸發
    revenue_yoy_surge_pct: float = 30.0       # YoY 暴增超過 30% 觸發
    revenue_consecutive_months: int = 3       # 連續衰退 3 個月觸發

    # VIX
    vix_warning: float = 25.0                 # VIX > 25 → 警告
    vix_critical: float = 35.0                # VIX > 35 → 嚴重

    # 殖利率曲線
    yield_curve_inversion: float = 0.0        # 10Y-2Y < 0 = 倒掛

    # EPS Surprise
    eps_beat_threshold: float = 5.0           # EPS 超預期 5% 以上
    eps_miss_threshold: float = -5.0          # EPS 低於預期 5% 以上

    # P/E 估值
    pe_high: float = 40.0                     # P/E > 40 偏貴
    pe_low: float = 8.0                       # P/E < 8 偏低（注意可能是陷阱）

    # 財報日距離
    earnings_days_ahead: int = 7              # 財報公布前 7 天提醒


# =============================================================================
# 基本面警報檢查器
# =============================================================================

class FundamentalAlertChecker:
    """
    基本面警報檢查器。

    核心功能：給它一個股票代號，它自動抓資料、檢查所有條件、回傳警報清單。

    Usage:
        checker = FundamentalAlertChecker()

        # 檢查單檔
        alerts = checker.check_stock('2330')
        for a in alerts:
            print(a)

        # 批次掃描
        report = checker.scan_watchlist(['2330', 'AAPL', 'NVDA'])
    """

    def __init__(
        self,
        thresholds: Optional[AlertThresholds] = None,
        financial_manager=None,
        news_manager=None,
    ):
        self.thresholds = thresholds or AlertThresholds()
        self._financial_manager = financial_manager
        self._news_manager = news_manager

    @property
    def financial_manager(self):
        if self._financial_manager is None:
            from .financial_reports import FinancialReportManager
            self._financial_manager = FinancialReportManager()
        return self._financial_manager

    @property
    def news_manager(self):
        if self._news_manager is None:
            from .news_fetcher import NewsManager
            self._news_manager = NewsManager()
        return self._news_manager

    def _is_taiwan_stock(self, symbol: str) -> bool:
        clean = symbol.upper().strip().replace('.TW', '').replace('.TWO', '')
        return clean.isdigit() and len(clean) in (4, 5)

    def _is_etf(self, symbol: str) -> bool:
        """判斷是否為 ETF（ETF 沒有 earnings/P-E 等基本面資料）。"""
        sym = symbol.upper().strip()
        # 台股 ETF：0 開頭的 4-5 碼數字
        clean = sym.replace('.TW', '').replace('.TWO', '')
        if clean.isdigit() and clean.startswith('0'):
            return True
        # 美股 ETF：常見清單判斷
        us_etfs = {
            'SPY', 'VOO', 'QQQ', 'VTI', 'IWM', 'VGT', 'VTV', 'SOXX',
            'IYW', 'IVW', 'IYF', 'IAU', 'IBIT', 'ICLN', 'VXUS', 'VYMI',
            'BND', 'BNDX', 'VIG', 'SCHD', 'XLF', 'XLK', 'XLE', 'XLV',
            'DIA', 'EFA', 'EEM', 'GLD', 'SLV', 'TLT', 'HYG', 'LQD',
            'ARKK', 'ARKG', 'ARKW', 'ARKF', 'VWO', 'VEA', 'VNQ',
        }
        if sym in us_etfs:
            return True
        # 嘗試用 yfinance 偵測 quoteType
        try:
            import yfinance as yf
            info = yf.Ticker(sym).info
            quote_type = info.get('quoteType', '')
            if quote_type == 'ETF':
                return True
        except Exception:
            pass
        return False

    # -----------------------------------------------------------------
    # 主要 API
    # -----------------------------------------------------------------

    def check_stock(
        self,
        symbol: str,
        include_macro: bool = True,
    ) -> List[FundamentalAlert]:
        """
        對一檔股票執行完整的基本面檢查。

        自動根據台股/美股執行不同的檢查項目。
        ETF 只做總經環境檢查，跳過個股基本面。

        Args:
            symbol: 股票代號
            include_macro: 是否包含總經檢查（批次掃描時由外部統一檢查，避免重複呼叫）

        Returns:
            觸發的警報清單
        """
        alerts = []

        # ETF 沒有 earnings / P-E / 月營收，跳過個股基本面
        if self._is_etf(symbol):
            logger.info(f"{symbol} 是 ETF，跳過基本面檢查")
            if include_macro:
                alerts.extend(self._check_macro_environment(symbol))
            return alerts

        if self._is_taiwan_stock(symbol):
            # 台股：月營收為核心
            alerts.extend(self._check_tw_revenue(symbol))
        else:
            # 美股：EPS + 估值
            alerts.extend(self._check_us_earnings(symbol))
            alerts.extend(self._check_us_valuation(symbol))

        # 通用：總經環境（批次掃描時跳過，因 scan_watchlist 已呼叫 check_macro_only）
        if include_macro:
            alerts.extend(self._check_macro_environment(symbol))

        return alerts

    def check_macro_only(self) -> List[FundamentalAlert]:
        """
        只檢查總經環境（不針對特定股票）。

        適合每日早盤前快速掃描。
        """
        return self._check_macro_environment('MACRO')

    def scan_watchlist(
        self,
        symbols: List[str],
        include_macro: bool = True,
    ) -> Dict[str, Any]:
        """
        批次掃描整個觀察清單。

        Args:
            symbols: 股票代號清單
            include_macro: 是否包含總經檢查

        Returns:
            掃描報告字典，包含：
            - alerts: 所有觸發的警報
            - summary: 摘要統計
            - by_symbol: 按股票分類的警報
            - by_severity: 按嚴重度分類
        """
        all_alerts = []
        by_symbol = {}

        # 總經（只檢查一次）
        if include_macro:
            macro_alerts = self.check_macro_only()
            all_alerts.extend(macro_alerts)
            by_symbol['MACRO'] = macro_alerts

        # 逐檔檢查（總經已在上方 check_macro_only() 統一檢查，不重複）
        for symbol in symbols:
            try:
                stock_alerts = self.check_stock(symbol, include_macro=False)
                all_alerts.extend(stock_alerts)
                by_symbol[symbol] = stock_alerts
            except Exception as e:
                logger.error(f"掃描 {symbol} 失敗: {e}")
                by_symbol[symbol] = [FundamentalAlert(
                    alert_type=FundamentalAlertType.HEALTH_CHECK,
                    symbol=symbol,
                    severity='info',
                    title='掃描失敗',
                    message=f'無法取得資料: {str(e)[:50]}',
                )]

        # 統計
        by_severity = {
            'critical': [a for a in all_alerts if a.severity == 'critical'],
            'warning': [a for a in all_alerts if a.severity == 'warning'],
            'info': [a for a in all_alerts if a.severity == 'info'],
        }

        return {
            'scan_time': datetime.now().isoformat(),
            'total_symbols': len(symbols),
            'total_alerts': len(all_alerts),
            'alerts': all_alerts,
            'by_symbol': by_symbol,
            'by_severity': by_severity,
            'summary': {
                'critical': len(by_severity['critical']),
                'warning': len(by_severity['warning']),
                'info': len(by_severity['info']),
            },
        }

    # -----------------------------------------------------------------
    # 台股檢查
    # -----------------------------------------------------------------

    def _check_tw_revenue(self, symbol: str) -> List[FundamentalAlert]:
        """檢查台股月營收。"""
        alerts = []

        try:
            rev_df = self.financial_manager.get_monthly_revenue(symbol)
            if rev_df.empty:
                return alerts

            latest = rev_df.iloc[-1]
            yoy = latest.get('revenue_yoy', None)

            if yoy is not None and pd.notna(yoy):
                # 1. YoY 衰退檢查
                if yoy <= self.thresholds.revenue_yoy_decline_pct:
                    severity = 'critical' if yoy <= -30 else 'warning'
                    alerts.append(FundamentalAlert(
                        alert_type=FundamentalAlertType.REVENUE_YOY_DECLINE,
                        symbol=symbol,
                        severity=severity,
                        title=f'月營收年增率 {yoy:+.1f}%',
                        message=(
                            f'{symbol} 最新月營收 YoY {yoy:+.1f}%，'
                            f'低於門檻 {self.thresholds.revenue_yoy_decline_pct}%'
                        ),
                        value=yoy,
                        threshold=self.thresholds.revenue_yoy_decline_pct,
                        data={'revenue': float(latest.get('revenue', 0))},
                    ))

                # 2. YoY 暴增檢查
                if yoy >= self.thresholds.revenue_yoy_surge_pct:
                    alerts.append(FundamentalAlert(
                        alert_type=FundamentalAlertType.REVENUE_YOY_SURGE,
                        symbol=symbol,
                        severity='info',
                        title=f'月營收年增率大幅成長 {yoy:+.1f}%',
                        message=(
                            f'{symbol} 月營收 YoY 暴增 {yoy:+.1f}%，'
                            f'超過 {self.thresholds.revenue_yoy_surge_pct}%'
                        ),
                        value=yoy,
                        threshold=self.thresholds.revenue_yoy_surge_pct,
                    ))

            # 3. 連續衰退檢查
            if 'revenue_yoy' in rev_df.columns:
                recent = rev_df.tail(self.thresholds.revenue_consecutive_months)
                if len(recent) >= self.thresholds.revenue_consecutive_months:
                    consecutive_decline = all(
                        v < 0 for v in recent['revenue_yoy'].dropna()
                    )
                    if consecutive_decline:
                        n = self.thresholds.revenue_consecutive_months
                        alerts.append(FundamentalAlert(
                            alert_type=FundamentalAlertType.REVENUE_CONSECUTIVE_DECLINE,
                            symbol=symbol,
                            severity='critical',
                            title=f'月營收連續 {n} 個月衰退',
                            message=(
                                f'{symbol} 月營收已連續 {n} 個月 YoY 為負，'
                                f'基本面趨勢轉弱'
                            ),
                            value=n,
                            threshold=n,
                        ))

        except Exception as e:
            logger.error(f"台股營收檢查失敗 {symbol}: {e}")

        return alerts

    # -----------------------------------------------------------------
    # 美股檢查
    # -----------------------------------------------------------------

    def _check_us_earnings(self, symbol: str) -> List[FundamentalAlert]:
        """檢查美股 EPS surprise 和即將到來的財報。"""
        alerts = []

        try:
            # EPS surprise
            earnings_hist = self.news_manager.get_earnings_history(symbol)
            if earnings_hist is not None and not earnings_hist.empty:
                # 取最新一期
                latest = earnings_hist.iloc[-1]
                actual = latest.get('epsActual', latest.get('Reported EPS'))
                estimate = latest.get('epsEstimate', latest.get('EPS Estimate'))

                if pd.notna(actual) and pd.notna(estimate) and estimate != 0:
                    surprise_pct = (actual - estimate) / abs(estimate) * 100

                    if surprise_pct >= self.thresholds.eps_beat_threshold:
                        alerts.append(FundamentalAlert(
                            alert_type=FundamentalAlertType.EPS_BEAT,
                            symbol=symbol,
                            severity='info',
                            title=f'EPS 優於預期 {surprise_pct:+.1f}%',
                            message=(
                                f'{symbol} 最新 EPS ${actual:.2f} vs '
                                f'預估 ${estimate:.2f} (surprise {surprise_pct:+.1f}%)'
                            ),
                            value=surprise_pct,
                            threshold=self.thresholds.eps_beat_threshold,
                            data={'actual': float(actual), 'estimate': float(estimate)},
                        ))

                    if surprise_pct <= self.thresholds.eps_miss_threshold:
                        severity = 'critical' if surprise_pct <= -15 else 'warning'
                        alerts.append(FundamentalAlert(
                            alert_type=FundamentalAlertType.EPS_MISS,
                            symbol=symbol,
                            severity=severity,
                            title=f'EPS 低於預期 {surprise_pct:+.1f}%',
                            message=(
                                f'{symbol} 最新 EPS ${actual:.2f} vs '
                                f'預估 ${estimate:.2f} (miss {surprise_pct:+.1f}%)'
                            ),
                            value=surprise_pct,
                            threshold=self.thresholds.eps_miss_threshold,
                            data={'actual': float(actual), 'estimate': float(estimate)},
                        ))

        except Exception as e:
            logger.error(f"美股 EPS 檢查失敗 {symbol}: {e}")

        return alerts

    def _check_us_valuation(self, symbol: str) -> List[FundamentalAlert]:
        """檢查美股估值水位。"""
        alerts = []

        try:
            ratios = self.financial_manager.get_key_ratios(symbol)
            if not ratios:
                return alerts

            pe = ratios.get('pe_ratio')
            if pe is not None:
                if pe > self.thresholds.pe_high:
                    alerts.append(FundamentalAlert(
                        alert_type=FundamentalAlertType.PE_EXTREME_HIGH,
                        symbol=symbol,
                        severity='warning',
                        title=f'P/E 偏高: {pe:.1f}',
                        message=(
                            f'{symbol} 本益比 {pe:.1f} 超過門檻 {self.thresholds.pe_high}，'
                            f'估值偏貴'
                        ),
                        value=pe,
                        threshold=self.thresholds.pe_high,
                    ))
                elif pe > 0 and pe < self.thresholds.pe_low:
                    alerts.append(FundamentalAlert(
                        alert_type=FundamentalAlertType.PE_EXTREME_LOW,
                        symbol=symbol,
                        severity='info',
                        title=f'P/E 偏低: {pe:.1f}',
                        message=(
                            f'{symbol} 本益比 {pe:.1f} 低於 {self.thresholds.pe_low}，'
                            f'可能低估，但也要注意是否為價值陷阱'
                        ),
                        value=pe,
                        threshold=self.thresholds.pe_low,
                    ))

        except Exception as e:
            logger.error(f"美股估值檢查失敗 {symbol}: {e}")

        return alerts

    # -----------------------------------------------------------------
    # 總經檢查
    # -----------------------------------------------------------------

    def _check_macro_environment(self, symbol: str) -> List[FundamentalAlert]:
        """檢查總經環境。"""
        alerts = []

        # 1. VIX
        try:
            vix_df = self.news_manager.get_macro_indicator('VIX')
            if not vix_df.empty:
                latest_vix = float(vix_df.iloc[-1]['value'])

                if latest_vix >= self.thresholds.vix_critical:
                    alerts.append(FundamentalAlert(
                        alert_type=FundamentalAlertType.VIX_EXTREME,
                        symbol=symbol,
                        severity='critical',
                        title=f'VIX 恐慌指數極端: {latest_vix:.1f}',
                        message=(
                            f'VIX 恐慌指數 {latest_vix:.1f} 超過 '
                            f'{self.thresholds.vix_critical}，市場極度恐慌'
                        ),
                        value=latest_vix,
                        threshold=self.thresholds.vix_critical,
                    ))
                elif latest_vix >= self.thresholds.vix_warning:
                    alerts.append(FundamentalAlert(
                        alert_type=FundamentalAlertType.VIX_SPIKE,
                        symbol=symbol,
                        severity='warning',
                        title=f'VIX 恐慌指數偏高: {latest_vix:.1f}',
                        message=(
                            f'VIX {latest_vix:.1f} 超過 '
                            f'{self.thresholds.vix_warning}，市場緊張'
                        ),
                        value=latest_vix,
                        threshold=self.thresholds.vix_warning,
                    ))
        except Exception as e:
            logger.warning(f"VIX 檢查失敗: {e}")

        # 2. 殖利率曲線
        try:
            yc_df = self.news_manager.get_macro_indicator('YIELD_CURVE')
            if not yc_df.empty:
                latest_yc = float(yc_df.iloc[-1]['value'])

                if latest_yc < self.thresholds.yield_curve_inversion:
                    alerts.append(FundamentalAlert(
                        alert_type=FundamentalAlertType.YIELD_CURVE_INVERSION,
                        symbol=symbol,
                        severity='warning',
                        title=f'殖利率曲線倒掛: {latest_yc:.2f}',
                        message=(
                            f'10年-2年殖利率利差 {latest_yc:.2f}%，'
                            f'倒掛通常預示經濟衰退風險'
                        ),
                        value=latest_yc,
                        threshold=0,
                    ))
        except Exception as e:
            logger.warning(f"殖利率曲線檢查失敗: {e}")

        return alerts

    # -----------------------------------------------------------------
    # 與現有 AlertManager 整合
    # -----------------------------------------------------------------

    def register_with_alert_manager(self, alert_manager):
        """
        註冊到現有的 AlertManager，讓基本面警報可以
        透過同一個 handler 機制（console / LINE / email）發送。

        Args:
            alert_manager: 現有的 AlertManager 實例
        """
        from .alerts import Alert, AlertType, AlertPriority, AlertEvent

        def fundamental_check_handler(event):
            """當價格警報觸發時，順便檢查基本面。"""
            symbol = event.alert.symbol
            try:
                fund_alerts = self.check_stock(symbol)
                for fa in fund_alerts:
                    if fa.severity in ('warning', 'critical'):
                        logger.info(f"[Fundamental] {fa}")
            except Exception as e:
                logger.warning(f"基本面檢查失敗: {e}")

        alert_manager.add_handler(fundamental_check_handler)
        logger.info("基本面警報已註冊到 AlertManager")


# =============================================================================
# 報告產生器
# =============================================================================

def generate_scan_report(scan_result: Dict[str, Any]) -> str:
    """
    從掃描結果產生文字報告。

    適合輸出到 console 或存成檔案。

    Args:
        scan_result: scan_watchlist() 的回傳值

    Returns:
        格式化的報告文字
    """
    lines = []
    lines.append("=" * 60)
    lines.append(f"  基本面掃描報告  |  {scan_result['scan_time'][:19]}")
    lines.append("=" * 60)
    lines.append("")

    summary = scan_result['summary']
    lines.append(f"  掃描股票數: {scan_result['total_symbols']}")
    lines.append(f"  總警報數:   {scan_result['total_alerts']}")
    lines.append(f"    🚨 嚴重: {summary['critical']}")
    lines.append(f"    ⚠️  警告: {summary['warning']}")
    lines.append(f"    ℹ️  資訊: {summary['info']}")
    lines.append("")

    # 嚴重警報優先顯示
    if scan_result['by_severity']['critical']:
        lines.append("--- 🚨 嚴重警報 ---")
        for alert in scan_result['by_severity']['critical']:
            lines.append(f"  [{alert.symbol}] {alert.title}")
            lines.append(f"    {alert.message}")
        lines.append("")

    if scan_result['by_severity']['warning']:
        lines.append("--- ⚠️ 警告 ---")
        for alert in scan_result['by_severity']['warning']:
            lines.append(f"  [{alert.symbol}] {alert.title}")
            lines.append(f"    {alert.message}")
        lines.append("")

    if scan_result['by_severity']['info']:
        lines.append("--- ℹ️ 資訊 ---")
        for alert in scan_result['by_severity']['info']:
            lines.append(f"  [{alert.symbol}] {alert.title}")
        lines.append("")

    lines.append("=" * 60)

    return "\n".join(lines)
