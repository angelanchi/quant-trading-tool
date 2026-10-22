# -*- coding: utf-8 -*-
"""
News & Macro Data Fetcher Module (新聞與總經資料模組)

提供三大類資料擷取：
1. 財經新聞 (Financial News)
   - Finnhub Company News (美股)
   - Google News RSS (台股/美股通用)

2. 法說會/重大訊息 (Earnings & Filings)
   - SEC EDGAR filings (美股)
   - Finnhub earnings calendar
   - 公開資訊觀測站（台股）

3. 總經數據 (Macro Economic Data)
   - FRED API (聯準會經濟數據庫)
   - 常用指標：CPI, 利率, PMI, GDP, 失業率

Usage:
    from core.news_fetcher import NewsManager

    manager = NewsManager()
    news = manager.get_company_news('AAPL')
    macro = manager.get_macro_indicator('CPI')
    calendar = manager.get_earnings_calendar_range('2024-01-01', '2024-03-31')
"""

from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
import logging
import json
import xml.etree.ElementTree as ET

import pandas as pd

logger = logging.getLogger(__name__)


# =============================================================================
# 財經新聞擷取 (Financial News)
# =============================================================================

class NewsFetcher:
    """
    財經新聞擷取器。

    資料來源：
    - Finnhub: 美股公司新聞（需要 API key，免費版 60 req/min）
    - Google News RSS: 台股/美股通用的新聞關鍵字搜尋（免費、無需 key）
    """

    def __init__(self, finnhub_api_key: Optional[str] = None):
        self.finnhub_api_key = finnhub_api_key
        self._finnhub_client = None

    @property
    def finnhub_client(self):
        """延遲初始化 Finnhub client。"""
        if self._finnhub_client is None and self.finnhub_api_key:
            try:
                import finnhub
                self._finnhub_client = finnhub.Client(api_key=self.finnhub_api_key)
                logger.info("Finnhub (新聞): client 已初始化")
            except ImportError:
                logger.warning("Finnhub 未安裝，新聞功能受限: pip install finnhub-python")
        return self._finnhub_client

    def get_company_news_finnhub(
        self,
        symbol: str,
        days_back: int = 7,
    ) -> List[Dict[str, Any]]:
        """
        透過 Finnhub 取得美股公司新聞。

        Args:
            symbol: 美股代號，例如 'AAPL'
            days_back: 往回幾天

        Returns:
            新聞列表，每則包含：headline, summary, url, datetime, source
        """
        if not self.finnhub_client:
            logger.warning("Finnhub API key 未設定，無法取得公司新聞")
            return []

        end = date.today()
        start = end - timedelta(days=days_back)

        try:
            news = self.finnhub_client.company_news(
                symbol,
                _from=start.strftime('%Y-%m-%d'),
                to=end.strftime('%Y-%m-%d'),
            )

            results = []
            for item in (news or []):
                results.append({
                    'source': item.get('source', ''),
                    'headline': item.get('headline', ''),
                    'summary': item.get('summary', ''),
                    'url': item.get('url', ''),
                    'datetime': datetime.fromtimestamp(item.get('datetime', 0)).isoformat(),
                    'image': item.get('image', ''),
                    'category': item.get('category', ''),
                    'related': item.get('related', ''),
                    'provider': 'finnhub',
                })

            logger.info(f"取得 {symbol} Finnhub 新聞 {len(results)} 則")
            return results

        except Exception as e:
            logger.error(f"Finnhub 新聞取得失敗 {symbol}: {e}")
            return []

    def get_news_google_rss(
        self,
        query: str,
        language: str = 'zh-TW',
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        透過 Google News RSS 搜尋新聞。

        這個方法不需要 API key，適合台股或任何關鍵字搜尋。
        內建重試機制與 proxy 失敗自動降級（直連）。

        Args:
            query: 搜尋關鍵字，例如 '台積電 法說會' 或 'Apple earnings'
            language: 語言 ('zh-TW', 'en')
            max_results: 最多回傳幾則

        Returns:
            新聞列表
        """
        import urllib.parse
        import urllib.request
        import time as _time

        encoded_query = urllib.parse.quote(query)
        url = (
            f"https://news.google.com/rss/search?"
            f"q={encoded_query}&hl={language}&gl=TW&ceid=TW:{language.split('-')[0]}"
        )

        max_retries = 3
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; QuantTool/1.0)'
                })

                # 第二次重試起：繞過系統 proxy 直連
                if attempt > 0:
                    no_proxy_handler = urllib.request.ProxyHandler({})
                    opener = urllib.request.build_opener(no_proxy_handler)
                    response = opener.open(req, timeout=15)
                else:
                    response = urllib.request.urlopen(req, timeout=10)

                with response:
                    xml_content = response.read()

                root = ET.fromstring(xml_content)
                channel = root.find('channel')
                if channel is None:
                    return []

                results = []
                for item in channel.findall('item')[:max_results]:
                    pub_date_str = item.findtext('pubDate', '')
                    try:
                        pub_date = datetime.strptime(
                            pub_date_str, '%a, %d %b %Y %H:%M:%S %Z'
                        ).isoformat()
                    except Exception:
                        pub_date = pub_date_str

                    results.append({
                        'headline': item.findtext('title', ''),
                        'url': item.findtext('link', ''),
                        'datetime': pub_date,
                        'source': item.findtext('source', ''),
                        'summary': '',  # Google RSS 不提供摘要
                        'provider': 'google_news',
                    })

                logger.info(f"Google News 取得 '{query}' 新聞 {len(results)} 則")
                return results

            except (OSError, ConnectionError) as e:
                # WinError 10061 (連線被拒) 等網路層錯誤 → 重試並降級繞過 proxy
                wait = 2 ** attempt
                logger.warning(
                    f"Google News '{query}' 第 {attempt+1} 次失敗 ({e}), "
                    f"{wait}s 後重試{'（繞過 proxy）' if attempt == 0 else ''}"
                )
                _time.sleep(wait)
            except Exception as e:
                logger.error(f"Google News RSS 取得失敗 '{query}': {e}")
                return []

        logger.error(f"Google News RSS '{query}' 重試 {max_retries} 次後仍失敗")
        return []


# =============================================================================
# 總經數據擷取 (Macro Economic Data via FRED)
# =============================================================================

class MacroDataFetcher:
    """
    總經數據擷取器，使用 FRED API (Federal Reserve Economic Data)。

    FRED 提供的常用指標：
    - CPIAUCSL: 消費者物價指數 (CPI)
    - FEDFUNDS: 聯邦基金利率
    - GDP: 國內生產毛額
    - UNRATE: 失業率
    - T10Y2Y: 10年-2年殖利率曲線
    - VIXCLS: VIX 恐慌指數
    - ISM/PMI: 採購經理人指數

    免費 API key 申請：https://fred.stlouisfed.org/docs/api/api_key.html

    不需要 API key 也可以用 pandas_datareader 取得部分資料。
    """

    # 常用指標代碼對照表
    INDICATOR_MAP = {
        # 通膨相關
        'CPI': 'CPIAUCSL',
        'CORE_CPI': 'CPILFESL',
        'PCE': 'PCEPI',
        'CORE_PCE': 'PCEPILFE',

        # 利率相關
        'FED_RATE': 'FEDFUNDS',
        'US_10Y': 'DGS10',
        'US_2Y': 'DGS2',
        'YIELD_CURVE': 'T10Y2Y',

        # 經濟成長
        'GDP': 'GDP',
        'REAL_GDP': 'GDPC1',

        # 就業
        'UNEMPLOYMENT': 'UNRATE',
        'NONFARM_PAYROLL': 'PAYEMS',
        'INITIAL_CLAIMS': 'ICSA',

        # 市場情緒
        'VIX': 'VIXCLS',

        # 製造業
        'ISM_PMI': 'MANEMP',  # 替代指標（ISM PMI 不在 FRED）

        # 房市
        'HOUSING_STARTS': 'HOUST',
        'CASE_SHILLER': 'CSUSHPINSA',

        # 消費者信心
        'CONSUMER_SENTIMENT': 'UMCSENT',

        # 貨幣供給
        'M2': 'M2SL',
    }

    # 快取 TTL（秒）：總經指標變動緩慢，15 分鐘內不重複抓取
    _CACHE_TTL = 900

    def __init__(self, fred_api_key: Optional[str] = None):
        import os
        self.fred_api_key = fred_api_key or os.environ.get('FRED_API_KEY')
        self._cache: Dict[str, tuple] = {}  # key -> (timestamp, DataFrame)

    def get_indicator(
        self,
        indicator: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        取得指定的總經指標資料。

        Args:
            indicator: 指標名稱（可用中文別名或 FRED 代碼）
                       例如 'CPI', 'FED_RATE', 'UNEMPLOYMENT'
                       或直接用 FRED 代碼 'CPIAUCSL'
            start_date: 開始日期 'YYYY-MM-DD'（預設 5 年前）
            end_date: 結束日期 'YYYY-MM-DD'

        Returns:
            DataFrame with columns: date, value, indicator
        """
        # 查找 FRED 代碼
        fred_code = self.INDICATOR_MAP.get(indicator.upper(), indicator.upper())

        # 檢查快取（同樣 indicator + start_date + end_date 才命中）
        import time as _time
        cache_key = f"{fred_code}|{start_date}|{end_date}"
        if cache_key in self._cache:
            cached_time, cached_df = self._cache[cache_key]
            if _time.time() - cached_time < self._CACHE_TTL:
                return cached_df

        if not start_date:
            start_date = (date.today() - timedelta(days=365 * 5)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = date.today().strftime('%Y-%m-%d')

        # 方法 1: 使用 FRED API (需要 key)
        if self.fred_api_key:
            result = self._fetch_from_fred_api(fred_code, start_date, end_date, indicator)
        else:
            # 方法 2: 使用 pandas_datareader (不需要 key)
            result = self._fetch_from_datareader(fred_code, start_date, end_date, indicator)

        # 存入快取
        self._cache[cache_key] = (_time.time(), result)
        return result

    def _fetch_from_fred_api(
        self,
        fred_code: str,
        start_date: str,
        end_date: str,
        indicator_name: str,
    ) -> pd.DataFrame:
        """透過 FRED REST API 取得資料，含重試與 proxy 降級。"""
        import urllib.request
        import json as json_module
        import time as _t

        url = (
            f"https://api.stlouisfed.org/fred/series/observations?"
            f"series_id={fred_code}"
            f"&observation_start={start_date}"
            f"&observation_end={end_date}"
            f"&api_key={self.fred_api_key}"
            f"&file_type=json"
        )

        max_retries = 3
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; QuantTool/1.0)'
                })

                if attempt > 0:
                    no_proxy = urllib.request.ProxyHandler({})
                    opener = urllib.request.build_opener(no_proxy)
                    response = opener.open(req, timeout=15)
                else:
                    response = urllib.request.urlopen(req, timeout=15)

                with response:
                    data = json_module.loads(response.read())

                observations = data.get('observations', [])
                if not observations:
                    logger.warning(f"FRED API 無資料: {fred_code}")
                    return pd.DataFrame()

                df = pd.DataFrame(observations)
                df['date'] = pd.to_datetime(df['date'])
                df['value'] = pd.to_numeric(df['value'], errors='coerce')
                df['indicator'] = indicator_name
                df['fred_code'] = fred_code
                df = df[['date', 'value', 'indicator', 'fred_code']].dropna(subset=['value'])

                logger.info(f"FRED API 取得 {indicator_name} ({fred_code}) {len(df)} 筆")
                return df

            except (OSError, ConnectionError) as e:
                wait = 2 ** attempt
                logger.warning(
                    f"FRED API {fred_code} 第 {attempt+1} 次失敗 ({e}), "
                    f"{wait}s 後重試"
                )
                _t.sleep(wait)
            except Exception as e:
                logger.error(f"FRED API 取得失敗 {fred_code}: {e}")
                return pd.DataFrame()

        logger.error(f"FRED API {fred_code} 重試 {max_retries} 次後仍失敗")
        return pd.DataFrame()

    def _fetch_from_datareader(
        self,
        fred_code: str,
        start_date: str,
        end_date: str,
        indicator_name: str,
    ) -> pd.DataFrame:
        """透過 pandas_datareader 取得資料（不需要 API key）。"""
        try:
            from pandas_datareader import data as pdr

            df = pdr.DataReader(fred_code, 'fred', start_date, end_date)

            if df is None or df.empty:
                logger.warning(f"pandas_datareader 無資料: {fred_code}")
                return pd.DataFrame()

            df = df.reset_index()
            df.columns = ['date', 'value']
            df['indicator'] = indicator_name
            df['fred_code'] = fred_code
            df = df.dropna(subset=['value'])

            logger.info(f"pandas_datareader 取得 {indicator_name} ({fred_code}) {len(df)} 筆")
            return df

        except ImportError:
            logger.error(
                "請安裝 pandas_datareader: pip install pandas-datareader\n"
                "或提供 FRED_API_KEY 環境變數"
            )
            return pd.DataFrame()

        except Exception as e:
            logger.error(f"pandas_datareader 取得失敗 {fred_code}: {e}")
            return pd.DataFrame()

    def get_multiple_indicators(
        self,
        indicators: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        一次取得多個指標，合併成同一個 DataFrame。

        Args:
            indicators: 指標列表，例如 ['CPI', 'FED_RATE', 'UNEMPLOYMENT']
            start_date: 開始日期
            end_date: 結束日期

        Returns:
            DataFrame with columns: date, value, indicator, fred_code
        """
        all_data = []
        for indicator in indicators:
            df = self.get_indicator(indicator, start_date, end_date)
            if not df.empty:
                all_data.append(df)

        if not all_data:
            return pd.DataFrame()

        combined = pd.concat(all_data, ignore_index=True)
        return combined.sort_values('date')

    def get_macro_dashboard_data(self) -> Dict[str, pd.DataFrame]:
        """
        取得總經儀表板常用的指標組合。

        回傳字典，方便在 Streamlit 上呈現。

        Returns:
            字典 key=指標名稱, value=DataFrame
        """
        dashboard_indicators = [
            'CPI', 'FED_RATE', 'UNEMPLOYMENT', 'US_10Y',
            'YIELD_CURVE', 'VIX', 'CONSUMER_SENTIMENT',
        ]

        results = {}
        for indicator in dashboard_indicators:
            df = self.get_indicator(indicator)
            if not df.empty:
                results[indicator] = df

        return results

    @staticmethod
    def list_available_indicators() -> Dict[str, str]:
        """列出所有可用的指標名稱與 FRED 代碼。"""
        return dict(MacroDataFetcher.INDICATOR_MAP)


# =============================================================================
# 法說會/重大訊息 (Earnings & SEC Filings)
# =============================================================================

class EarningsCalendarFetcher:
    """
    財報日程與法說會資料擷取器。

    資料來源：
    - Finnhub earnings calendar (美股)
    - yfinance earnings dates
    """

    def __init__(self, finnhub_api_key: Optional[str] = None):
        self.finnhub_api_key = finnhub_api_key
        self._finnhub_client = None

    @property
    def finnhub_client(self):
        if self._finnhub_client is None and self.finnhub_api_key:
            try:
                import finnhub
                self._finnhub_client = finnhub.Client(api_key=self.finnhub_api_key)
            except ImportError:
                pass
        return self._finnhub_client

    def get_upcoming_earnings(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        取得即將到來的財報發布日程。

        Args:
            from_date: 開始日期
            to_date: 結束日期（預設未來 2 週）

        Returns:
            DataFrame 包含：symbol, date, epsEstimate, epsActual, revenueEstimate
        """
        if not self.finnhub_client:
            logger.warning("Finnhub API key 未設定，無法取得 earnings calendar")
            return pd.DataFrame()

        if not from_date:
            from_date = date.today().strftime('%Y-%m-%d')
        if not to_date:
            to_date = (date.today() + timedelta(days=14)).strftime('%Y-%m-%d')

        try:
            calendar = self.finnhub_client.earnings_calendar(
                _from=from_date,
                to=to_date,
                symbol='',
                international=False,
            )

            earnings = calendar.get('earningsCalendar', [])
            if not earnings:
                return pd.DataFrame()

            df = pd.DataFrame(earnings)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')

            logger.info(f"取得 earnings calendar {len(df)} 筆 ({from_date} ~ {to_date})")
            return df

        except Exception as e:
            logger.error(f"取得 earnings calendar 失敗: {e}")
            return pd.DataFrame()

    def get_company_earnings_history(self, symbol: str) -> pd.DataFrame:
        """
        取得特定公司的歷史 EPS 資料與 surprise。

        Args:
            symbol: 美股代號

        Returns:
            DataFrame 包含：date, epsEstimate, epsActual, surprise, surprisePercent
        """
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)

            # 嘗試取得 earnings history
            try:
                hist = ticker.earnings_history
                if hist is not None and not hist.empty:
                    logger.info(f"取得 {symbol} earnings history {len(hist)} 期")
                    return hist
            except Exception:
                pass

            # 備用：從 earnings_dates 取得
            try:
                dates = ticker.earnings_dates
                if dates is not None and not dates.empty:
                    dates = dates.reset_index()
                    return dates
            except Exception:
                pass

            return pd.DataFrame()

        except Exception as e:
            logger.error(f"取得 {symbol} earnings history 失敗: {e}")
            return pd.DataFrame()


