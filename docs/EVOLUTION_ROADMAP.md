# 系統進化路線圖 — 從監控到智慧決策

## 全貌：四階段進化

```
你現在的位置                                         最終目標
     ↓                                                 ↓
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Phase 1  │ →  │ Phase 2  │ →  │ Phase 3  │ →  │ Phase 4  │
│ 基本面   │    │ 新聞情緒 │    │ 多因子   │    │ 自動化   │
│ 警報系統 │    │ 分析     │    │ 選股模型 │    │ 每日掃描 │
│          │    │          │    │          │    │          │
│ ✅ 已完成│    │ 待實作   │    │ 待實作   │    │ 待實作   │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
   基礎設施        資料增強        策略核心        系統整合
```

## 為什麼是這個順序？

每一階段都是下一階段的基礎：

- Phase 1（基本面警報）提供了「掃描」的框架和門檻邏輯 → Phase 4 需要
- Phase 2（情緒分析）讓新聞從「文字」變成「數字信號」→ Phase 3 需要
- Phase 3（多因子模型）組合所有信號 → Phase 4 用它產出推薦
- Phase 4（自動化）把前面三個串起來，每天自動跑

---

## Phase 1：基本面警報系統 ✅ 已完成

**檔案：** `core/fundamental_alerts.py`

**做了什麼：**
在原有的 AlertManager（價格、漲跌幅、回撤警報）上，新增了基本面觸發條件。

**支援的警報類型：**

| 警報 | 觸發條件 | 嚴重度 |
|------|---------|--------|
| 月營收 YoY 衰退 | 台股 YoY < -10% | warning / critical |
| 月營收 YoY 暴增 | 台股 YoY > +30% | info |
| 連續 N 月衰退 | 連續 3 個月 YoY 為負 | critical |
| VIX 飆升 | VIX > 25 | warning |
| VIX 極端 | VIX > 35 | critical |
| 殖利率曲線倒掛 | 10Y-2Y < 0 | warning |
| EPS 優於預期 | surprise > +5% | info |
| EPS 低於預期 | surprise < -5% | warning / critical |
| P/E 偏高 | > 40 | warning |
| P/E 偏低 | < 8 | info（注意價值陷阱）|

**使用方式：**
```python
from core.fundamental_alerts import FundamentalAlertChecker

checker = FundamentalAlertChecker()

# 掃描你的持股
alerts = checker.scan_watchlist(['2330', '2454', 'AAPL', 'NVDA'])

# 看報告
from core.fundamental_alerts import generate_scan_report
print(generate_scan_report(alerts))
```

**門檻可自訂：**
```python
from core.fundamental_alerts import AlertThresholds

# 調整門檻
my_thresholds = AlertThresholds(
    revenue_yoy_decline_pct=-15.0,  # 比預設 -10% 更寬鬆
    vix_warning=20.0,               # 比預設 25 更敏感
)
checker = FundamentalAlertChecker(thresholds=my_thresholds)
```

---

## Phase 2：新聞情緒分析（待實作）

**目標：** 讓新聞從「純文字」變成可量化的「情緒分數」。

**實作方案（由簡到難）：**

### 方案 A：關鍵字規則（最簡單，建議先做）

```python
# core/sentiment.py 草案

POSITIVE_KEYWORDS = [
    '獲利', '成長', '突破', '新高', '上調', '超預期',
    'beat', 'upgrade', 'growth', 'record', 'bullish',
]
NEGATIVE_KEYWORDS = [
    '衰退', '下修', '裁員', '虧損', '低於預期', '調降',
    'miss', 'downgrade', 'decline', 'layoff', 'bearish',
]

def simple_sentiment(text: str) -> float:
    """回傳 -1.0 ~ +1.0 的情緒分數。"""
    text_lower = text.lower()
    pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in text_lower)
    neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text_lower)
    total = pos + neg
    if total == 0:
        return 0.0
    return (pos - neg) / total
```

### 方案 B：用 Hugging Face 預訓練模型

```python
# 需要安裝：pip install transformers torch
from transformers import pipeline

classifier = pipeline("sentiment-analysis",
                      model="ProsusAI/finbert")

def finbert_sentiment(text: str) -> dict:
    result = classifier(text[:512])  # FinBERT 限制 512 tokens
    return result[0]  # {'label': 'positive', 'score': 0.95}
```

### 方案 C：用 Claude API（最強但有成本）

```python
import anthropic

client = anthropic.Anthropic()

def llm_sentiment(headline: str, symbol: str) -> dict:
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": f"分析這則新聞對 {symbol} 股價的影響：\n{headline}\n"
                       f"回傳 JSON: {{\"sentiment\": \"positive/negative/neutral\", "
                       f"\"score\": 0.0~1.0, \"reason\": \"一句話\"}}"
        }]
    )
    return json.loads(response.content[0].text)
```

**建議路徑：** 先用方案 A 上線，之後換 B 或 C 提升準確度。

**整合進 Context Engine：**
```python
# 在 context_engine.py 的 _get_news_events() 中
# 把 impact='neutral' 替換成情緒分析的結果
sentiment = simple_sentiment(news['headline'] + ' ' + news['summary'])
impact = 'positive' if sentiment > 0.3 else ('negative' if sentiment < -0.3 else 'neutral')
```

---

## Phase 3：多因子選股模型（待實作）

