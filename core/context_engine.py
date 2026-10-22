# -*- coding: utf-8 -*-
"""
Context Engine Module (背景串聯引擎)

這是整合的核心——把「股價」「財報」「新聞時事」「總經數據」
串聯成時間軸，讓你在看盤時能快速理解：
  "這段漲跌是因為什麼？"
  "財報公布前後股價怎麼反應？"
  "總經環境對這檔股票有什麼影響？"

核心概念：
- ContextEvent: 時間軸上的單一事件（新聞、財報、總經、價格異動）
- StockTimeline: 某檔股票的完整時間軸
- ContextEngine: 整合所有資料源，產出時間軸

Usage:
    from core.context_engine import ContextEngine

    engine = ContextEngine()

    # 取得完整時間軸
    timeline = engine.build_timeline('AAPL', days_back=90)
    timeline.print_summary()

    # 取得「財報日股價反應」分析
    reaction = engine.analyze_earnings_reaction('AAPL')

    # 取得「背景卡片」給 Dashboard 用
    card = engine.get_context_card('2330')
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
# 資料結構 (Data Structures)
# =============================================================================

class EventType(Enum):
    """事件類型。"""
    PRICE_SPIKE = "price_spike"           # 單日大漲/大跌
    VOLUME_SPIKE = "volume_spike"         # 成交量異常放大
    EARNINGS_RELEASE = "earnings_release" # 財報公布
    MONTHLY_REVENUE = "monthly_revenue"   # 台股月營收公布
    NEWS = "news"                         # 重要新聞
    MACRO_EVENT = "macro_event"           # 總經事件（利率決議、CPI 公布等）
    DIVIDEND = "dividend"                 # 除權息
    ANALYST = "analyst"                   # 分析師調整評等/目標價


@dataclass
class ContextEvent:
    """
    時間軸上的一個事件。

    這是所有資料的統一格式，不管是新聞、財報還是價格異動，
    都會被轉成這個格式，放到時間軸上。
    """
    event_type: EventType
    date: datetime
    title: str
    description: str = ""
    impact: str = "neutral"    # 'positive', 'negative', 'neutral'
    importance: int = 1        # 1 (低) ~ 5 (高)
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_type': self.event_type.value,
            'date': self.date.isoformat() if isinstance(self.date, datetime) else str(self.date),
            'title': self.title,
            'description': self.description,
            'impact': self.impact,
            'importance': self.importance,
            'data': self.data,
            'source': self.source,
            'url': self.url,
        }


@dataclass
class StockTimeline:
    """
    某檔股票的完整背景時間軸。

    把所有事件按時間排好，方便在 Dashboard 上呈現。
    """
    symbol: str
    market: str  # 'TW' or 'US'
    events: List[ContextEvent] = field(default_factory=list)
    price_data: Optional[pd.DataFrame] = None
    fetch_time: datetime = field(default_factory=datetime.now)

    def add_event(self, event: ContextEvent):
        self.events.append(event)

    def sort_events(self):
        """按日期排序（最新在前）。"""
        self.events.sort(key=lambda e: e.date, reverse=True)

    def filter_by_type(self, event_type: EventType) -> List[ContextEvent]:
        return [e for e in self.events if e.event_type == event_type]

    def filter_by_importance(self, min_importance: int = 3) -> List[ContextEvent]:
        return [e for e in self.events if e.importance >= min_importance]

    def get_events_near_date(
        self, target_date: datetime, days_range: int = 3
    ) -> List[ContextEvent]:
        """取得某日期前後的事件。"""
        start = target_date - timedelta(days=days_range)
        end = target_date + timedelta(days=days_range)
        return [e for e in self.events if start <= e.date <= end]

    def to_dataframe(self) -> pd.DataFrame:
        """轉成 DataFrame 方便分析。"""
        if not self.events:
            return pd.DataFrame()
        return pd.DataFrame([e.to_dict() for e in self.events])

    def print_summary(self, limit: int = 20):
        """印出時間軸摘要。"""
        self.sort_events()
        print(f"\n=== {self.symbol} ({self.market}) 時間軸 ===")
        print(f"共 {len(self.events)} 個事件\n")

        for event in self.events[:limit]:
            impact_icon = {
                'positive': '[+]',
                'negative': '[-]',
                'neutral': '[=]',
            }.get(event.impact, '[?]')

            importance_bar = '*' * event.importance
            date_str = event.date.strftime('%Y-%m-%d') if isinstance(event.date, datetime) else str(event.date)
            print(f"  {date_str} {impact_icon} [{importance_bar:5s}] {event.title}")
            if event.description:
                print(f"           {event.description[:80]}")
            print()


# =============================================================================
# Context Engine (背景串聯引擎)
# =============================================================================

class ContextEngine:
    """
    背景串聯引擎——整合的核心。

    把 DataManager, FinancialReportManager, NewsManager 的資料
    全部整合到一條時間軸上。

    Usage:
        engine = ContextEngine()
        timeline = engine.build_timeline('AAPL', days_back=90)
    """

    def __init__(
        self,
        data_manager=None,
        financial_manager=None,
        news_manager=None,
    ):
        """
        初始化 Context Engine。

        如果不傳入已有的 manager，會自動建立新的。

        Args:
            data_manager: DataManager 實例（價格資料）
            financial_manager: FinancialReportManager 實例（財報）
            news_manager: NewsManager 實例（新聞/總經）
        """
        # 延遲初始化，避免立刻出錯
        self._data_manager = data_manager
        self._financial_manager = financial_manager
        self._news_manager = news_manager

    @property
    def data_manager(self):
        if self._data_manager is None:
            from .data_fetcher import DataManager
            self._data_manager = DataManager()
        return self._data_manager

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

    # -----------------------------------------------------------------
    # 主要 API
    # -----------------------------------------------------------------

    def build_timeline(
        self,
        symbol: str,
        days_back: int = 90,
        include_news: bool = True,
        include_financials: bool = True,
        include_macro: bool = True,
        include_price_events: bool = True,
    ) -> StockTimeline:
        """
        建構完整的背景時間軸。

        這是最重要的方法——一次呼叫，自動整合所有資料。

        Args:
            symbol: 股票代號
            days_back: 往回幾天
            include_news: 是否包含新聞
            include_financials: 是否包含財報事件
            include_macro: 是否包含總經事件
            include_price_events: 是否包含價格/量異常事件

        Returns:
            StockTimeline 物件
        """
        market = 'TW' if self._is_taiwan_stock(symbol) else 'US'
        timeline = StockTimeline(symbol=symbol, market=market)

        start_date = date.today() - timedelta(days=days_back)
        end_date = date.today()

        # 1. 取得價格資料（其他分析的基礎）
        logger.info(f"[Context] 取得 {symbol} 價格資料...")
        try:
            price_df = self.data_manager.fetch_prices(
                symbol,
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d'),
            )
            timeline.price_data = price_df
        except Exception as e:
            logger.error(f"[Context] 價格資料取得失敗: {e}")
            price_df = pd.DataFrame()

        # 2. 偵測價格/量異常事件
        if include_price_events and not price_df.empty:
            logger.info(f"[Context] 偵測 {symbol} 價格異常...")
            price_events = self._detect_price_events(symbol, price_df)
            for event in price_events:
                timeline.add_event(event)

        # 3. 財報事件
        if include_financials:
            logger.info(f"[Context] 取得 {symbol} 財報事件...")
            financial_events = self._get_financial_events(symbol, market)
            for event in financial_events:
                timeline.add_event(event)

        # 4. 新聞
        if include_news:
            logger.info(f"[Context] 取得 {symbol} 新聞...")
            news_events = self._get_news_events(symbol, days_back)
            for event in news_events:
                timeline.add_event(event)

        # 5. 總經事件
        if include_macro:
            logger.info(f"[Context] 取得總經事件...")
            macro_events = self._get_macro_events(days_back)
            for event in macro_events:
                timeline.add_event(event)

        timeline.sort_events()
        logger.info(f"[Context] {symbol} 時間軸建構完成，共 {len(timeline.events)} 個事件")

        return timeline

    def get_context_card(self, symbol: str) -> Dict[str, Any]:
        """
        產出「背景卡片」—— 精簡版的背景資訊，適合 Dashboard 顯示。

        包含：
        - 最新財報亮點
        - 最近重要新聞（前 3 則）
        - 目前總經環境快照
        - 近期價格異常事件

        Args:
            symbol: 股票代號

        Returns:
            背景卡片字典
        """
        card = {
            'symbol': symbol,
            'market': 'TW' if self._is_taiwan_stock(symbol) else 'US',
            'fetch_time': datetime.now().isoformat(),
        }

        # 財報亮點
        try:
            ratios = self.financial_manager.get_key_ratios(symbol)
            card['key_ratios'] = ratios
        except Exception as e:
            logger.warning(f"背景卡片 - 財報比率取得失敗: {e}")
            card['key_ratios'] = {}

        # 最近新聞
        try:
            news = self.news_manager.get_company_news(symbol, days_back=7)
            card['recent_news'] = news[:5]  # 只取前 5 則
        except Exception as e:
            logger.warning(f"背景卡片 - 新聞取得失敗: {e}")
            card['recent_news'] = []

        # 總經快照
        try:
            macro_snapshot = {}
            for indicator in ['FED_RATE', 'CPI', 'VIX']:
                df = self.news_manager.get_macro_indicator(indicator)
                if not df.empty:
                    latest = df.iloc[-1]
                    macro_snapshot[indicator] = {
                        'value': float(latest['value']),
                        'date': str(latest['date']),
                    }
            card['macro_snapshot'] = macro_snapshot
        except Exception as e:
            logger.warning(f"背景卡片 - 總經快照取得失敗: {e}")
            card['macro_snapshot'] = {}

        # 台股特有：月營收
        if self._is_taiwan_stock(symbol):
            try:
                rev = self.financial_manager.get_monthly_revenue(symbol)
                if not rev.empty:
                    latest_rev = rev.iloc[-1]
                    card['monthly_revenue'] = {
                        'revenue': float(latest_rev.get('revenue', 0)),
                        'yoy': float(latest_rev.get('revenue_yoy', 0)),
                        'mom': float(latest_rev.get('revenue_mom', 0)),
                        'date': str(latest_rev.get('date', '')),
                    }
            except Exception:
                pass

        return card

    def analyze_earnings_reaction(
        self,
        symbol: str,
        window_days: int = 5,
    ) -> Dict[str, Any]:
        """
        分析「財報公布前後的股價反應」。

        計算財報公布日前後 N 天的累積報酬，
        看市場對財報的即時反應。

        Args:
            symbol: 股票代號
            window_days: 前後觀察天數

        Returns:
            字典包含每次財報公布的股價反應
        """
        analysis = {
            'symbol': symbol,
            'window_days': window_days,
            'reactions': [],
        }

        # 取得歷史價格（長期）
        try:
            price_df = self.data_manager.fetch_prices(
                symbol,
                (date.today() - timedelta(days=365 * 2)).strftime('%Y-%m-%d'),
                date.today().strftime('%Y-%m-%d'),
            )
            if price_df.empty:
                return analysis
        except Exception:
            return analysis

        # 取得 EPS 歷史（財報發布日期）
        if not self._is_taiwan_stock(symbol):
            earnings = self.news_manager.get_earnings_history(symbol)
            if earnings is None or earnings.empty:
                return analysis

            # 確保有日期欄位
            if 'Earnings Date' in earnings.columns:
                report_dates = pd.to_datetime(earnings['Earnings Date'])
            elif 'date' in earnings.columns:
                report_dates = pd.to_datetime(earnings['date'])
            else:
                return analysis

            for report_date in report_dates:
                reaction = self._compute_price_reaction(
                    price_df, report_date, window_days
                )
                if reaction:
                    analysis['reactions'].append(reaction)

        return analysis

    # -----------------------------------------------------------------
    # 內部方法：偵測事件
    # -----------------------------------------------------------------

    def _detect_price_events(
        self,
        symbol: str,
        price_df: pd.DataFrame,
        price_threshold: float = 0.03,   # 3% 漲跌
        volume_threshold: float = 2.0,    # 成交量 > 20日均量的 2 倍
    ) -> List[ContextEvent]:
        """
        偵測價格與成交量異常事件。

        Args:
            symbol: 股票代號
            price_df: 價格 DataFrame
            price_threshold: 日漲跌幅門檻
            volume_threshold: 量能倍數門檻

        Returns:
            事件列表
        """
        events = []

        if price_df.empty or 'close' not in price_df.columns:
            return events

        df = price_df.copy()
        df = df.sort_values('date')

        # 計算日報酬率
        df['daily_return'] = df['close'].pct_change()

        # 計算 20 日均量
        if 'volume' in df.columns:
            df['avg_volume_20'] = df['volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['volume'] / df['avg_volume_20']

        for _, row in df.iterrows():
            # 偵測大漲/大跌
            ret = row.get('daily_return', 0)
            if pd.notna(ret) and abs(ret) >= price_threshold:
                impact = 'positive' if ret > 0 else 'negative'
                importance = min(5, int(abs(ret) / price_threshold) + 2)

                events.append(ContextEvent(
                    event_type=EventType.PRICE_SPIKE,
                    date=pd.Timestamp(row['date']).to_pydatetime(),
                    title=f"{symbol} 單日{'大漲' if ret > 0 else '大跌'} {ret:.1%}",
                    description=f"收盤 {row['close']:.2f}，漲跌幅 {ret:+.2%}",
                    impact=impact,
                    importance=importance,
                    data={
                        'close': float(row['close']),
                        'return': float(ret),
                        'volume': float(row.get('volume', 0)),
                    },
                    source='price_detection',
                ))

            # 偵測量能異常
            vol_ratio = row.get('volume_ratio', 0)
            if pd.notna(vol_ratio) and vol_ratio >= volume_threshold:
                importance = min(5, int(vol_ratio / volume_threshold) + 1)

                events.append(ContextEvent(
                    event_type=EventType.VOLUME_SPIKE,
                    date=pd.Timestamp(row['date']).to_pydatetime(),
                    title=f"{symbol} 量能放大 {vol_ratio:.1f} 倍",
                    description=f"成交量 {row.get('volume', 0):,.0f}，為 20 日均量的 {vol_ratio:.1f} 倍",
                    impact='neutral',
                    importance=importance,
                    data={
                        'volume': float(row.get('volume', 0)),
                        'avg_volume_20': float(row.get('avg_volume_20', 0)),
                        'volume_ratio': float(vol_ratio),
                    },
                    source='volume_detection',
                ))

        return events

    def _get_financial_events(
        self, symbol: str, market: str
    ) -> List[ContextEvent]:
        """從財報資料產生事件。"""
        events = []

        try:
            if market == 'TW':
                # 台股：月營收事件
                rev = self.financial_manager.get_monthly_revenue(symbol)
                if not rev.empty:
                    for _, row in rev.tail(6).iterrows():  # 最近 6 個月
                        yoy = row.get('revenue_yoy', 0)
                        if pd.notna(yoy):
                            impact = 'positive' if yoy > 0 else 'negative'
                            importance = self._yoy_to_importance(yoy)

                            events.append(ContextEvent(
                                event_type=EventType.MONTHLY_REVENUE,
                                date=pd.Timestamp(row['date']).to_pydatetime(),
                                title=f"{symbol} 月營收 YoY {yoy:+.1f}%",
                                description=f"營收 {row.get('revenue', 0):,.0f}，年增 {yoy:+.1f}%",
                                impact=impact,
                                importance=importance,
                                data={
                                    'revenue': float(row.get('revenue', 0)),
                                    'yoy': float(yoy),
                                    'mom': float(row.get('revenue_mom', 0)),
                                },
                                source='finmind_revenue',
                            ))

            else:
                # 美股：EPS surprise 事件
                earnings = self.news_manager.get_earnings_history(symbol)
                if earnings is not None and not earnings.empty:
                    for _, row in earnings.iterrows():
                        eps_actual = row.get('epsActual', row.get('Reported EPS'))
                        eps_estimate = row.get('epsEstimate', row.get('EPS Estimate'))

                        if pd.notna(eps_actual) and pd.notna(eps_estimate) and eps_estimate != 0:
                            surprise_pct = (eps_actual - eps_estimate) / abs(eps_estimate) * 100
                            impact = 'positive' if surprise_pct > 0 else 'negative'
                            importance = min(5, int(abs(surprise_pct) / 5) + 2)

                            # 嘗試取得日期
                            event_date = row.get('Earnings Date', row.get('date', datetime.now()))
                            if isinstance(event_date, str):
                                event_date = pd.Timestamp(event_date).to_pydatetime()
                            elif hasattr(event_date, 'to_pydatetime'):
                                event_date = event_date.to_pydatetime()

                            events.append(ContextEvent(
                                event_type=EventType.EARNINGS_RELEASE,
                                date=event_date,
                                title=f"{symbol} EPS Surprise {surprise_pct:+.1f}%",
                                description=(
                                    f"實際 EPS ${eps_actual:.2f} vs "
                                    f"預估 ${eps_estimate:.2f} "
                                    f"(差異 {surprise_pct:+.1f}%)"
                                ),
                                impact=impact,
                                importance=importance,
                                data={
                                    'eps_actual': float(eps_actual),
                                    'eps_estimate': float(eps_estimate),
                                    'surprise_pct': float(surprise_pct),
                                },
                                source='earnings_history',
                            ))

        except Exception as e:
            logger.error(f"取得財報事件失敗 {symbol}: {e}")

        return events

    def _get_news_events(
        self, symbol: str, days_back: int
    ) -> List[ContextEvent]:
        """從新聞資料產生事件。"""
        events = []

        try:
            news_list = self.news_manager.get_company_news(symbol, days_back=days_back)

            for news in news_list[:15]:  # 最多 15 則新聞
                try:
                    news_date = datetime.fromisoformat(news.get('datetime', ''))
                except Exception:
                    news_date = datetime.now()

                events.append(ContextEvent(
                    event_type=EventType.NEWS,
                    date=news_date,
                    title=news.get('headline', ''),
                    description=news.get('summary', ''),
                    impact='neutral',  # 新聞情緒需要 NLP 才能判斷
                    importance=2,
                    data=news,
                    source=news.get('source', news.get('provider', '')),
                    url=news.get('url', ''),
                ))

        except Exception as e:
            logger.error(f"取得新聞事件失敗 {symbol}: {e}")

        return events

    def _get_macro_events(self, days_back: int) -> List[ContextEvent]:
        """取得總經重大事件。"""
        events = []

        # 定義要追蹤的總經指標和門檻
        macro_checks = [
            ('FED_RATE', '聯準會利率', 'neutral', 4),
            ('CPI', 'CPI 消費者物價指數', 'neutral', 4),
            ('VIX', 'VIX 恐慌指數', 'neutral', 3),
        ]

        try:
            for indicator, name, default_impact, importance in macro_checks:
                df = self.news_manager.get_macro_indicator(indicator)
                if df.empty:
                    continue

                # 只取最近的資料
                cutoff = datetime.now() - timedelta(days=days_back)
                df = df[df['date'] >= cutoff]

                if df.empty:
                    continue

                # 偵測變動（與前一期比較）
                df = df.sort_values('date')
                df['change'] = df['value'].diff()

                for _, row in df.iterrows():
                    change = row.get('change', 0)
                    if pd.notna(change) and change != 0:
                        impact = 'neutral'
                        # VIX 上升 = negative, 下降 = positive
                        if indicator == 'VIX':
                            impact = 'negative' if change > 0 else 'positive'
                        # FED_RATE 上升 = 偏緊縮
                        elif indicator == 'FED_RATE':
                            impact = 'negative' if change > 0 else 'positive'

                        events.append(ContextEvent(
                            event_type=EventType.MACRO_EVENT,
                            date=pd.Timestamp(row['date']).to_pydatetime(),
                            title=f"{name}: {row['value']:.2f} ({change:+.2f})",
                            description=f"{indicator} 從上期變動 {change:+.2f}",
                            impact=impact,
                            importance=importance,
                            data={
                                'indicator': indicator,
                                'value': float(row['value']),
                                'change': float(change),
                            },
                            source='fred',
                        ))

        except Exception as e:
            logger.error(f"取得總經事件失敗: {e}")

        return events

    def _compute_price_reaction(
        self,
        price_df: pd.DataFrame,
        event_date,
        window_days: int,
    ) -> Optional[Dict[str, Any]]:
        """
        計算某事件日期前後的股價反應。

        Args:
            price_df: 價格 DataFrame
            event_date: 事件日期
            window_days: 前後觀察天數

        Returns:
            反應分析字典
        """
        try:
            if isinstance(event_date, str):
                event_date = pd.Timestamp(event_date)

            df = price_df.copy()
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')

            # 找到最接近事件日的交易日
            idx = df['date'].searchsorted(event_date)
            if idx >= len(df) or idx < window_days:
                return None

            # 事件日前後的價格
            pre_prices = df.iloc[max(0, idx - window_days):idx]
            post_prices = df.iloc[idx:min(len(df), idx + window_days + 1)]

            if pre_prices.empty or post_prices.empty:
                return None

            pre_close = pre_prices.iloc[-1]['close']
            event_close = df.iloc[idx]['close']
            post_close = post_prices.iloc[-1]['close']

            return {
                'event_date': str(event_date),
                'pre_return': float((event_close - pre_close) / pre_close),
                'post_return': float((post_close - event_close) / event_close),
                'total_return': float((post_close - pre_close) / pre_close),
                'pre_close': float(pre_close),
                'event_close': float(event_close),
                'post_close': float(post_close),
            }

        except Exception as e:
            logger.error(f"計算股價反應失敗: {e}")
            return None

    @staticmethod
    def _yoy_to_importance(yoy: float) -> int:
        """月營收 YoY 成長率轉成重要度等級。"""
        abs_yoy = abs(yoy)
        if abs_yoy >= 50:
            return 5
        elif abs_yoy >= 30:
            return 4
        elif abs_yoy >= 15:
            return 3
        elif abs_yoy >= 5:
            return 2
        return 1
