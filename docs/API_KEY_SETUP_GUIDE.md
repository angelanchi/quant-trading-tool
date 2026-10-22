# API Key 設定指南

> 依照「免費 → 進階」的順序，逐步設定資料源。
> 不需要一次全部設定完，先設定 Phase 0 就能跑起來！

---

## Phase 0: 完全免費（不需任何 Key）

這些資料源直接可用，不需要申請任何東西：

| 資料源 | 用途 | 限制 |
|--------|------|------|
| **yfinance** | 美股/台股(.TW)股價、基本財報 | 非官方 API，偶爾會被限速 |
| **Google News RSS** | 中/英文財經新聞搜尋 | 僅有標題和連結，無全文 |

安裝：
```bash
pip install yfinance
```

驗證：
```python
import yfinance as yf
ticker = yf.Ticker("AAPL")
print(ticker.history(period="5d"))          # 股價
print(ticker.quarterly_income_stmt)         # 季度損益表
print(ticker.info.get('trailingPE'))        # PE 比率
```

---

## Phase 1: 免費 API Key

### 1. FinMind（台股財報/月營收）

**用途**: 台股季度財報、月營收、股利、法人買賣超等

**申請步驟**:
1. 前往 https://finmindtrade.com
2. 點右上角「註冊」，填寫 Email 和密碼
3. 登入後，進入「個人頁面」→「API Token」
4. 複製你的 Token

**免費額度**: 每日 600 次 API 呼叫（一般使用足夠）

**設定**:
```bash
# 在 .env 檔案中加入
FINMIND_API_TOKEN=your_token_here
```

**驗證**:
```python
from FinMind.data import DataLoader
dl = DataLoader()
dl.login_by_token(api_token="your_token")
df = dl.taiwan_stock_daily(stock_id="2330", start_date="2026-01-01")
print(df.head())
```

---

### 2. FRED（美國總經數據）

**用途**: 聯邦基金利率、CPI、PMI、GDP、失業率等

**申請步驟**:
1. 前往 https://fred.stlouisfed.org/docs/api/api_key.html
2. 點「Request API Key」
3. 填寫基本資料（姓名、Email、用途寫 "Personal research"）
4. 收到 Email 後點擊確認連結
5. 在帳戶頁面找到你的 API Key

**免費額度**: 無限制（合理使用）

**設定**:
```bash
# 在 .env 檔案中加入
FRED_API_KEY=your_key_here
```

**驗證**:
```python
import requests
key = "your_key_here"
url = f"https://api.stlouisfed.org/fred/series/observations?series_id=DFF&api_key={key}&file_type=json&limit=5&sort_order=desc"
resp = requests.get(url)
print(resp.json()['observations'][:3])
```

**常用總經代碼**:
| 代碼 | 指標 | 更新頻率 |
|------|------|----------|
| `DFF` | 聯邦基金利率 | 每日 |
| `CPIAUCSL` | 消費者物價指數 (CPI) | 每月 |
| `UNRATE` | 失業率 | 每月 |
| `GDP` | 國內生產毛額 | 每季 |
| `T10YIE` | 10年期通膨預期 | 每日 |
| `VIXCLS` | VIX 恐慌指數 | 每日 |

---

### 3. Finnhub（美股新聞/法說會）

**用途**: 公司新聞、法說會日程、SEC filing、分析師評等

**申請步驟**:
1. 前往 https://finnhub.io
2. 點「Get free API key」
3. 用 Email 註冊
4. 登入後在 Dashboard 找到 API Key

**免費額度**: 60 次/分鐘（一般使用足夠）

**設定**:
```bash
# 在 .env 檔案中加入
FINNHUB_API_KEY=your_key_here
```

**驗證**:
```python
import finnhub
client = finnhub.Client(api_key="your_key_here")
news = client.company_news('AAPL', _from='2026-04-01', to='2026-04-24')
print(f"找到 {len(news)} 則新聞")
for n in news[:3]:
    print(f"  {n['datetime']} - {n['headline']}")
```

---

## .env 檔案完整範例

在 `quant_trading_tool/` 目錄下建立 `.env` 檔案：

```bash
# ===== 資料源 API Keys =====

# Phase 1: 台股財報（FinMind）
FINMIND_API_TOKEN=

# Phase 1: 美國總經數據（FRED）
FRED_API_KEY=

# Phase 1: 美股新聞（Finnhub）
FINNHUB_API_KEY=

# ===== Phase 2: 進階（選填） =====

# Alpha Vantage（更完整的基本面）
# ALPHA_VANTAGE_KEY=

# Anthropic API（LLM 情緒分析 Level 3）
# ANTHROPIC_API_KEY=

# ===== 資料庫（選填，PostgreSQL） =====
# DATABASE_URL=postgresql://user:password@localhost:5432/quant_db
```

**重要**: 確保 `.env` 已在 `.gitignore` 中，不要提交到 Git！

---

## 驗證所有設定

設定完 Key 後，執行驗證腳本：

```bash
cd quant_trading_tool
python scripts/verify_context_engine.py --symbol AAPL   # 美股
python scripts/verify_context_engine.py --symbol 2330   # 台股
```

如果看到大部分 ✅，就代表設定成功了！
