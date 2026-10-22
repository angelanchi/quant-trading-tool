# 財報 × 時事 × 股價 整合設計指南

## 架構總覽

```
┌─────────────────────────────────────────────────────┐
│                   Streamlit Dashboard                │
│           pages/8_Fundamental_News.py                │
│                                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │ 背景卡片 │ │  時間軸  │ │ 財報分析 │ │ 總經板 │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └───┬────┘ │
└───────┼────────────┼────────────┼────────────┼──────┘
        │            │            │            │
        └────────────┴─────┬──────┴────────────┘
                           │
              ┌────────────▼────────────┐
              │    ContextEngine        │
              │  core/context_engine.py │
              │                         │
              │  整合所有資料源          │
              │  產出 StockTimeline     │
              └───┬─────┬─────┬────────┘
                  │     │     │
        ┌─────────┘     │     └──────────┐
        ▼               ▼                ▼
┌──────────────┐ ┌─────────────┐ ┌──────────────┐
│ DataManager  │ │ Financial   │ │ NewsManager  │
│ (已有的)     │ │ Report Mgr  │ │ (新增)       │
│              │ │ (新增)      │ │              │
│ • 股價 OHLCV │ │ • 損益表    │ │ • 公司新聞   │
│ • 即時報價   │ │ • 資產負債表│ │ • 總經數據   │
│ • 三大法人   │ │ • 現金流量表│ │ • 財報日程   │
│ • 融資券     │ │ • 月營收    │ │ • RSS搜尋    │
│              │ │ • 關鍵比率  │ │              │
└──────────────┘ └─────────────┘ └──────────────┘
   FinMind         FinMind          Finnhub
   yfinance        yfinance         Google News
   Finnhub                          FRED API
```

## 新增的三個核心模組

### 1. `core/financial_reports.py` — 財報資料模組

**負責什麼：** 抓取台股與美股的財務報表。

**類別：**

| 類別 | 說明 |
|------|------|
| `TaiwanFinancialFetcher` | 台股財報（FinMind API） |
| `USFinancialFetcher` | 美股財報（yfinance） |
| `FinancialReportManager` | 統一管理器，自動判斷台/美股 |

**可以取得的資料：**

- 損益表（Income Statement）
- 資產負債表（Balance Sheet）
- 現金流量表（Cash Flow Statement）
- 月營收（台股特有，每月 10 日公布）
- 關鍵比率（P/E, ROE, Debt/Equity 等）
- 股利資料
- 分析師目標價（美股）

**使用範例：**
```python
from core.financial_reports import FinancialReportManager

manager = FinancialReportManager()

# 自動判斷台股/美股
income = manager.get_income_statement('2330')    # 台積電
income = manager.get_income_statement('AAPL')    # Apple

# 台股月營收
rev = manager.get_monthly_revenue('2330')

# 完整摘要（一次抓全部）
summary = manager.get_financial_summary('AAPL')
```

---

### 2. `core/news_fetcher.py` — 新聞與總經資料模組

**負責什麼：** 抓取財經新聞、總經數據、財報日程。

**子模組：**

| 類別 | 說明 | 資料來源 |
|------|------|---------|
| `NewsFetcher` | 公司新聞搜尋 | Finnhub, Google News RSS |
| `MacroDataFetcher` | 總經指標 | FRED API |
| `EarningsCalendarFetcher` | 財報日程 | Finnhub, yfinance |
| `NewsManager` | 統一管理器 | 以上全部 |

**總經指標對照表（FRED）：**

| 別名 | FRED 代碼 | 說明 |
|------|-----------|------|
| CPI | CPIAUCSL | 消費者物價指數 |
| FED_RATE | FEDFUNDS | 聯邦基金利率 |
| UNEMPLOYMENT | UNRATE | 失業率 |
| US_10Y | DGS10 | 10年期公債殖利率 |
| VIX | VIXCLS | 恐慌指數 |
| YIELD_CURVE | T10Y2Y | 殖利率曲線 |
| GDP | GDP | 國內生產毛額 |
| M2 | M2SL | M2 貨幣供給 |
| CONSUMER_SENTIMENT | UMCSENT | 消費者信心指數 |