**目標：** 把技術面 + 基本面 + 情緒面 合成一個「綜合評分」。

**設計草案：**

```python
# core/multi_factor.py 草案

@dataclass
class FactorScore:
    """單一因子的評分。"""
    name: str
    value: float      # 原始值
    score: float       # 標準化後 0~100 分
    weight: float      # 權重

class MultiFactorModel:
    """
    多因子評分模型。

    因子分三大類：
    1. 技術面 (40%): RSI, MACD 方向, 均線排列, 布林位置
    2. 基本面 (40%): P/E 排名, 營收成長, ROE, D/E
    3. 情緒面 (20%): 新聞情緒分數, VIX 水位
    """

    def __init__(self):
        self.weights = {
            'technical': 0.40,
            'fundamental': 0.40,
            'sentiment': 0.20,
        }

    def score_stock(self, symbol: str) -> Dict:
        """對一檔股票評分。"""
        tech_score = self._technical_score(symbol)
        fund_score = self._fundamental_score(symbol)
        sent_score = self._sentiment_score(symbol)

        total = (
            tech_score * self.weights['technical'] +
            fund_score * self.weights['fundamental'] +
            sent_score * self.weights['sentiment']
        )

        return {
            'symbol': symbol,
            'total_score': total,
            'technical': tech_score,
            'fundamental': fund_score,
            'sentiment': sent_score,
            'rating': self._score_to_rating(total),
        }

    def rank_watchlist(self, symbols: List[str]) -> pd.DataFrame:
        """把觀察清單的所有股票排名。"""
        scores = [self.score_stock(s) for s in symbols]
        df = pd.DataFrame(scores)
        return df.sort_values('total_score', ascending=False)
```

**CQF 學習連結：** 這就是量化金融裡的「因子投資」(Factor Investing)。
你在 CQF Module 4 會學到更正式的因子模型（Fama-French 三因子/五因子），
但核心概念一樣：把多個信號標準化 → 加權 → 排名。

---

## Phase 4：自動化每日掃描（待實作）

**目標：** 每天早上自動跑一次，產出報告，推送通知。

**流程：**

```
每日 08:00（台股開盤前）
    │
    ▼
 1. 更新觀察清單股價
    │
    ▼
 2. 基本面掃描（FundamentalAlertChecker）
    │
    ▼
 3. 新聞情緒掃描（SentimentAnalyzer）
    │
    ▼
 4. 多因子評分排名（MultiFactorModel）
    │
    ▼
 5. 產出「每日晨報」
    │
    ├─→ 存成 HTML/MD 檔案
    ├─→ 推送到 Notion（你有 Notion MCP）
    └─→ LINE Notify 通知重要警報
```

**scripts/daily_scan.py 草案：**

```python
#!/usr/bin/env python3
"""每日自動掃描腳本。"""
import json
from pathlib import Path
from core.fundamental_alerts import FundamentalAlertChecker, generate_scan_report

# 讀取觀察清單
with open('config/watchlists.json') as f:
    watchlists = json.load(f)

symbols = []
for group in watchlists.values():
    if isinstance(group, dict) and 'symbols' in group:
        symbols.extend(group['symbols'].keys())

# 執行掃描
checker = FundamentalAlertChecker()
result = checker.scan_watchlist(list(set(symbols)))

# 產出報告
report = generate_scan_report(result)
print(report)

# 存檔
Path('reports').mkdir(exist_ok=True)
with open(f'reports/daily_{date.today()}.txt', 'w') as f:
    f.write(report)
```

**排程方式：**
- macOS/Linux: crontab (`0 8 * * 1-5 python daily_scan.py`)
- 或用 Cowork 的 schedule 功能

---

## 現有系統完整能力清單

| 模組 | 狀態 | 說明 |
|------|------|------|
| DataManager | ✅ 穩定 | 台美股價格 OHLCV |
| TechnicalIndicators | ✅ 穩定 | MA, RSI, MACD, 布林 |
| BacktestEngine | ✅ 穩定 | 均值回歸、動量、RSI 策略 |
| RiskAnalysis | ✅ 穩定 | VaR, CVaR, Sharpe, MDD |
| AlertManager | ✅ 穩定 | 價格、漲跌幅、回撤、信號 |
| PortfolioOptimizer | ✅ 穩定 | 權重最佳化 |
| WalkForward | ✅ 穩定 | 前向驗證 |
| FinancialReports | ✅ 新增 | 三表 + 月營收 + 比率 |
| NewsManager | ✅ 新增 | 新聞 + 總經 + 財報日程 |
| ContextEngine | ✅ 新增 | 時間軸串聯引擎 |
| **FundamentalAlerts** | ✅ **新增** | 基本面警報系統 |
| SentimentAnalyzer | ⏳ Phase 2 | 新聞情緒分析 |
| MultiFactorModel | ⏳ Phase 3 | 多因子選股 |
| DailyScan | ⏳ Phase 4 | 自動化掃描 + 報告 |

---

## 你的下一步

1. **現在就能做：** 在 Python 裡試跑 `FundamentalAlertChecker().scan_watchlist()`
2. **本週目標：** 實作 Phase 2 的方案 A（關鍵字情緒分析）
3. **本月目標：** 完成 Phase 3 多因子模型的 MVP
4. **最終目標：** Phase 4 每天自動跑，早上看手機就知道今天要注意什麼
