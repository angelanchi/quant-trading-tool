# -*- coding: utf-8 -*-
"""
Financial Reports Module (財報資料模組)

提供台股與美股的財務報表資料擷取，包括：
- 損益表 (Income Statement)
- 資產負債表 (Balance Sheet)
- 現金流量表 (Cash Flow Statement)
- 關鍵財務比率 (Financial Ratios)

資料來源：
- 台股：FinMind API
- 美股：yfinance

Usage:
    from core.financial_reports import FinancialReportManager

    manager = FinancialReportManager()
    income = manager.get_income_statement('2330')       # 台積電
    balance = manager.get_balance_sheet('AAPL')         # Apple
    ratios = manager.get_key_ratios('2330')             # 關鍵比率
    calendar = manager.get_earnings_calendar('AAPL')    # 財報日程
"""

from abc import ABC, abstractmethod
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
import logging
import time

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# 台股財報擷取 (Taiwan Financial Reports via FinMind)
# =============================================================================

class TaiwanFinancialFetcher:
    """
    台股財報資料擷取器，使用 FinMind API。

    FinMind 提供的財報資料集：
    - TaiwanStockFinancialStatements: 綜合損益表
    - TaiwanStockBalanceSheet: 資產負債表
    - TaiwanStockCashFlowsStatement: 現金流量表
    - TaiwanStockMonthRevenue: 月營收
    - TaiwanStockDividend: 股利資料
    """

    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token
        self._client = None

    @property
    def client(self):
        """延遲初始化 FinMind DataLoader。"""
        if self._client is None:
            try:
                from FinMind.data import DataLoader
                self._client = DataLoader()
                if self.api_token:
                    self._client.login_by_token(api_token=self.api_token)
                    logger.info("FinMind (財報): 已驗證 API token")
            except ImportError:
                logger.error("請安裝 FinMind: pip install FinMind")
                raise
        return self._client

    def get_income_statement(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        取得損益表 (Income Statement)。

        Args:
            symbol: 台股代號，例如 '2330'
            start_date: 開始日期 'YYYY-MM-DD'（預設最近 3 年）
            end_date: 結束日期 'YYYY-MM-DD'

        Returns:
            DataFrame 包含：營收、毛利、營業利益、稅後淨利等
        """
        symbol = symbol.replace('.TW', '').replace('.TWO', '')
        if not start_date:
            start_date = (date.today() - timedelta(days=365 * 3)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = date.today().strftime('%Y-%m-%d')

        try:
            df = self.client.taiwan_stock_financial_statement(
                stock_id=symbol,
                start_date=start_date,
                end_date=end_date,
            )
            if df is None or df.empty:
                logger.warning(f"無損益表資料: {symbol}")
                return pd.DataFrame()

            df['date'] = pd.to_datetime(df['date'])
            logger.info(f"取得 {symbol} 損益表 {len(df)} 筆")
            return df

        except Exception as e:
            logger.error(f"取得台股損益表失敗 {symbol}: {e}")
            return pd.DataFrame()

    def get_balance_sheet(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        取得資產負債表 (Balance Sheet)。

        Args:
            symbol: 台股代號
            start_date: 開始日期
            end_date: 結束日期

        Returns:
            DataFrame 包含：總資產、總負債、股東權益等
        """
        symbol = symbol.replace('.TW', '').replace('.TWO', '')
        if not start_date:
            start_date = (date.today() - timedelta(days=365 * 3)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = date.today().strftime('%Y-%m-%d')

        try:
            df = self.client.taiwan_stock_balance_sheet(
                stock_id=symbol,
                start_date=start_date,
                end_date=end_date,
            )
            if df is None or df.empty:
                logger.warning(f"無資產負債表資料: {symbol}")
                return pd.DataFrame()

            df['date'] = pd.to_datetime(df['date'])
            logger.info(f"取得 {symbol} 資產負債表 {len(df)} 筆")
            return df

        except Exception as e:
            logger.error(f"取得台股資產負債表失敗 {symbol}: {e}")
            return pd.DataFrame()

    def get_cash_flow(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        取得現金流量表 (Cash Flow Statement)。

        Args:
            symbol: 台股代號
            start_date: 開始日期
            end_date: 結束日期

        Returns:
            DataFrame 包含：營業現金流、投資現金流、融資現金流
        """
        symbol = symbol.replace('.TW', '').replace('.TWO', '')
        if not start_date:
            start_date = (date.today() - timedelta(days=365 * 3)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = date.today().strftime('%Y-%m-%d')

        try:
            df = self.client.taiwan_stock_cash_flows_statement(
                stock_id=symbol,
                start_date=start_date,
                end_date=end_date,
            )
            if df is None or df.empty:
                logger.warning(f"無現金流量表資料: {symbol}")
                return pd.DataFrame()

            df['date'] = pd.to_datetime(df['date'])
            logger.info(f"取得 {symbol} 現金流量表 {len(df)} 筆")
            return df

        except Exception as e:
            logger.error(f"取得台股現金流量表失敗 {symbol}: {e}")
            return pd.DataFrame()

    def get_monthly_revenue(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        取得月營收資料 (Monthly Revenue)。

        台股特色：每月 10 日前公布上月營收，是最即時的基本面資料。

        Args:
            symbol: 台股代號
            start_date: 開始日期
            end_date: 結束日期

        Returns:
            DataFrame 包含：當月營收、去年同月營收、YoY 成長率、MoM 成長率
        """
        symbol = symbol.replace('.TW', '').replace('.TWO', '')
        if not start_date:
            start_date = (date.today() - timedelta(days=365 * 3)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = date.today().strftime('%Y-%m-%d')

        try:
            df = self.client.taiwan_stock_month_revenue(
                stock_id=symbol,
                start_date=start_date,
                end_date=end_date,
            )
            if df is None or df.empty:
                logger.warning(f"無月營收資料: {symbol}")
                return pd.DataFrame()

            df['date'] = pd.to_datetime(df['date'])

            # 計算 YoY, MoM 成長率
            if 'revenue' in df.columns:
                df['revenue_yoy'] = df['revenue'].pct_change(periods=12) * 100
                df['revenue_mom'] = df['revenue'].pct_change(periods=1) * 100

            logger.info(f"取得 {symbol} 月營收 {len(df)} 筆")
            return df

        except Exception as e:
            logger.error(f"取得台股月營收失敗 {symbol}: {e}")
            return pd.DataFrame()

    def get_dividend(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """取得股利資料 (Dividend)。"""
        symbol = symbol.replace('.TW', '').replace('.TWO', '')
        if not start_date:
            start_date = (date.today() - timedelta(days=365 * 5)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = date.today().strftime('%Y-%m-%d')

        try:
            df = self.client.taiwan_stock_dividend(
                stock_id=symbol,
                start_date=start_date,
                end_date=end_date,
            )
            if df is None or df.empty:
                return pd.DataFrame()

            df['date'] = pd.to_datetime(df['date'])
            return df

        except Exception as e:
            logger.error(f"取得台股股利資料失敗 {symbol}: {e}")
            return pd.DataFrame()


# =============================================================================
# 美股財報擷取 (US Financial Reports via yfinance)
# =============================================================================

class USFinancialFetcher:
    """
    美股財報資料擷取器，使用 yfinance。

    yfinance 提供：
    - 季報/年報 損益表、資產負債表、現金流量表
    - 關鍵財務比率
    - 財報發布日程 (Earnings Calendar)
    - 分析師共識估計
    """

    def __init__(self):
        try:
            import yfinance
            self._yf = yfinance
        except ImportError:
            logger.error("請安裝 yfinance: pip install yfinance")
            raise
        self._last_info_call = 0.0  # 上一次呼叫 ticker.info 的時間戳
        self._info_interval = 2.0   # 每次呼叫間隔至少 2 秒

    def _get_ticker(self, symbol: str):
        """取得 yfinance Ticker 物件。"""
        return self._yf.Ticker(symbol)

    def get_income_statement(
        self,
        symbol: str,
        quarterly: bool = True,
    ) -> pd.DataFrame:
        """
        取得損益表 (Income Statement)。

        Args:
            symbol: 美股代號，例如 'AAPL'
            quarterly: True=季報, False=年報

        Returns:
            DataFrame 包含：Revenue, Gross Profit, Operating Income,
                          Net Income, EPS 等
        """
        try:
            ticker = self._get_ticker(symbol)
            if quarterly:
                df = ticker.quarterly_income_stmt
            else:
                df = ticker.income_stmt

            if df is None or df.empty:
                logger.warning(f"無損益表資料: {symbol}")
                return pd.DataFrame()

            # 轉置：讓日期變成 rows
            df = df.T
            df.index.name = 'date'
            df = df.reset_index()
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')

            logger.info(f"取得 {symbol} 損益表 {len(df)} 期")
            return df

        except Exception as e:
            logger.error(f"取得美股損益表失敗 {symbol}: {e}")
            return pd.DataFrame()

    def get_balance_sheet(
        self,
        symbol: str,
        quarterly: bool = True,
    ) -> pd.DataFrame:
        """
        取得資產負債表 (Balance Sheet)。

        Args:
            symbol: 美股代號
            quarterly: True=季報, False=年報

        Returns:
            DataFrame 包含：Total Assets, Total Liabilities,
                          Stockholders Equity 等
        """
        try:
            ticker = self._get_ticker(symbol)
            if quarterly:
                df = ticker.quarterly_balance_sheet
            else:
                df = ticker.balance_sheet

            if df is None or df.empty:
                logger.warning(f"無資產負債表資料: {symbol}")
                return pd.DataFrame()

            df = df.T
            df.index.name = 'date'
            df = df.reset_index()
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')

            logger.info(f"取得 {symbol} 資產負債表 {len(df)} 期")
            return df

        except Exception as e:
            logger.error(f"取得美股資產負債表失敗 {symbol}: {e}")
            return pd.DataFrame()

    def get_cash_flow(
        self,
        symbol: str,
        quarterly: bool = True,
    ) -> pd.DataFrame:
        """
        取得現金流量表 (Cash Flow Statement)。

        Args:
            symbol: 美股代號
            quarterly: True=季報, False=年報

        Returns:
            DataFrame 包含：Operating Cash Flow, Investing Cash Flow,
                          Financing Cash Flow, Free Cash Flow 等
        """
        try:
            ticker = self._get_ticker(symbol)
            if quarterly:
                df = ticker.quarterly_cashflow
            else:
                df = ticker.cashflow

            if df is None or df.empty:
                logger.warning(f"無現金流量表資料: {symbol}")
                return pd.DataFrame()

            df = df.T
            df.index.name = 'date'
            df = df.reset_index()
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')

            logger.info(f"取得 {symbol} 現金流量表 {len(df)} 期")
            return df

        except Exception as e:
            logger.error(f"取得美股現金流量表失敗 {symbol}: {e}")
            return pd.DataFrame()

    def get_key_ratios(self, symbol: str) -> Dict[str, Any]:
        """
        取得關鍵財務比率 (Key Financial Ratios)。

        Args:
            symbol: 美股代號

        Returns:
            字典包含：P/E, P/B, ROE, Debt/Equity, Profit Margin 等
        """
        try:
            # Rate limiting：避免 yfinance Too Many Requests
            elapsed = time.time() - self._last_info_call
            if elapsed < self._info_interval:
                time.sleep(self._info_interval - elapsed)

            ticker = self._get_ticker(symbol)
            info = ticker.info
            self._last_info_call = time.time()

            ratios = {
                'symbol': symbol,
                'market': 'US',
                'fetch_date': datetime.now().isoformat(),

                # 估值指標 (Valuation)
                'pe_ratio': info.get('trailingPE'),
                'forward_pe': info.get('forwardPE'),
                'pb_ratio': info.get('priceToBook'),
                'ps_ratio': info.get('priceToSalesTrailing12Months'),
                'peg_ratio': info.get('pegRatio'),
                'ev_ebitda': info.get('enterpriseToEbitda'),

                # 獲利能力 (Profitability)
                'profit_margin': info.get('profitMargins'),
                'operating_margin': info.get('operatingMargins'),
                'gross_margin': info.get('grossMargins'),
                'roe': info.get('returnOnEquity'),
                'roa': info.get('returnOnAssets'),

                # 成長指標 (Growth)
                'revenue_growth': info.get('revenueGrowth'),
                'earnings_growth': info.get('earningsGrowth'),
                'earnings_quarterly_growth': info.get('earningsQuarterlyGrowth'),

                # 財務健全度 (Financial Health)
                'debt_to_equity': info.get('debtToEquity'),
                'current_ratio': info.get('currentRatio'),
                'quick_ratio': info.get('quickRatio'),

                # 股利 (Dividend)
                'dividend_yield': info.get('dividendYield'),
                'payout_ratio': info.get('payoutRatio'),

                # 市場資訊 (Market Info)
                'market_cap': info.get('marketCap'),
                'enterprise_value': info.get('enterpriseValue'),
                'beta': info.get('beta'),
                'fifty_two_week_high': info.get('fiftyTwoWeekHigh'),
                'fifty_two_week_low': info.get('fiftyTwoWeekLow'),

                # 分析師估計 (Analyst Estimates)
                'target_mean_price': info.get('targetMeanPrice'),
                'target_high_price': info.get('targetHighPrice'),
                'target_low_price': info.get('targetLowPrice'),
                'recommendation': info.get('recommendationKey'),
                'number_of_analysts': info.get('numberOfAnalystOpinions'),
            }

            logger.info(f"取得 {symbol} 關鍵比率")
            return ratios

        except Exception as e:
            logger.error(f"取得美股關鍵比率失敗 {symbol}: {e}")
            return {}

    def get_earnings_calendar(self, symbol: str) -> Dict[str, Any]:
        """
        取得財報發布日程與 Earnings Surprise (盈餘驚喜)。

        Args:
            symbol: 美股代號

        Returns:
            字典包含：下次財報日、歷史 EPS surprise
        """
        try:
            ticker = self._get_ticker(symbol)

            calendar_info = {}

            # 下次財報日
            try:
                cal = ticker.calendar
                if cal is not None:
                    if isinstance(cal, dict):
                        calendar_info['earnings_date'] = cal.get('Earnings Date')
                    elif isinstance(cal, pd.DataFrame) and not cal.empty:
                        calendar_info['earnings_date'] = cal.iloc[0].get('Earnings Date')
            except Exception:
                pass

            # 歷史 EPS 資料 (Earnings History)
            try:
                earnings = ticker.earnings_history
                if earnings is not None and not earnings.empty:
                    calendar_info['earnings_history'] = earnings.to_dict('records')
            except Exception:
                pass

            logger.info(f"取得 {symbol} 財報日程")
            return calendar_info

        except Exception as e:
            logger.error(f"取得美股財報日程失敗 {symbol}: {e}")
            return {}


# =============================================================================
# 統一管理器 (Unified Financial Report Manager)
# =============================================================================

class FinancialReportManager:
    """
    統一的財報管理器，自動判斷台股/美股並路由到對應的資料源。

    Usage:
        manager = FinancialReportManager()

        # 自動判斷市場
        income = manager.get_income_statement('2330')    # -> 台股
        income = manager.get_income_statement('AAPL')    # -> 美股

        # 關鍵比率
        ratios = manager.get_key_ratios('AAPL')

        # 台股月營收
        rev = manager.get_monthly_revenue('2330')
    """

    def __init__(
        self,
        finmind_token: Optional[str] = None,
    ):
        import os

        if finmind_token is None:
            finmind_token = os.environ.get('FINMIND_API_TOKEN')

        self.tw_fetcher = TaiwanFinancialFetcher(api_token=finmind_token)
        self.us_fetcher = USFinancialFetcher()

    def _is_taiwan_stock(self, symbol: str) -> bool:
        """判斷是否為台股代號。"""
        clean = symbol.upper().strip().replace('.TW', '').replace('.TWO', '')
        return clean.isdigit() and len(clean) in (4, 5)

    def _is_etf(self, symbol: str) -> bool:
        """判斷是否為 ETF（ETF 沒有個股財報資料）。"""
        sym = symbol.upper().strip()
        # 台股 ETF：0 開頭
        clean = sym.replace('.TW', '').replace('.TWO', '')
        if clean.isdigit() and clean.startswith('0'):
            return True
        # 美股常見 ETF
        us_etfs = {
            'SPY', 'VOO', 'QQQ', 'VTI', 'IWM', 'VGT', 'VTV', 'SOXX',
            'IYW', 'IVW', 'IYF', 'IAU', 'IBIT', 'ICLN', 'VXUS', 'VYMI',
            'BND', 'BNDX', 'VIG', 'SCHD', 'XLF', 'XLK', 'XLE', 'XLV',
            'DIA', 'EFA', 'EEM', 'GLD', 'SLV', 'TLT', 'HYG', 'LQD',
            'ARKK', 'ARKG', 'ARKW', 'ARKF', 'VWO', 'VEA', 'VNQ',
        }
        return sym in us_etfs

    def get_income_statement(
        self,
        symbol: str,
        quarterly: bool = True,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """取得損益表，自動路由到台股或美股。"""
        if self._is_taiwan_stock(symbol):
            return self.tw_fetcher.get_income_statement(symbol, start_date, end_date)
        else:
            return self.us_fetcher.get_income_statement(symbol, quarterly)

    def get_balance_sheet(
        self,
        symbol: str,
        quarterly: bool = True,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """取得資產負債表，自動路由到台股或美股。"""
        if self._is_taiwan_stock(symbol):
            return self.tw_fetcher.get_balance_sheet(symbol, start_date, end_date)
        else:
            return self.us_fetcher.get_balance_sheet(symbol, quarterly)

    def get_cash_flow(
        self,
        symbol: str,
        quarterly: bool = True,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """取得現金流量表，自動路由到台股或美股。"""
        if self._is_taiwan_stock(symbol):
            return self.tw_fetcher.get_cash_flow(symbol, start_date, end_date)
        else:
            return self.us_fetcher.get_cash_flow(symbol, quarterly)

    def get_key_ratios(self, symbol: str) -> Dict[str, Any]:
        """
        取得關鍵財務比率。

        台股：從財報資料計算
        美股：直接從 yfinance info 取得
        """
        if self._is_taiwan_stock(symbol):
            return self._compute_tw_ratios(symbol)
        else:
            return self.us_fetcher.get_key_ratios(symbol)

    def get_monthly_revenue(self, symbol: str, **kwargs) -> pd.DataFrame:
        """
        取得台股月營收（僅限台股）。

        這是台股特有的資料，每月 10 日公布，是最即時的基本面指標。
        """
        if not self._is_taiwan_stock(symbol):
            logger.warning(f"{symbol} 非台股，無月營收資料")
            return pd.DataFrame()
        return self.tw_fetcher.get_monthly_revenue(symbol, **kwargs)

    def get_earnings_calendar(self, symbol: str) -> Dict[str, Any]:
        """取得美股財報日程（僅限美股個股，ETF 跳過）。"""
        if self._is_taiwan_stock(symbol):
            logger.info("台股財報日程請參考公開資訊觀測站")
            return {'note': '台股請查公開資訊觀測站 https://mops.twse.com.tw'}
        if self._is_etf(symbol):
            logger.info(f"{symbol} 是 ETF，無財報日程")
            return {'note': f'{symbol} 是 ETF，無個股財報日程'}
        return self.us_fetcher.get_earnings_calendar(symbol)

    def get_financial_summary(self, symbol: str) -> Dict[str, Any]:
        """
        取得完整的財務摘要（一次抓所有資料）。

        回傳一個字典，包含所有可用的財報資料，方便串聯分析。

        Args:
            symbol: 股票代號

        Returns:
            字典包含：income_statement, balance_sheet, cash_flow,
                     key_ratios, monthly_revenue (台股), earnings_calendar (美股)
        """
        summary = {
            'symbol': symbol,
            'market': 'TW' if self._is_taiwan_stock(symbol) else 'US',
            'is_etf': self._is_etf(symbol),
            'fetch_time': datetime.now().isoformat(),
        }

        # ETF 沒有個股財報，只回傳基本資訊
        if self._is_etf(symbol):
            logger.info(f"{symbol} 是 ETF，跳過財報資料抓取")
            summary['note'] = f'{symbol} 是 ETF，無個股財報資料（損益表、資產負債表等）'
            return summary

        summary['income_statement'] = self.get_income_statement(symbol)
        summary['balance_sheet'] = self.get_balance_sheet(symbol)
        summary['cash_flow'] = self.get_cash_flow(symbol)
        summary['key_ratios'] = self.get_key_ratios(symbol)

        if self._is_taiwan_stock(symbol):
            summary['monthly_revenue'] = self.get_monthly_revenue(symbol)
            summary['dividend'] = self.tw_fetcher.get_dividend(symbol)
        else:
            summary['earnings_calendar'] = self.get_earnings_calendar(symbol)

        return summary

    def _compute_tw_ratios(self, symbol: str) -> Dict[str, Any]:
        """
        從台股財報原始資料計算關鍵比率。

        因為 FinMind 不直接提供比率，需要從三表數據推算。
        """
        ratios = {
            'symbol': symbol,
            'market': 'TW',
            'fetch_date': datetime.now().isoformat(),
        }

        try:
            # 取得最新一季的損益表與資產負債表
            income = self.tw_fetcher.get_income_statement(symbol)
            balance = self.tw_fetcher.get_balance_sheet(symbol)

            if not income.empty:
                # 嘗試從資料中抽取常見欄位
                # FinMind 回傳的格式: type (科目名稱), value (金額)
                latest_income = income[income['date'] == income['date'].max()]
                ratios['latest_income_date'] = str(income['date'].max())
                ratios['income_data_available'] = True

                # 將科目轉成字典方便查詢
                if 'type' in latest_income.columns and 'value' in latest_income.columns:
                    items = dict(zip(latest_income['type'], latest_income['value']))
                    ratios['income_items'] = items

            if not balance.empty:
                latest_balance = balance[balance['date'] == balance['date'].max()]
                ratios['latest_balance_date'] = str(balance['date'].max())
                ratios['balance_data_available'] = True

                if 'type' in latest_balance.columns and 'value' in latest_balance.columns:
                    items = dict(zip(latest_balance['type'], latest_balance['value']))
                    ratios['balance_items'] = items

            # 月營收成長（最即時的指標）
            revenue = self.tw_fetcher.get_monthly_revenue(symbol)
            if not revenue.empty:
                latest_rev = revenue.iloc[-1]
                ratios['latest_monthly_revenue'] = float(latest_rev.get('revenue', 0))
                ratios['revenue_yoy'] = float(latest_rev.get('revenue_yoy', 0))
                ratios['revenue_mom'] = float(latest_rev.get('revenue_mom', 0))

        except Exception as e:
            logger.error(f"計算台股比率失敗 {symbol}: {e}")

        return ratios
