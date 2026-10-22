# -*- coding: utf-8 -*-
"""
News Sentiment Analysis Module (新聞情緒分析模組) — Phase 2

三種分析方案，由簡到難：
- Level 1: 關鍵字規則 (Keyword Rules) — 不需安裝額外套件
- Level 2: FinBERT 模型 — 需要 transformers + torch
- Level 3: LLM API — 需要 Anthropic API key

使用方式：
    from core.sentiment import SentimentAnalyzer

    analyzer = SentimentAnalyzer()  # 預設用 Level 1

    # 分析單則新聞
    result = analyzer.analyze('台積電法說會釋出正面展望，AI 營收大幅成長')
    # → {'score': 0.8, 'label': 'positive', 'method': 'keyword'}

    # 批次分析新聞列表
    results = analyzer.analyze_news_list(news_list)

    # 計算某檔股票的整體情緒分數
    sentiment = analyzer.get_stock_sentiment('AAPL', days_back=7)
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)


# =============================================================================
# Level 1: 關鍵字規則（預設方案）
# =============================================================================

# --- 中文關鍵字 ---
POSITIVE_KEYWORDS_ZH = [
    '成長', '獲利', '突破', '新高', '上調', '超預期', '利多',
    '擴張', '增資', '併購', '合作', '訂單', '營收增', '需求強勁',
    '復甦', '加碼', '買超', '看好', '樂觀', '上修', '創新高',
    '大幅成長', '年增', '月增', '毛利率提升', '市佔率',
    'AI', '人工智慧', '資料中心', '雲端',
]

NEGATIVE_KEYWORDS_ZH = [
    '衰退', '下修', '裁員', '虧損', '低於預期', '利空',
    '調降', '減產', '庫存', '供過於求', '跌停', '崩跌',
    '賣超', '看壞', '悲觀', '下滑', '萎縮', '風險',
    '制裁', '關稅', '貿易戰', '違約', '倒閉', '破產',
    '連續衰退', '營收減', '毛利率下降', '出貨減少',
]

# --- 英文關鍵字 ---
POSITIVE_KEYWORDS_EN = [
    'beat', 'exceed', 'upgrade', 'growth', 'record', 'bullish',
    'surge', 'rally', 'breakout', 'outperform', 'strong demand',
    'raised guidance', 'buy rating', 'expansion', 'innovation',
    'partnership', 'dividend increase', 'buyback', 'acquisition',
    'revenue growth', 'profit', 'margin expansion', 'ai demand',
]

NEGATIVE_KEYWORDS_EN = [
    'miss', 'downgrade', 'decline', 'layoff', 'bearish', 'loss',
    'sell-off', 'crash', 'underperform', 'weak guidance', 'warning',
    'cut', 'reduced', 'tariff', 'sanction', 'recession', 'default',
    'bankruptcy', 'debt', 'writedown', 'inventory', 'oversupply',
    'margin compression', 'revenue decline', 'slowdown',
]


class KeywordSentimentAnalyzer:
    """
    關鍵字規則情緒分析器。

    原理：計算正面/負面關鍵字出現次數，算出加權分數。
    優點：速度快、不需額外套件、可自訂關鍵字。
    缺點：無法理解語境（如「營收成長不如預期」會被誤判）。
    """

    def __init__(
        self,
        positive_zh=None,
        negative_zh=None,
        positive_en=None,
        negative_en=None,
    ):
        self.positive_zh = positive_zh or POSITIVE_KEYWORDS_ZH
        self.negative_zh = negative_zh or NEGATIVE_KEYWORDS_ZH
        self.positive_en = positive_en or POSITIVE_KEYWORDS_EN
        self.negative_en = negative_en or NEGATIVE_KEYWORDS_EN

    def analyze(self, text: str) -> Dict[str, Any]:
        """
        分析一段文字的情緒。

        Args:
            text: 新聞標題或摘要

        Returns:
            {
                'score': float,       # -1.0 ~ +1.0
                'label': str,         # 'positive', 'negative', 'neutral'
                'confidence': float,  # 0.0 ~ 1.0
                'method': 'keyword',
                'pos_count': int,
                'neg_count': int,
                'matched_keywords': list,
            }
        """
        if not text:
            return self._neutral_result()

        text_lower = text.lower()
        matched = []

        # 中文關鍵字匹配
        pos_count = 0
        for kw in self.positive_zh:
            if kw in text:
                pos_count += 1
                matched.append(f'+{kw}')

        neg_count = 0
        for kw in self.negative_zh:
            if kw in text:
                neg_count += 1
                matched.append(f'-{kw}')

        # 英文關鍵字匹配
        for kw in self.positive_en:
            if kw in text_lower:
                pos_count += 1
                matched.append(f'+{kw}')

        for kw in self.negative_en:
            if kw in text_lower:
                neg_count += 1
                matched.append(f'-{kw}')

        total = pos_count + neg_count
        if total == 0:
            return self._neutral_result()

        score = (pos_count - neg_count) / total  # -1.0 ~ +1.0
        confidence = min(total / 5, 1.0)  # 匹配越多越有信心

        if score > 0.2:
            label = 'positive'
        elif score < -0.2:
            label = 'negative'
        else:
            label = 'neutral'

        return {
            'score': round(score, 3),
            'label': label,
            'confidence': round(confidence, 3),
            'method': 'keyword',
            'pos_count': pos_count,
            'neg_count': neg_count,
            'matched_keywords': matched,
        }

    def _neutral_result(self):
        return {
            'score': 0.0,
            'label': 'neutral',
            'confidence': 0.0,
            'method': 'keyword',
            'pos_count': 0,
            'neg_count': 0,
            'matched_keywords': [],
        }


# =============================================================================
# Level 2: FinBERT (需要 transformers + torch)
# =============================================================================

class FinBERTSentimentAnalyzer:
    """
    使用 FinBERT 預訓練模型做金融新聞情緒分析。

    FinBERT 是專門在金融文本上微調的 BERT 模型，
    對英文金融新聞的準確率遠高於關鍵字規則。

    安裝：pip install transformers torch
    首次使用會自動下載模型（約 400MB）。
    """

    def __init__(self, model_name: str = "ProsusAI/finbert"):
        self.model_name = model_name
        self._classifier = None

    @property
    def classifier(self):
        if self._classifier is None:
            try:
                from transformers import pipeline
                self._classifier = pipeline(
                    "sentiment-analysis",
                    model=self.model_name,
                )
                logger.info(f"FinBERT 模型已載入: {self.model_name}")
            except ImportError:
                logger.error(
                    "請安裝 transformers 和 torch:\n"
                    "pip install transformers torch"
                )
                raise
        return self._classifier

    def analyze(self, text: str) -> Dict[str, Any]:
        """
        用 FinBERT 分析情緒。

        Args:
            text: 英文新聞文字（FinBERT 對英文效果最好）

        Returns:
            情緒分析結果
        """
        if not text:
            return {'score': 0.0, 'label': 'neutral', 'confidence': 0.0, 'method': 'finbert'}

        try:
            # FinBERT 限制 512 tokens
            truncated = text[:512]
            result = self.classifier(truncated)[0]

            label = result['label'].lower()
            confidence = result['score']

            # 轉換成 -1 ~ +1 的 score
            if label == 'positive':
                score = confidence
            elif label == 'negative':
                score = -confidence
            else:
                score = 0.0

            return {
                'score': round(score, 3),
                'label': label,
                'confidence': round(confidence, 3),
                'method': 'finbert',
            }

        except Exception as e:
            logger.error(f"FinBERT 分析失敗: {e}")
            return {'score': 0.0, 'label': 'neutral', 'confidence': 0.0, 'method': 'finbert'}


# =============================================================================
# 統一介面 (Unified Interface)
# =============================================================================

class SentimentAnalyzer:
    """
    統一的情緒分析器。

    自動選擇最佳可用方案：
    - 有 FinBERT → 英文新聞用 FinBERT，中文用 keyword
    - 沒有 → 全部用 keyword

    Usage:
        analyzer = SentimentAnalyzer()

        # 分析單則
        result = analyzer.analyze('Apple beats earnings expectations')

        # 批次分析
        results = analyzer.analyze_news_list(news_list)

        # 股票整體情緒
        score = analyzer.get_stock_sentiment('AAPL')
    """

    def __init__(self, use_finbert: bool = False):
        self.keyword_analyzer = KeywordSentimentAnalyzer()
        self._finbert_analyzer = None

        if use_finbert:
            try:
                self._finbert_analyzer = FinBERTSentimentAnalyzer()
                # 預載測試
                self._finbert_analyzer.classifier
                logger.info("SentimentAnalyzer: FinBERT 可用")
            except Exception:
                logger.warning("SentimentAnalyzer: FinBERT 不可用，回退到 keyword")
                self._finbert_analyzer = None

    def analyze(self, text: str) -> Dict[str, Any]:
        """
        分析單段文字的情緒。

        自動判斷語言，選擇合適的分析器。
        """
        if not text:
            return {'score': 0.0, 'label': 'neutral', 'confidence': 0.0, 'method': 'none'}

        # 判斷是否包含中文
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))

        # 中文 → 一律用 keyword（FinBERT 對中文效果不好）
        if has_chinese:
            return self.keyword_analyzer.analyze(text)

        # 英文 → 優先用 FinBERT
        if self._finbert_analyzer is not None:
            return self._finbert_analyzer.analyze(text)

        # Fallback: keyword
        return self.keyword_analyzer.analyze(text)

    def analyze_news_list(
        self,
        news_list: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        批次分析新聞列表。

        在每則新聞字典中加入 'sentiment' 欄位。

        Args:
            news_list: 新聞列表（從 NewsManager 取得的格式）

        Returns:
            加入情緒分數的新聞列表
        """
        for news in news_list:
            text = news.get('headline', '') + ' ' + news.get('summary', '')
            sentiment = self.analyze(text.strip())
            news['sentiment'] = sentiment

        return news_list

    def get_stock_sentiment(
        self,
        symbol: str,
        days_back: int = 7,
        news_manager=None,
    ) -> Dict[str, Any]:
        """
        計算某檔股票的整體新聞情緒。

        把最近 N 天的所有新聞情緒分數做加權平均，
        越新的新聞權重越高。

        Args:
            symbol: 股票代號
            days_back: 回溯天數
            news_manager: NewsManager 實例（不傳則自動建立）

        Returns:
            {
                'symbol': str,
                'avg_score': float,       # 加權平均情緒分數
                'label': str,             # 整體情緒標籤
                'total_news': int,        # 分析的新聞數量
                'positive_count': int,
                'negative_count': int,
                'neutral_count': int,
                'details': list,          # 每則新聞的分析結果
            }
        """
        if news_manager is None:
            from .news_fetcher import NewsManager
            news_manager = NewsManager()

        news_list = news_manager.get_company_news(symbol, days_back=days_back)

        if not news_list:
            return {
                'symbol': symbol,
                'avg_score': 0.0,
                'label': 'neutral',
                'total_news': 0,
                'positive_count': 0,
                'negative_count': 0,
                'neutral_count': 0,
                'details': [],
            }

        # 分析每則新聞
        analyzed = self.analyze_news_list(news_list)

        # 加權平均（越新權重越高）
        scores = []
        weights = []
        pos_count = neg_count = neu_count = 0

        for i, news in enumerate(analyzed):
            sentiment = news.get('sentiment', {})
            score = sentiment.get('score', 0)
            # 越新的新聞權重越高（第一則=最新，權重最大）
            weight = 1.0 / (i + 1)

            scores.append(score)
            weights.append(weight)

            label = sentiment.get('label', 'neutral')
            if label == 'positive':
                pos_count += 1
            elif label == 'negative':
                neg_count += 1
            else:
                neu_count += 1

        # 加權平均
        total_weight = sum(weights)
        if total_weight > 0:
            avg_score = sum(s * w for s, w in zip(scores, weights)) / total_weight
        else:
            avg_score = 0.0

        if avg_score > 0.15:
            overall_label = 'positive'
        elif avg_score < -0.15:
            overall_label = 'negative'
        else:
            overall_label = 'neutral'

        return {
            'symbol': symbol,
            'avg_score': round(avg_score, 3),
            'label': overall_label,
            'total_news': len(analyzed),
            'positive_count': pos_count,
            'negative_count': neg_count,
            'neutral_count': neu_count,
            'details': [
                {
                    'headline': n.get('headline', ''),
                    'sentiment': n.get('sentiment', {}),
                }
                for n in analyzed[:10]  # 最多回傳 10 則
            ],
        }
