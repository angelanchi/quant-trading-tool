# -*- coding: utf-8 -*-
"""
Multi-Factor Scoring Model (多因子評分模型) — Phase 3

把技術面、基本面、情緒面三大類因子合成一個綜合評分，
對觀察清單的股票做排名。

三大因子群組與權重（可自訂）：
- 技術面 40%: RSI 位置、MACD 方向、均線排列、布林位置
- 基本面 40%: 營收成長(台)/P/E(美)、獲利能力、財務健全度
- 情緒面 20%: 新聞情緒分數、VIX 環境

CQF 學習連結：
這就是量化金融裡的「因子投資」。正式做法會用 Fama-French
三因子/五因子模型，但核心概念一樣：把多個信號標準化 → 加權 → 排名。

Usage:
    from core.multi_factor import MultiFactorModel

    model = MultiFactorModel()

    # 單檔評分
    result = model.score_stock('AAPL')

    # 整個觀察清單排名
    ranking = model.rank_watchlist(['2330', '2454', 'AAPL', 'NVDA'])
"""

from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import logging

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# 設定
# =============================================================================

@dataclass
class FactorWeights:
    """
    因子權重設定。

    三大類的權重加總應 = 1.0。
    你可以根據自己的投資風格調整。
    """
    technical: float = 0.40    # 技術面權重
    fundamental: float = 0.40  # 基本面權重
    sentiment: float = 0.20    # 情緒面權重

    def __post_init__(self):
        total = self.technical + self.fundamental + self.sentiment
        if abs(total - 1.0) > 0.01:
            logger.warning(f"因子權重加總 {total:.2f} ≠ 1.0，已自動正規化")
            self.technical /= total
            self.fundamental /= total
            self.sentiment /= total


@dataclass
class FactorResult:
    """單一因子的評分結果。"""
    name: str
    raw_value: Any        # 原始值
    score: float          # 0 ~ 100 分
    weight: float         # 權重
    description: str = "" # 說明


# =============================================================================
# Multi-Factor Model
# =============================================================================