**使用範例：**
```python
from core.news_fetcher import NewsManager

manager = NewsManager()

# 公司新聞（台股自動用 Google News）
news = manager.get_company_news('AAPL')
news = manager.get_company_news('2330')

# 總經指標
cpi = manager.get_macro_indicator('CPI')
fed = manager.get_macro_indicator('FED_RATE')

# 關鍵字搜尋新聞
results = manager.search_news('半導體 AI', language='zh-TW')

# 財報日程
calendar = manager.get_upcoming_earnings()
```

---

### 3. `core/context_engine.py` — 背景串聯引擎

**負責什麼：** 把股價 + 財報 + 新聞 + 總經 整合成「時間軸」。

**核心概念：**

- **ContextEvent**: 時間軸上的一個事件（任何類型）
- **StockTimeline**: 某檔股票的完整事件時間軸
- **ContextEngine**: 整合引擎，自動呼叫所有 Manager

**事件類型 (EventType)：**

| 類型 | 說明 | 觸發條件 |
|------|------|---------|
| PRICE_SPIKE | 單日大漲/大跌 | 日報酬 > 3% |
| VOLUME_SPIKE | 成交量異常放大 | > 20日均量的 2 倍 |
| EARNINGS_RELEASE | 財報公布 | EPS surprise |
| MONTHLY_REVENUE | 台股月營收 | 每月 10 日 |
| NEWS | 重要新聞 | 關鍵字比對 |
| MACRO_EVENT | 總經事件 | CPI/利率/VIX 變動 |
| DIVIDEND | 除權息 | — |

**使用範例：**
```python
from core.context_engine import ContextEngine

engine = ContextEngine()

# 建構完整時間軸
timeline = engine.build_timeline('AAPL', days_back=90)
timeline.print_summary()

# 只看重要事件
important = timeline.filter_by_importance(min_importance=3)

# 背景卡片（精簡版）
card = engine.get_context_card('2330')

# 財報日股價反應分析
reaction = engine.analyze_earnings_reaction('AAPL')
```

---

## API Keys 設定

在 `.env` 檔案中加入：

```bash
# 已有的
FINMIND_API_TOKEN=your_token      # 台股資料（必要）
FINNHUB_API_KEY=your_key          # 美股即時+新聞（建議）

# 新增的
FRED_API_KEY=your_key             # 總經數據（建議，免費申請）
```

**免費申請連結：**
- FinMind: https://finmindtrade.com/
- Finnhub: https://finnhub.io/ （免費版 60 req/min）
- FRED: https://fred.stlouisfed.org/docs/api/api_key.html

**不需要 API key 也能用的功能：**
- Google News RSS 新聞搜尋
- yfinance 美股財報（有速率限制）
- pandas_datareader FRED 資料（需安裝套件）

---

## 需要安裝的額外套件

```bash
pip install pandas-datareader    # FRED 總經數據（不需 API key 的方法）
```

其他套件（FinMind, yfinance, finnhub-python）你的系統已經有了。

---

## Streamlit 頁面使用

啟動後多了一個新頁面：**8. 基本面與時事 (Fundamental & News)**

四個 Tab：

1. **背景卡片** — 一眼看到股票的關鍵比率、最近新聞、總經快照
2. **時間軸** — 所有事件按時間排列，可疊合股價走勢圖
3. **財報分析** — 三表數據、月營收趨勢圖
4. **總經儀表板** — CPI、利率、VIX 等指標追蹤 + 新聞搜尋

---

## 設計思路：為什麼這樣架構？

**問題：** 看盤的時候，股價突然漲跌，但不知道為什麼。

**解法：** 把所有可能的「原因」（財報、新聞、總經變化）都放到同一條時間軸上，
和股價走勢對照，就能快速看出因果關係。

**三層架構：**

```
Layer 1: Fetchers（資料擷取）
  → 各自負責從不同來源抓資料
  → 統一輸出格式（DataFrame 或 Dict）

Layer 2: Context Engine（串聯引擎）
  → 把不同來源的資料轉成統一的 ContextEvent
  → 組合成 StockTimeline
  → 自動偵測價格/量異常

Layer 3: Dashboard（呈現層）
  → Streamlit 頁面
  → 互動式篩選、圖表
  → 匯出功能
```

這樣的好處是：每一層都可以獨立使用和測試。
你可以只用 `FinancialReportManager` 抓財報，
也可以用 `ContextEngine` 一次整合所有資料。