# =============================================================================
# 統一管理器 (Unified News Manager)
# =============================================================================

class NewsManager:
    """
    統一的新聞與總經資料管理器。

    整合三個子模組，提供簡潔的 API。

    Usage:
        manager = NewsManager()

        # 公司新聞
        news = manager.get_company_news('AAPL')
        news_tw = manager.get_company_news('2330')

        # 總經指標
        cpi = manager.get_macro_indicator('CPI')
        macro = manager.get_macro_dashboard()

        # 財報日程
        calendar = manager.get_upcoming_earnings()
    """

    def __init__(
        self,
        finnhub_api_key: Optional[str] = None,
        fred_api_key: Optional[str] = None,
    ):
        import os
        # Ensure .env is loaded before reading environment variables
        try:
            from dotenv import load_dotenv
            from pathlib import Path
            env_file = Path(__file__).parent.parent / '.env'
            if env_file.exists():
                load_dotenv(env_file)
        except ImportError:
            pass

        if finnhub_api_key is None:
            finnhub_api_key = os.environ.get('FINNHUB_API_KEY')
        if fred_api_key is None:
            fred_api_key = os.environ.get('FRED_API_KEY')

        self.news_fetcher = NewsFetcher(finnhub_api_key=finnhub_api_key)
        self.macro_fetcher = MacroDataFetcher(fred_api_key=fred_api_key)
        self.earnings_fetcher = EarningsCalendarFetcher(finnhub_api_key=finnhub_api_key)

    def _is_taiwan_stock(self, symbol: str) -> bool:
        clean = symbol.upper().strip().replace('.TW', '').replace('.TWO', '')
        return clean.isdigit() and len(clean) in (4, 5)

    def _is_etf(self, symbol: str) -> bool:
        """判斷是否為 ETF。"""
        sym = symbol.upper().strip()
        clean = sym.replace('.TW', '').replace('.TWO', '')
        if clean.isdigit() and clean.startswith('0'):
            return True
        us_etfs = {
            'SPY', 'VOO', 'QQQ', 'VTI', 'IWM', 'VGT', 'VTV', 'SOXX',
            'IYW', 'IVW', 'IYF', 'IAU', 'IBIT', 'ICLN', 'VXUS', 'VYMI',
            'BND', 'BNDX', 'VIG', 'SCHD', 'XLF', 'XLK', 'XLE', 'XLV',
            'DIA', 'EFA', 'EEM', 'GLD', 'SLV', 'TLT', 'HYG', 'LQD',
            'ARKK', 'ARKG', 'ARKW', 'ARKF', 'VWO', 'VEA', 'VNQ',
        }
        return sym in us_etfs

    # ---- 新聞相關 ----

    def get_company_news(
        self,
        symbol: str,
        days_back: int = 7,
    ) -> List[Dict[str, Any]]:
        """
        取得公司相關新聞。

        台股 → Google News RSS（搜尋股票名稱）
        美股 → Finnhub（優先）+ Google News

        Args:
            symbol: 股票代號
            days_back: 往回幾天

        Returns:
            新聞列表
        """
        all_news = []

        if self._is_taiwan_stock(symbol):
            # 台股：用 Google News 搜尋
            # 可以搜尋股票代號 + 公司名稱
            queries = [f"{symbol} 股票", f"{symbol} 財報"]
            for q in queries:
                news = self.news_fetcher.get_news_google_rss(q, language='zh-TW', max_results=10)
                all_news.extend(news)
        else:
            # 美股：先用 Finnhub
            finnhub_news = self.news_fetcher.get_company_news_finnhub(symbol, days_back)
            all_news.extend(finnhub_news)

            # 補充 Google News
            google_news = self.news_fetcher.get_news_google_rss(
                f"{symbol} stock", language='en', max_results=10
            )
            all_news.extend(google_news)

        # 去重（依 headline 去重）
        seen_headlines = set()
        unique_news = []
        for news in all_news:
            headline = news.get('headline', '')
            if headline and headline not in seen_headlines:
                seen_headlines.add(headline)
                unique_news.append(news)

        # 按日期排序（最新在前）
        unique_news.sort(key=lambda x: x.get('datetime', ''), reverse=True)

        return unique_news

    def search_news(
        self,
        query: str,
        language: str = 'zh-TW',
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        搜尋任意關鍵字的新聞。

        適合搜尋產業趨勢、總經事件等。

        Args:
            query: 搜尋關鍵字，例如 'AI 半導體', 'Fed 升息'
            language: 語言
            max_results: 最多回傳幾則

        Returns:
            新聞列表
        """
        return self.news_fetcher.get_news_google_rss(query, language, max_results)

    # ---- 總經相關 ----

    def get_macro_indicator(
        self,
        indicator: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """取得總經指標。"""
        return self.macro_fetcher.get_indicator(indicator, start_date, end_date)

    def get_macro_dashboard(self) -> Dict[str, pd.DataFrame]:
        """取得總經儀表板資料。"""
        return self.macro_fetcher.get_macro_dashboard_data()

    def list_macro_indicators(self) -> Dict[str, str]:
        """列出可用的總經指標。"""
        return MacroDataFetcher.list_available_indicators()

    # ---- 財報日程相關 ----

    def get_upcoming_earnings(self, **kwargs) -> pd.DataFrame:
        """取得即將到來的財報發布日程。"""
        return self.earnings_fetcher.get_upcoming_earnings(**kwargs)

    def get_earnings_history(self, symbol: str) -> pd.DataFrame:
        """取得特定公司的 EPS 歷史與 surprise（ETF 跳過）。"""
        if self._is_etf(symbol):
            return pd.DataFrame()
        return self.earnings_fetcher.get_company_earnings_history(symbol)

    # ---- 打包取得 ----

    def get_full_context(
        self,
        symbol: str,
        days_back: int = 30,
    ) -> Dict[str, Any]:
        """
        取得某檔股票的完整新聞與事件背景。

        一次呼叫，把公司新聞、財報日程、相關總經指標都抓回來。

        Args:
            symbol: 股票代號
            days_back: 新聞往回幾天

        Returns:
            字典包含：company_news, earnings_history, macro_snapshot
        """
        context = {
            'symbol': symbol,
            'fetch_time': datetime.now().isoformat(),
        }

        # 1. 公司新聞
        context['company_news'] = self.get_company_news(symbol, days_back)

        # 2. EPS 歷史（美股個股，ETF 跳過）
        if not self._is_taiwan_stock(symbol) and not self._is_etf(symbol):
            context['earnings_history'] = self.get_earnings_history(symbol)
        else:
            context['earnings_history'] = pd.DataFrame()

        # 3. 關鍵總經指標快照（最新值）
        macro_snapshot = {}
        for indicator in ['FED_RATE', 'CPI', 'VIX', 'US_10Y']:
            df = self.get_macro_indicator(indicator)
            if not df.empty:
                latest = df.iloc[-1]
                macro_snapshot[indicator] = {
                    'value': float(latest['value']),
                    'date': str(latest['date']),
                }
        context['macro_snapshot'] = macro_snapshot

        return context
