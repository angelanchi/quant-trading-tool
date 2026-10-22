# SDD: 財報 × 時事串聯整合設計

> Author: AIdevteam_An9
> Version: 1.0
> Date: 2026-04-24
> Status: Draft

---

## 1. 目標

在現有 `context_engine.py` 基礎上，實現「財報資料 × 時事背景」的端到端串聯，
讓使用者在 Streamlit 儀表板上能一眼看出：

- 這段漲跌背後發生了什麼事？
- 財報公布前後，市場如何反應？
- 總經環境（利率、CPI）對個股有什麼影響？

## 2. 現有架構盤點

### 已完成的模組

| 模組 | 檔案 | 功能 | 狀態 |
|------|------|------|------|
| 股價資料 | `core/data_fetcher.py` | FinMind(台) + yfinance(美) | ✅ 可用 |
| 財報擷取 | `core/financial_reports.py` | 損益表/資產負債表/現金流 | ✅ 可用 |
| 新聞擷取 | `core/news_fetcher.py` | Finnhub + Google News RSS | ✅ 可用 |
| 情緒分析 | `core/sentiment.py` | 關鍵字 / FinBERT / LLM | ✅ 可用 |
| 串聯引擎 | `core/context_engine.py` | ContextEvent + StockTimeline | ✅ 架構完成 |
| Dashboard | `pages/0_每日總覽_Daily_Overview.py` | 每日掃描報告 | ✅ 可用 |

### 尚未完成 / 需加強的部分

| 缺口 | 說明 | 優先級 |
|------|------|--------|
| API Key 未設定 | FinMind/Finnhub/FRED 都需要 Key | P0 |
| 免費替代方案 | yfinance + Google RSS 可先撐住 | P0 |
| 財報 × 股價相關性分析 | 財報公布日前後的報酬率計算 | P1 |
| 時間軸視覺化 | Streamlit 上的互動式時間軸圖表 | P1 |
| 總經事件日曆 | FOMC/CPI/PMI 固定日程整合 | P2 |
| 因果推論標記 | 標記「這則新聞可能解釋了這段漲跌」 | P3 |

## 3. 資料源策略（免費優先）

### Phase 0: 完全免費（立刻可用）

```
股價資料：yfinance（美股免費、台股透過 .TW 後綴）
基本財報：yfinance（季度損益表、資產負債表、現金流）
新聞：    Google News RSS（關鍵字搜尋，無需 Key）
總經：    yfinance 內建的市場指數（^TNX 10年期殖利率等）
```

### Phase 1: 免費 API Key

| 來源 | 用途 | 免費額度 | 申請連結 |
|------|------|----------|----------|
| FinMind | 台股財報/月營收 | 每日 600 次 | https://finmindtrade.com |
| Finnhub | 美股新聞/法說會 | 60 req/min | https://finnhub.io |
| FRED | 美國總經數據 | 無限制 | https://fred.stlouisfed.org/docs/api/api_key.html |

### Phase 2: 進階資料

| 來源 | 用途 | 費用 |
|------|------|------|
| Alpha Vantage | 更完整的基本面 | 免費 tier 可用 |
| 公開資訊觀測站 | 台股重大訊息/法說會 | 免費，需爬蟲 |
| Anthropic API | LLM 情緒分析 (Level 3) | 按用量計費 |

## 4. 系統設計

### 4.1 資料流

```
[資料採集層]
  yfinance ─────→ 股價 DataFrame + 基本財報 dict
  Google RSS ───→ 新聞列表 [{title, date, url}]
  (FRED API) ──→ 總經指標 DataFrame（有 Key 時啟用）

      ↓ 統一轉換為 ContextEvent

[串聯引擎層] context_engine.py
  build_timeline(symbol, days_back=90)
    ├── _detect_price_events()      ← 價格/量異常偵測
    ├── _get_financial_events()     ← 財報事件
    ├── _get_news_events()          ← 新聞（含情緒分析）
    └── _get_macro_events()         ← 總經事件
      ↓
  StockTimeline（統一時間軸物件）

      ↓

[分析層] 新增模組
  EarningsReactionAnalyzer         ← 財報日前後報酬率分析
  EventCorrelator                  ← 事件 × 股價相關性
  MacroImpactScorer                ← 總經對個股影響評分

      ↓

[展示層] Streamlit Pages
  頁面 0: 每日總覽 + 背景卡片
  頁面 3: 個股分析 + 時間軸圖表（增強）
  新頁面: 財報 × 時事串聯專頁
```