class MultiFactorModel:
    """
    多因子評分模型。

    給每檔股票一個 0~100 分的綜合評分，
    方便你快速篩選「現在最值得關注的股票」。

    評分邏輯：
    - 90~100: 強力推薦關注（技術+基本+情緒都好）
    - 70~89:  值得關注
    - 50~69:  中性，觀望
    - 30~49:  偏弱，注意風險
    - 0~29:   警戒，可能需要停損
    """

    def __init__(
        self,
        weights: Optional[FactorWeights] = None,
        data_manager=None,
        financial_manager=None,
        news_manager=None,
        sentiment_analyzer=None,
    ):
        self.weights = weights or FactorWeights()
        self._data_manager = data_manager
        self._financial_manager = financial_manager
        self._news_manager = news_manager
        self._sentiment_analyzer = sentiment_analyzer

    # --- Lazy init ---

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

    @property
    def sentiment_analyzer(self):
        if self._sentiment_analyzer is None:
            from .sentiment import SentimentAnalyzer
            self._sentiment_analyzer = SentimentAnalyzer()
        return self._sentiment_analyzer

    def _is_taiwan_stock(self, symbol: str) -> bool:
        clean = symbol.upper().strip().replace('.TW', '').replace('.TWO', '')
        return clean.isdigit() and len(clean) in (4, 5)

    # -----------------------------------------------------------------
    # 主要 API
    # -----------------------------------------------------------------

    def score_stock(self, symbol: str) -> Dict[str, Any]:
        """
        對一檔股票做完整的多因子評分。

        Args:
            symbol: 股票代號

        Returns:
            評分結果字典
        """
        result = {
            'symbol': symbol,
            'market': 'TW' if self._is_taiwan_stock(symbol) else 'US',
            'timestamp': datetime.now().isoformat(),
            'factors': {},
        }

        # 1. 技術面評分
        tech_score, tech_factors = self._technical_score(symbol)
        result['factors']['technical'] = {
            'score': tech_score,
            'weight': self.weights.technical,
            'weighted_score': tech_score * self.weights.technical,
            'details': tech_factors,
        }

        # 2. 基本面評分
        fund_score, fund_factors = self._fundamental_score(symbol)
        result['factors']['fundamental'] = {
            'score': fund_score,
            'weight': self.weights.fundamental,
            'weighted_score': fund_score * self.weights.fundamental,
            'details': fund_factors,
        }

        # 3. 情緒面評分
        sent_score, sent_factors = self._sentiment_score(symbol)
        result['factors']['sentiment'] = {
            'score': sent_score,
            'weight': self.weights.sentiment,
            'weighted_score': sent_score * self.weights.sentiment,
            'details': sent_factors,
        }

        # 綜合分數
        total = (
            tech_score * self.weights.technical +
            fund_score * self.weights.fundamental +
            sent_score * self.weights.sentiment
        )
        result['total_score'] = round(total, 1)
        result['rating'] = self._score_to_rating(total)

        return result

    def rank_watchlist(self, symbols: List[str]) -> pd.DataFrame:
        """
        把觀察清單的所有股票排名。

        Args:
            symbols: 股票代號清單

        Returns:
            排名 DataFrame，由高到低
        """
        scores = []
        for symbol in symbols:
            try:
                result = self.score_stock(symbol)
                scores.append({
                    '代碼': symbol,
                    '市場': result['market'],
                    '總分': result['total_score'],
                    '評等': result['rating'],
                    '技術面': result['factors']['technical']['score'],
                    '基本面': result['factors']['fundamental']['score'],
                    '情緒面': result['factors']['sentiment']['score'],
                })
            except Exception as e:
                logger.error(f"評分失敗 {symbol}: {e}")
                scores.append({
                    '代碼': symbol,
                    '市場': '?',
                    '總分': 0,
                    '評等': '無法評分',
                    '技術面': 0,
                    '基本面': 0,
                    '情緒面': 0,
                })

        df = pd.DataFrame(scores)
        df = df.sort_values('總分', ascending=False).reset_index(drop=True)
        df.index = df.index + 1  # 排名從 1 開始
        df.index.name = '排名'

        return df

    # -----------------------------------------------------------------
    # 技術面評分 (40%)
    # -----------------------------------------------------------------

    def _technical_score(self, symbol: str) -> tuple:
        """
        技術面評分。

        因子：
        - RSI 位置 (30~70 最好)
        - MACD 方向 (柱狀圖擴大 = 好)
        - 均線排列 (多頭排列 = 好)
        - 價格在布林通道的位置
        """
        factors = []
        sub_scores = []

        try:
            end = date.today()
            start = end - timedelta(days=120)
            df = self.data_manager.fetch_prices(
                symbol, start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')
            )

            if df.empty or len(df) < 30:
                return 50.0, [FactorResult('data', None, 50, 1.0, '資料不足')]

            close = df['close']

            # 1. RSI (25分)
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss.replace(0, np.nan)
            rsi = (100 - (100 / (1 + rs))).iloc[-1]

            if pd.notna(rsi):
                # RSI 50 = 最佳, 偏離越多分越低
                if 40 <= rsi <= 60:
                    rsi_score = 80
                    desc = f'RSI {rsi:.0f} — 中性偏好'
                elif 30 <= rsi < 40 or 60 < rsi <= 70:
                    rsi_score = 60
                    desc = f'RSI {rsi:.0f} — 尚可'
                elif rsi < 30:
                    rsi_score = 70  # 超賣可能是買點
                    desc = f'RSI {rsi:.0f} — 超賣，可能反彈'
                else:
                    rsi_score = 30  # 超買風險
                    desc = f'RSI {rsi:.0f} — 超買，注意回檔'
            else:
                rsi_score = 50
                desc = 'RSI 無法計算'

            factors.append(FactorResult('RSI', rsi, rsi_score, 0.25, desc))
            sub_scores.append(rsi_score * 0.25)

            # 2. MACD 方向 (25分)
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd = ema12 - ema26
            signal = macd.ewm(span=9, adjust=False).mean()
            hist = macd - signal

            if len(hist) >= 2:
                latest_hist = hist.iloc[-1]
                prev_hist = hist.iloc[-2]

                if latest_hist > 0 and latest_hist > prev_hist:
                    macd_score = 85
                    desc = 'MACD 多頭且擴大'
                elif latest_hist > 0:
                    macd_score = 65
                    desc = 'MACD 多頭但收斂'
                elif latest_hist < 0 and latest_hist > prev_hist:
                    macd_score = 55
                    desc = 'MACD 空頭但收斂（可能翻多）'
                else:
                    macd_score = 30
                    desc = 'MACD 空頭且擴大'
            else:
                macd_score = 50
                desc = 'MACD 資料不足'

            factors.append(FactorResult('MACD', latest_hist if len(hist) >= 2 else None, macd_score, 0.25, desc))
            sub_scores.append(macd_score * 0.25)

            # 3. 均線排列 (25分)
            ma5 = close.rolling(5).mean().iloc[-1]
            ma20 = close.rolling(20).mean().iloc[-1]
            ma60 = close.rolling(60).mean().iloc[-1] if len(close) >= 60 else ma20

            current = close.iloc[-1]

            if current > ma5 > ma20 > ma60:
                ma_score = 90
                desc = '完美多頭排列'
            elif current > ma20 and ma5 > ma20:
                ma_score = 70
                desc = '偏多排列'
            elif current < ma5 < ma20 < ma60:
                ma_score = 15
                desc = '空頭排列'
            elif current < ma20:
                ma_score = 35
                desc = '偏空，在均線下方'
            else:
                ma_score = 50
                desc = '均線糾結，方向不明'

            factors.append(FactorResult('均線排列', None, ma_score, 0.25, desc))
            sub_scores.append(ma_score * 0.25)

            # 4. 動量 — 近 20 日報酬 (25分)
            ret_20d = (close.iloc[-1] / close.iloc[-20] - 1) * 100 if len(close) >= 20 else 0

            if ret_20d > 10:
                mom_score = 85
                desc = f'近20日 {ret_20d:+.1f}% — 強勢'
            elif ret_20d > 3:
                mom_score = 70
                desc = f'近20日 {ret_20d:+.1f}% — 偏多'
            elif ret_20d > -3:
                mom_score = 50
                desc = f'近20日 {ret_20d:+.1f}% — 中性'
            elif ret_20d > -10:
                mom_score = 35
                desc = f'近20日 {ret_20d:+.1f}% — 偏弱'
            else:
                mom_score = 15
                desc = f'近20日 {ret_20d:+.1f}% — 弱勢'

            factors.append(FactorResult('動量', ret_20d, mom_score, 0.25, desc))
            sub_scores.append(mom_score * 0.25)

            total = sum(sub_scores)
            return round(total, 1), factors

        except Exception as e:
            logger.error(f"技術面評分失敗 {symbol}: {e}")
            return 50.0, [FactorResult('error', str(e), 50, 1.0, '評分失敗')]

    # -----------------------------------------------------------------
    # 基本面評分 (40%)
    # -----------------------------------------------------------------

    def _fundamental_score(self, symbol: str) -> tuple:
        """
        基本面評分。

        台股因子：月營收 YoY、月營收 MoM
        美股因子：P/E、ROE、營收成長、EPS surprise
        """
        factors = []
        sub_scores = []

        try:
            if self._is_taiwan_stock(symbol):
                return self._tw_fundamental_score(symbol)
            else:
                return self._us_fundamental_score(symbol)

        except Exception as e:
            logger.error(f"基本面評分失敗 {symbol}: {e}")
            return 50.0, [FactorResult('error', str(e), 50, 1.0, '評分失敗')]

    def _tw_fundamental_score(self, symbol: str) -> tuple:
        """台股基本面評分（以月營收為核心）。"""
        factors = []
        sub_scores = []

        rev_df = self.financial_manager.get_monthly_revenue(symbol)
        if rev_df.empty:
            return 50.0, [FactorResult('月營收', None, 50, 1.0, '無資料')]

        latest = rev_df.iloc[-1]

        # 1. 月營收 YoY (50分)
        yoy = latest.get('revenue_yoy', 0)
        if pd.notna(yoy):
            if yoy > 30:
                score = 90
            elif yoy > 15:
                score = 75
            elif yoy > 0:
                score = 60
            elif yoy > -10:
                score = 40
            else:
                score = 20

            factors.append(FactorResult('營收YoY', yoy, score, 0.5, f'YoY {yoy:+.1f}%'))
            sub_scores.append(score * 0.5)
        else:
            factors.append(FactorResult('營收YoY', None, 50, 0.5, '無資料'))
            sub_scores.append(50 * 0.5)

        # 2. 月營收 MoM (25分)
        mom = latest.get('revenue_mom', 0)
        if pd.notna(mom):
            if mom > 10:
                score = 80
            elif mom > 0:
                score = 60
            elif mom > -10:
                score = 45
            else:
                score = 25

            factors.append(FactorResult('營收MoM', mom, score, 0.25, f'MoM {mom:+.1f}%'))
            sub_scores.append(score * 0.25)
        else:
            factors.append(FactorResult('營收MoM', None, 50, 0.25, '無資料'))
            sub_scores.append(50 * 0.25)

        # 3. 營收趨勢（近3月 YoY 是否改善）(25分)
        if len(rev_df) >= 3 and 'revenue_yoy' in rev_df.columns:
            recent_yoy = rev_df['revenue_yoy'].tail(3).dropna()
            if len(recent_yoy) >= 2:
                improving = recent_yoy.iloc[-1] > recent_yoy.iloc[0]
                if improving and recent_yoy.iloc[-1] > 0:
                    score = 85
                    desc = '趨勢改善且正成長'
                elif improving:
                    score = 65
                    desc = '趨勢改善（衰退收斂）'
                elif recent_yoy.iloc[-1] > 0:
                    score = 55
                    desc = '正成長但趨勢走緩'
                else:
                    score = 25
                    desc = '趨勢惡化'
            else:
                score = 50
                desc = '資料不足'
        else:
            score = 50
            desc = '資料不足'

        factors.append(FactorResult('營收趨勢', None, score, 0.25, desc))
        sub_scores.append(score * 0.25)

        total = sum(sub_scores)
        return round(total, 1), factors

    def _us_fundamental_score(self, symbol: str) -> tuple:
        """美股基本面評分。"""
        factors = []
        sub_scores = []

        ratios = self.financial_manager.get_key_ratios(symbol)
        if not ratios:
            return 50.0, [FactorResult('比率', None, 50, 1.0, '無資料')]

        # 1. P/E 估值 (30分)
        pe = ratios.get('pe_ratio')
        if pe and pe > 0:
            if pe < 15:
                score = 80
                desc = f'P/E {pe:.1f} — 低估值'
            elif pe < 25:
                score = 65
                desc = f'P/E {pe:.1f} — 合理'
            elif pe < 40:
                score = 45
                desc = f'P/E {pe:.1f} — 偏高'
            else:
                score = 25
                desc = f'P/E {pe:.1f} — 昂貴'
        else:
            score = 40
            desc = 'P/E 無資料或為負'

        factors.append(FactorResult('P/E', pe, score, 0.3, desc))
        sub_scores.append(score * 0.3)

        # 2. ROE 獲利能力 (25分)
        roe = ratios.get('roe')
        if roe:
            roe_pct = roe * 100
            if roe_pct > 25:
                score = 85
            elif roe_pct > 15:
                score = 70
            elif roe_pct > 5:
                score = 50
            else:
                score = 30
            desc = f'ROE {roe_pct:.1f}%'
        else:
            score = 50
            desc = '無資料'

        factors.append(FactorResult('ROE', roe, score, 0.25, desc))
        sub_scores.append(score * 0.25)

        # 3. 營收成長 (25分)
        rev_growth = ratios.get('revenue_growth')
        if rev_growth:
            growth_pct = rev_growth * 100
            if growth_pct > 20:
                score = 85
            elif growth_pct > 5:
                score = 65
            elif growth_pct > -5:
                score = 45
            else:
                score = 25
            desc = f'Revenue Growth {growth_pct:+.1f}%'
        else:
            score = 50
            desc = '無資料'

        factors.append(FactorResult('營收成長', rev_growth, score, 0.25, desc))
        sub_scores.append(score * 0.25)

        # 4. 分析師共識 (20分)
        rec = ratios.get('recommendation', '')
        rec_scores = {
            'strongbuy': 90, 'strong_buy': 90,
            'buy': 75,
            'hold': 50,
            'sell': 25,
            'strongsell': 10, 'strong_sell': 10,
        }
        rec_key = str(rec).lower().replace(' ', '')
        score = rec_scores.get(rec_key, 50)
        desc = f'分析師: {rec}' if rec else '無資料'

        factors.append(FactorResult('分析師', rec, score, 0.2, desc))
        sub_scores.append(score * 0.2)

        total = sum(sub_scores)
        return round(total, 1), factors

    # -----------------------------------------------------------------
    # 情緒面評分 (20%)
    # -----------------------------------------------------------------

    def _sentiment_score(self, symbol: str) -> tuple:
        """
        情緒面評分。

        因子：
        - 新聞情緒分數 (70%)
        - VIX 環境 (30%)
        """
        factors = []
        sub_scores = []

        # 1. 新聞情緒 (70分)
        try:
            stock_sent = self.sentiment_analyzer.get_stock_sentiment(
                symbol, days_back=7, news_manager=self.news_manager
            )
            avg_score = stock_sent.get('avg_score', 0)

            # 轉成 0~100 分 (-1→0, 0→50, +1→100)
            news_score = (avg_score + 1) / 2 * 100
            news_score = max(0, min(100, news_score))

            total_news = stock_sent.get('total_news', 0)
            label = stock_sent.get('label', 'neutral')
            desc = f'{label} (avg={avg_score:+.2f}, {total_news}則新聞)'

        except Exception as e:
            logger.warning(f"情緒評分失敗 {symbol}: {e}")
            news_score = 50
            desc = '無法取得'

        factors.append(FactorResult('新聞情緒', avg_score if 'avg_score' in dir() else 0, news_score, 0.7, desc))
        sub_scores.append(news_score * 0.7)

        # 2. VIX 環境 (30分)
        try:
            vix_df = self.news_manager.get_macro_indicator('VIX')
            if not vix_df.empty:
                vix = float(vix_df.iloc[-1]['value'])

                if vix < 15:
                    vix_score = 85
                    desc = f'VIX {vix:.1f} — 低波動，市場平靜'
                elif vix < 20:
                    vix_score = 70
                    desc = f'VIX {vix:.1f} — 正常'
                elif vix < 25:
                    vix_score = 50
                    desc = f'VIX {vix:.1f} — 略偏高'
                elif vix < 35:
                    vix_score = 30
                    desc = f'VIX {vix:.1f} — 市場緊張'
                else:
                    vix_score = 10
                    desc = f'VIX {vix:.1f} — 極度恐慌'
            else:
                vix_score = 50
                desc = 'VIX 無資料'

        except Exception:
            vix_score = 50
            desc = 'VIX 無法取得'

        factors.append(FactorResult('VIX環境', None, vix_score, 0.3, desc))
        sub_scores.append(vix_score * 0.3)

        total = sum(sub_scores)
        return round(total, 1), factors

    # -----------------------------------------------------------------
    # 工具
    # -----------------------------------------------------------------

    @staticmethod
    def _score_to_rating(score: float) -> str:
        """分數轉評等文字。"""
        if score >= 80:
            return '★★★★★ 強力關注'
        elif score >= 65:
            return '★★★★ 值得關注'
        elif score >= 50:
            return '★★★ 中性觀望'
        elif score >= 35:
            return '★★ 偏弱注意'
        else:
            return '★ 警戒'