### 4.2 核心新增：EarningsReactionAnalyzer

```python
# 設計概念（將實作於 core/earnings_reaction.py）

class EarningsReactionAnalyzer:
    """
    分析財報公布日前後的市場反應。

    計算指標：
    - 財報日前 5 天的累積報酬（市場預期）
    - 財報日後 1/3/5 天的報酬（市場反應）
    - 與同期大盤（SPY/TAIEX）的超額報酬
    - 營收 YoY 成長率 vs 股價反應的對照
    """

    def analyze(self, symbol, earnings_dates, price_df):
        results = []
        for ed in earnings_dates:
            result = {
                'earnings_date': ed,
                'pre_5d_return': self._calc_return(price_df, ed, -5, 0),
                'post_1d_return': self._calc_return(price_df, ed, 0, 1),
                'post_3d_return': self._calc_return(price_df, ed, 0, 3),
                'post_5d_return': self._calc_return(price_df, ed, 0, 5),
                'nearby_events': [],  # 同期有什麼新聞/總經事件
            }
            results.append(result)
        return results
```

### 4.3 核心新增：Streamlit 時間軸視覺化

```python
# 設計概念（將整合於個股分析頁面）

def render_timeline_chart(timeline: StockTimeline):
    """
    用 Plotly 畫互動式時間軸：
    - 主軸：股價折線圖
    - 標記：財報日（藍色）、新聞（橘色）、總經（綠色）
    - 點擊事件標記可展開細節
    - 底部：情緒分數折線（每日加總）
    """
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.7, 0.3])

    # 上半：股價 + 事件標記
    fig.add_trace(go.Scatter(x=dates, y=prices, name='股價'), row=1, col=1)

    # 事件標記（不同顏色 + 形狀）
    for event in timeline.events:
        fig.add_annotation(...)

    # 下半：情緒分數
    fig.add_trace(go.Bar(x=dates, y=sentiments, name='情緒'), row=2, col=1)

    return fig
```

## 5. 實作排程（MVP 迭代）

### Sprint 1（本週）：驗證 + 免費資料跑通

- [x] 盤點現有架構
- [ ] 用 yfinance 驗證 context_engine 端到端
- [ ] 確認 Google News RSS 抓得到中/英文新聞
- [ ] 在 Streamlit 上看到基本時間軸

### Sprint 2（下週）：財報反應分析

- [ ] 實作 EarningsReactionAnalyzer
- [ ] 財報日前後報酬率計算
- [ ] 申請 FinMind API Key（台股月營收）
- [ ] 申請 FRED API Key（總經數據）

### Sprint 3（第三週）：視覺化 + 串聯

- [ ] Plotly 互動式時間軸圖表
- [ ] 事件 × 股價相關性標記
- [ ] 背景卡片增強（加入情緒分數）
- [ ] 新增「財報 × 時事」專頁

### Sprint 4（第四週）：進階功能

- [ ] 總經事件日曆（FOMC/CPI 固定日程）
- [ ] 多股票比較時間軸
- [ ] 申請 Finnhub Key（法說會/分析師評等）
- [ ] 警報系統：財報公布前 3 天提醒

## 6. 檔案變更清單

| 操作 | 檔案 | 說明 |
|------|------|------|
| 新增 | `core/earnings_reaction.py` | 財報反應分析器 |
| 新增 | `core/free_data_sources.py` | 免費資料源封裝（yfinance + RSS） |
| 新增 | `pages/11_財報串聯_Context.py` | 新 Streamlit 頁面 |
| 修改 | `core/context_engine.py` | 整合免費資料源 fallback |
| 修改 | `pages/3_個股分析_Stock_Analysis.py` | 加入時間軸圖表 |
| 新增 | `scripts/verify_context_engine.py` | 端到端驗證腳本 |
| 新增 | `docs/API_KEY_SETUP_GUIDE.md` | API Key 設定指南 |
