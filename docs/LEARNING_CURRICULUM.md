# CQF 量化交易 13 週完整學習課程

> 每天 30 分鐘，從零開始掌握量化交易核心知識

---

## 課程總覽

| 階段 | 週次 | 主題 | 核心技能 |
|------|------|------|---------|
| 基礎 | 1-2 | 環境與數據 | 工具操作、數據獲取 |
| 基礎 | 3-4 | 回測入門 | 策略執行、績效解讀 |
| 進階 | 5-6 | 投資組合 | 優化方法、權重配置 |
| 進階 | 7-8 | 風險管理 | VaR、CVaR、回撤 |
| 進階 | 9-10 | 統計套利 | 協整、配對交易 |
| 進階 | 11 | 動量策略 | 趨勢跟蹤、突破 |
| 進階 | 12 | 穩健測試 | Walk-Forward |
| 實戰 | 13+ | 策略開發 | 自訂策略、實盤準備 |

---

# 第一週：環境設置與工具熟悉

## 學習目標
- 完成開發環境設置
- 熟悉網頁介面操作
- 執行第一個互動教學

## Day 1：環境安裝

### 任務
```bash
# 確認 Python 版本 (需要 3.9+)
python --version

# 進入專案目錄
cd quant_trading_tool

# 安裝所有依賴
pip install -r requirements.txt
```

### 驗證
- [ ] Python 版本 >= 3.9
- [ ] pip install 無錯誤完成

### 今日知識點
**什麼是量化交易？**
量化交易是使用數學模型和電腦程式來識別交易機會並執行交易的方法。核心流程：
1. 數據獲取 -> 2. 策略開發 -> 3. 回測驗證 -> 4. 風險管理 -> 5. 實盤執行

---

## Day 2：啟動網頁介面

### 任務
```bash
# 啟動 Streamlit 應用
streamlit run app.py
```

瀏覽器開啟 `http://localhost:8501`

### 探索內容
1. **首頁**：閱讀功能介紹
2. **Dashboard**：查看系統狀態
3. **Data Management**：瀏覽數據管理功能
4. **Backtesting**：了解回測介面
5. **Portfolio**：查看優化選項
6. **Risk Analysis**：了解風險指標

### 驗證
- [ ] 成功啟動網頁介面
- [ ] 能說出每個頁面的主要功能

### 今日知識點
**OHLCV 數據結構**
- **O**pen：開盤價
- **H**igh：最高價
- **L**ow：最低價
- **C**lose：收盤價
- **V**olume：成交量

這是金融數據最基本的格式，所有技術分析都基於此。

---

## Day 3：系統健康檢查

### 任務
```bash
# Windows
run.bat health

# 或直接執行
python scripts/health_check.py
```

### 理解輸出
檢查項目：
- Python 環境
- 核心模組載入
- 資料庫連接（可選）
- API 金鑰配置（可選）

### 驗證
- [ ] 健康檢查執行成功
- [ ] 理解哪些是必要項目，哪些是可選項目

### 今日知識點
**為什麼需要資料庫？**
- 緩存歷史數據，避免重複下載
- 存儲回測結果，方便比較
- 記錄交易日誌

初學階段可以不使用資料庫，系統會使用記憶體或檔案緩存。

---

## Day 4：互動教學 - 數據獲取

### 任務
```bash
# 啟動 Jupyter Notebook
jupyter notebook notebooks/quickstart.ipynb
```

### 學習內容
完成 **第 1 節：數據獲取**
- 使用 DataManager 獲取股票數據
- 繪製 K 線圖
- 觀察數據結構

### 練習
修改代碼，嘗試獲取不同股票：
- 台股：2330（台積電）、2317（鴻海）
- 美股：AAPL、MSFT、GOOGL

### 驗證
- [ ] 成功執行數據獲取代碼
- [ ] 能看懂 K 線圖

### 今日知識點
**收益率計算**
```python
# 簡單收益率
simple_return = (P_t - P_{t-1}) / P_{t-1}

# 對數收益率（更常用）
log_return = ln(P_t / P_{t-1})
```

對數收益率的優點：可加性（多期收益率可以直接相加）

---

## Day 5：互動教學 - 回測基礎

### 任務
繼續 `quickstart.ipynb` **第 2 節：回測基礎**

### 學習內容
- 什麼是回測
- 均值回歸策略概念
- 執行第一個回測
- 解讀權益曲線

### 今日知識點
**均值回歸 (Mean Reversion)**

核心假設：價格會回歸到其歷史平均值

策略邏輯：
- 當價格低於均值太多 -> 買入
- 當價格高於均值太多 -> 賣出
- 當價格回到均值附近 -> 平倉

Z-score 計算：
```
Z = (當前價格 - 移動平均) / 移動標準差
```

---

## Day 6：互動教學 - 優化與風險

### 任務
完成 `quickstart.ipynb` **第 3-4 節**
- 第 3 節：投資組合優化
- 第 4 節：風險分析

### 學習內容
- 為什麼要分散投資
- 夏普比率的意義
- VaR 的概念

### 今日知識點
**夏普比率 (Sharpe Ratio)**
```
Sharpe = (投資組合收益 - 無風險利率) / 投資組合波動率
```

解讀：
- Sharpe > 1：良好
- Sharpe > 2：優秀
- Sharpe < 0：不如存銀行

---

## Day 7：週複習與筆記

### 任務
1. 完成 quickstart.ipynb 最後一節
2. 整理本週學習筆記
3. 列出不理解的概念

### 複習清單
- [ ] 能啟動網頁介面
- [ ] 理解 OHLCV 數據
- [ ] 能執行 Jupyter Notebook
- [ ] 理解收益率計算
- [ ] 知道什麼是均值回歸
- [ ] 聽過夏普比率

---

# 第二週：基礎數據操作

## 學習目標
- 深入理解數據處理
- 計算基礎統計指標
- 使用網頁介面操作

## Day 1：基礎範例 - 數據獲取

### 任務
```bash
python examples/basic_usage.py
```

### 學習內容
觀察 Example 1 和 Example 2 的輸出：
- 數據獲取流程
- 基本價格統計
- 收益率分布

### 今日知識點
**描述性統計**
- **Mean（均值）**：平均收益
- **Std（標準差）**：波動程度
- **Skewness（偏度）**：分布是否對稱
- **Kurtosis（峰度）**：尾部厚度

---

## Day 2：基礎範例 - 相關性分析

### 任務
繼續觀察 `basic_usage.py` 的 Example 3-4

### 學習內容
- 資產相關性分析
- 相關性矩陣解讀
- 為什麼相關性重要

### 今日知識點
**相關係數**
- 範圍：-1 到 +1
- +1：完全正相關（同漲同跌）
- 0：無相關
- -1：完全負相關（一漲一跌）

投資組合分散化的核心：選擇低相關性的資產

---

## Day 3：基礎範例 - 技術指標

### 任務
觀察 Example 5 的輸出

### 學習內容
- 移動平均線（SMA）
- 信號生成邏輯
- 交易信號可視化

### 今日知識點
**移動平均線 (Moving Average)**
```python
# 簡單移動平均 SMA
SMA_20 = 過去 20 天收盤價的平均值

# 指數移動平均 EMA（近期權重較高）
EMA_20 = 加權平均，最近的數據權重更大
```

交叉信號：
- 短期 SMA 向上穿越長期 SMA -> 買入信號
- 短期 SMA 向下穿越長期 SMA -> 賣出信號

---

## Day 4：網頁介面 - 數據管理

### 任務
1. 啟動網頁介面：`streamlit run app.py`
2. 進入 **Data Management** 頁面
3. 嘗試搜索和下載股票數據

### 練習
1. 搜索 "AAPL"
2. 下載 2023 年數據
3. 查看 K 線圖
4. 觀察成交量變化

### 驗證
- [ ] 能通過網頁介面下載數據
- [ ] 能看懂 K 線圖上的買賣信號

---

## Day 5：修改代碼練習

### 任務
複製並修改 `basic_usage.py`

### 練習
```python
# 創建 my_analysis.py
# 修改以下內容：
symbols = ['TSLA', 'NVDA', 'AMD']  # 改成你感興趣的股票
start_date = '2023-01-01'
end_date = '2023-12-31'
```

執行並觀察輸出差異

### 驗證
- [ ] 能修改股票代碼
- [ ] 能修改日期範圍
- [ ] 理解輸出結果

---

## Day 6：理論閱讀 - 績效指標

### 任務
閱讀計劃文檔中的 **1.4.1 績效指標** 章節

### 學習內容
| 指標 | 定義 | 公式 |
|------|------|------|
| 總收益率 | 期末 vs 期初變化 | (V_end - V_start) / V_start |
| CAGR | 年化複合成長率 | (V_end/V_start)^(1/n) - 1 |
| 勝率 | 獲利交易佔比 | 獲利數 / 總交易數 |
| 盈虧比 | 平均獲利/虧損 | avg_win / avg_loss |

### 今日知識點
**為什麼需要年化？**

如果策略 A 在 6 個月賺了 10%，策略 B 在 2 年賺了 30%，哪個更好？

年化後：
- 策略 A：約 21% 年化
- 策略 B：約 14% 年化

年化讓不同時間週期的策略可以公平比較。

---

## Day 7：週複習與整理

### 任務
1. 複習本週所有範例
2. 整理學習筆記
3. 完成驗證清單

### 第二週驗證清單
- [ ] 理解描述性統計（均值、標準差、偏度、峰度）
- [ ] 理解相關係數的意義
- [ ] 能計算移動平均線
- [ ] 能使用網頁介面操作
- [ ] 能修改範例代碼

---

# 第三週：回測基礎（上）

## 學習目標
- 深入理解回測流程
- 學習均值回歸策略
- 解讀回測績效報告

## Day 1：回測概念

### 任務
```bash
python examples/backtest_example.py
```

### 觀察 Example 1 輸出
- 策略參數設定
- 績效指標結果
- 權益曲線

### 今日知識點
**什麼是回測？**

回測 = 用歷史數據模擬策略執行

流程：
1. 定義策略規則
2. 獲取歷史數據
3. 模擬每天的交易決策
4. 計算績效指標
5. 分析結果

注意：過去表現不代表未來結果！

---

## Day 2：均值回歸策略

### 任務
詳細閱讀 backtest_example.py 中的均值回歸策略

### 學習內容
```python
# 策略參數
lookback = 20      # 回望期間：計算均值和標準差的天數
entry_zscore = 2.0 # 進場門檻：Z-score 達到 2 時進場
exit_zscore = 0.5  # 出場門檻：Z-score 回到 0.5 時出場
```

### 今日知識點
**Z-score 交易信號**

```
Z-score = (當前價格 - 20日均價) / 20日標準差

交易規則：
- Z < -2.0：價格異常低，買入
- Z > +2.0：價格異常高，賣出
- |Z| < 0.5：回歸均值，平倉
```

---

## Day 3：MA 交叉策略

### 任務
觀察 Example 2：MA 交叉策略

### 學習內容
```python
# 策略參數
fast_period = 10  # 短期均線
slow_period = 30  # 長期均線
```

### 今日知識點
**黃金交叉與死亡交叉**

- **黃金交叉**：短期均線向上穿越長期均線 -> 買入
- **死亡交叉**：短期均線向下穿越長期均線 -> 賣出

這是最經典的趨勢跟蹤策略之一。

---

## Day 4：參數敏感度

### 任務
觀察 Example 3：參數測試

### 學習內容
- 不同 lookback 值的影響
- 參數選擇的權衡

### 今日知識點
**參數敏感度分析**

如果策略對參數非常敏感（小改動大影響），可能是過擬合的信號。

好的策略應該在一定參數範圍內都表現穩定。

---

## Day 5：策略比較

### 任務
觀察 Example 4：策略比較

### 學習內容
- 如何比較不同策略
- 看哪些指標最重要

### 今日知識點
**策略比較的關鍵指標**

| 優先級 | 指標 | 原因 |
|-------|------|------|
| 1 | Sharpe Ratio | 風險調整後收益 |
| 2 | Max Drawdown | 最大虧損風險 |
| 3 | Win Rate | 心理承受能力 |
| 4 | Total Return | 絕對收益 |

---

## Day 6：網頁回測

### 任務
使用網頁介面執行回測

### 步驟
1. 啟動 `streamlit run app.py`
2. 進入 **Backtesting** 頁面
3. 選擇股票
4. 選擇策略
5. 設定參數
6. 執行回測
7. 分析結果

### 驗證
- [ ] 能通過網頁執行回測
- [ ] 能解讀結果頁面

---

## Day 7：週複習

### 第三週驗證清單
- [ ] 理解回測的目的和流程
- [ ] 理解均值回歸策略邏輯
- [ ] 理解 MA 交叉策略邏輯
- [ ] 能解讀績效報告
- [ ] 能使用網頁執行回測

---

# 第四週：回測基礎（下）

## 學習目標
- 理解回測的陷阱
- 學習滑價和手續費
- 初步認識過擬合

## Day 1：回測陷阱

### 今日知識點
**常見回測陷阱**

1. **前視偏差 (Look-ahead Bias)**
   - 使用了未來才知道的資訊
   - 例：用明天的新聞來決定今天交易

2. **生存者偏差 (Survivorship Bias)**
   - 只測試現存的股票
   - 忽略了已下市的股票

3. **過擬合 (Overfitting)**
   - 策略在歷史數據上表現完美
   - 但在新數據上失效

---

## Day 2：滑價與手續費

### 今日知識點
**交易成本**

```python
# 滑價：預期價格 vs 實際成交價
# 買入時通常成交價較高，賣出時較低
slippage = 0.05%  # 假設 0.05% 滑價

# 手續費
# 台股：0.1425%（券商可能折讓）
# 美股：部分券商免手續費
commission = 0.1%
```

回測時必須考慮這些成本，否則會高估策略收益。

---

## Day 3：CLI 回測

### 任務
使用命令列執行回測

```bash
python cli.py backtest run \
    --strategy mean_reversion \
    --symbols AAPL,MSFT \
    --start 2022-01-01 \
    --end 2023-12-31 \
    --capital 100000
```

### 學習內容
- CLI 的優點：可腳本化、批次處理
- 適合進階使用者

---

## Day 4：回測報告生成

### 任務
```bash
python examples/report_example.py
```

### 學習內容
- HTML 報告生成
- 報告包含的內容
- 如何保存和分享報告

---

## Day 5：多策略比較

### 任務
重新執行 backtest_example.py，專注於策略比較部分

### 練習
記錄以下策略的表現：
| 策略 | Sharpe | Max DD | Win Rate |
|------|--------|--------|----------|
| Mean Reversion | | | |
| MA Crossover | | | |

---

## Day 6-7：理論閱讀與複習

### 閱讀內容
計劃文檔中的 **1.4.2 滑價與手續費** 章節

### 第四週驗證清單
- [ ] 能說出 3 種回測陷阱
- [ ] 理解滑價和手續費的影響
- [ ] 能使用 CLI 執行回測
- [ ] 能生成回測報告

---

# 第五週：投資組合優化（上）

## 學習目標
- 理解投資組合理論
- 學習 Markowitz 優化
- 理解有效邊界

## Day 1：為什麼要優化？

### 任務
```bash
python examples/optimization_example.py
```

### 今日知識點
**分散投資的數學基礎**

如果持有兩個不完全相關的資產：
- 組合風險 < 單一資產風險的加權平均
- 這就是「分散投資降低風險」的數學證明

---

## Day 2：Maximum Sharpe

### 觀察 Example 1 輸出

### 今日知識點
**Maximum Sharpe Ratio 優化**

目標：找到風險調整後收益最高的權重組合

```
最大化 Sharpe = (E[Rp] - Rf) / σp

約束條件：
- 所有權重加總 = 1
- 每個權重 >= 0（不允許做空）
```

---

## Day 3：Minimum Volatility

### 觀察 Example 2 輸出

### 今日知識點
**Minimum Volatility 優化**

目標：找到風險最低的權重組合

適用場景：
- 保守型投資者
- 市場不確定性高時
- 退休金等低風險需求

---

## Day 4：有效邊界

### 觀察 Example 5：效率前沿

### 今日知識點
**有效邊界 (Efficient Frontier)**

```
收益率
  |        * Max Sharpe
  |       /
  |      /
  |     *
  |    /
  |   * Min Volatility
  |  /
  | /
  |/_____________ 波動率
```

邊界上的每個點都是「最佳」的：
- 給定風險下，收益最高
- 給定收益下，風險最低

---

## Day 5：權重解讀

### 練習
觀察不同優化方法產生的權重，回答：
1. 哪個方法最分散？
2. 哪個方法最集中？
3. 為什麼會這樣？

---

## Day 6-7：理論閱讀

### 閱讀內容
計劃文檔 **1.1.1 Markowitz 均值-方差優化**

### 第五週驗證清單
- [ ] 理解為什麼分散投資能降低風險
- [ ] 能解釋 Max Sharpe 的目標
- [ ] 能解釋 Min Volatility 的目標
- [ ] 理解有效邊界的意義

---

# 第六週：投資組合優化（下）

## 學習目標
- 學習 Risk Parity
- 學習 Black-Litterman
- 實際應用優化結果

## Day 1：Risk Parity (HRP)

### 觀察 Example 3 輸出

### 今日知識點
**風險平價 (Risk Parity)**

目標：讓每個資產對組合風險的貢獻相等

優點：
- 不需要估計預期收益（最難估計的參數）
- 結果更穩健

---

## Day 2：Black-Litterman

### 觀察 Example 4 輸出

### 今日知識點
**Black-Litterman 模型**

解決問題：傳統 Markowitz 對預期收益估計太敏感

方法：
1. 從市場得到「隱含」預期收益
2. 加入投資者主觀觀點
3. 用貝葉斯方法結合兩者

```python
# 表達觀點
views = {
    'AAPL': 0.15  # 我認為 AAPL 會漲 15%
}
```

---

## Day 3：方法比較

### 練習
整理四種方法的比較：

| 方法 | 優點 | 缺點 | 適用場景 |
|------|------|------|---------|
| Max Sharpe | 收益最高 | 對輸入敏感 | 積極型 |
| Min Vol | 風險最低 | 收益可能較低 | 保守型 |
| Risk Parity | 穩健 | 不考慮收益 | 長期配置 |
| Black-Litterman | 可加入觀點 | 複雜 | 有明確觀點時 |

---

## Day 4：網頁操作

### 任務
使用 **Portfolio** 頁面執行優化

### 步驟
1. 選擇多支股票
2. 選擇優化方法
3. 執行優化
4. 觀察權重分配

---

## Day 5：離散配置

### 今日知識點
**從權重到實際股數**

優化結果是權重（百分比），但實際交易需要股數。

```python
# 假設
# 總資金 = $100,000
# AAPL 權重 = 40%
# AAPL 股價 = $180

# 計算股數
AAPL_金額 = 100000 * 0.4 = $40,000
AAPL_股數 = 40000 / 180 = 222 股
```

---

## Day 6-7：理論閱讀與複習

### 閱讀內容
計劃文檔 **1.1.2 有效邊界** 和 **1.1.3 Black-Litterman**

### 第六週驗證清單
- [ ] 能解釋 Risk Parity 的優點
- [ ] 理解 Black-Litterman 的用途
- [ ] 能比較四種優化方法
- [ ] 能將權重轉換為股數

---

# 第七週：風險管理（上）

## 學習目標
- 理解 VaR 概念
- 學習三種 VaR 計算方法
- 解讀 VaR 結果

## Day 1：VaR 概念

### 任務
```bash
python examples/risk_analysis_example.py
```

### 今日知識點
**Value at Risk (VaR)**

定義：在給定信賴水準下，投資組合在持有期間可能遭受的最大損失

例如：「95% VaR = -2%」表示
- 有 95% 機率，損失不會超過 2%
- 有 5% 機率，損失會超過 2%

---

## Day 2：歷史模擬法

### 觀察 Example 1 中的歷史 VaR

### 今日知識點
**Historical VaR**

```python
def var_historical(returns, confidence=0.95):
    # 步驟：
    # 1. 收集過去 N 天收益率
    # 2. 排序（從小到大）
    # 3. 找出第 (1-0.95)*N 個位置的值
    return np.percentile(returns, (1 - confidence) * 100)
```

優點：不需要假設分布
缺點：依賴歷史數據，極端事件可能沒發生過

---

## Day 3：參數法 VaR

### 今日知識點
**Parametric VaR**

假設收益率服從常態分布：

```python
VaR = μ - z × σ

# 95% VaR: z = 1.645
# 99% VaR: z = 2.326
```

優點：計算簡單
缺點：常態假設可能不成立

---

## Day 4：蒙地卡羅 VaR

### 今日知識點
**Monte Carlo VaR**

```python
# 步驟：
# 1. 估計收益率分布參數
# 2. 模擬 10,000 次可能的未來收益
# 3. 從模擬結果計算 VaR
```

優點：可處理複雜投資組合（含選擇權）
缺點：計算量大

---

## Day 5：VaR 比較

### 練習
記錄三種方法的結果：

| 方法 | 95% VaR | 99% VaR |
|------|---------|---------|
| Historical | | |
| Parametric | | |
| Monte Carlo | | |

為什麼結果不同？

---

## Day 6-7：理論閱讀

### 閱讀內容
計劃文檔 **1.2.1 VaR**

### 第七週驗證清單
- [ ] 能用白話解釋 VaR 的意義
- [ ] 能說出三種 VaR 計算方法
- [ ] 理解每種方法的優缺點

---

# 第八週：風險管理（下）

## 學習目標
- 理解 CVaR
- 學習回撤分析
- 綜合風險評估

## Day 1：CVaR (Expected Shortfall)

### 觀察 Example 2 中的 CVaR

### 今日知識點
**Conditional VaR**

VaR 告訴你：門檻在哪
CVaR 告訴你：超過門檻後，平均會虧多少

```python
# 如果 VaR(95%) = -3%
# 最差的 5% 情況：-3.5%, -4%, -5%, -7%, -10%
# CVaR = (-3.5 + -4 + -5 + -7 + -10) / 5 = -5.9%
```

CVaR 比 VaR 更保守，更能捕捉尾部風險。

---

## Day 2：Sortino Ratio

### 今日知識點
**Sortino vs Sharpe**

Sharpe：懲罰所有波動（包括上漲）
Sortino：只懲罰下行波動

```python
Sharpe = (收益 - 無風險) / 總波動
Sortino = (收益 - 無風險) / 下行波動
```

Sortino 對只關心虧損風險的投資者更有意義。

---

## Day 3：最大回撤

### 觀察 Example 3：回撤分析

### 今日知識點
**Maximum Drawdown (MDD)**

```python
# 計算步驟
peak = 歷史最高點
drawdown = (當前值 - peak) / peak
MDD = 最大的 drawdown
```

解讀：
- MDD = -20% 表示曾經從高點下跌 20%
- 這是投資者可能面臨的最大虧損（若在高點買入）

---

## Day 4：風險分解

### 觀察 Example 6：風險分解

### 今日知識點
**Portfolio Risk Decomposition**

問題：投資組合的風險來自哪些資產？

```python
# 邊際風險貢獻
# 每個資產對總風險的貢獻度
```

用途：識別風險集中的資產

---

## Day 5：網頁風險分析

### 任務
使用 **Risk Analysis** 頁面

### 觀察
- VaR/CVaR 數值
- 回撤圖
- 收益分布圖

---

## Day 6-7：理論與複習

### 閱讀內容
計劃文檔 **1.2.2 CVaR** 和 **1.2.5 最大回撤**

### 第八週驗證清單
- [ ] 能解釋 CVaR 與 VaR 的差異
- [ ] 理解 Sortino Ratio 的意義
- [ ] 能解讀回撤圖
- [ ] 能使用網頁進行風險分析

---

# 第九週：統計套利（上）

## 學習目標
- 理解協整概念
- 學習配對選擇
- 理解價差交易

## Day 1：什麼是協整？

### 任務
```bash
python examples/pairs_trading_example.py
```

### 今日知識點
**Cointegration（協整）**

- **定態序列**：均值和變異數不隨時間改變
- 股價通常是非定態的（隨機遊走）
- 但兩支股票的**價差**可能是定態的

如果 A 和 B 的價差是定態的，我們說 A 和 B 協整。

---

## Day 2：協整檢定

### 觀察 Example 1：協整測試

### 今日知識點
**Engle-Granger 檢定**

```python
# 步驟
# 1. 回歸：Y = α + β × X
# 2. 計算殘差
# 3. 對殘差進行 ADF 檢定
# 4. 若 p-value < 0.05，則協整
```

---

## Day 3：對沖比率

### 觀察 Example 2：對沖比率

### 今日知識點
**Hedge Ratio**

```python
# 從回歸得到
Y = α + β × X

# β 就是對沖比率
# 如果 β = 1.5，表示
# 買 1 股 Y，要賣 1.5 股 X 來對沖
```

---

## Day 4：價差計算

### 觀察 Example 3：價差分析

### 今日知識點
**Spread 計算**

```python
spread = 價格Y - hedge_ratio × 價格X

# Z-score
zscore = (spread - 均值) / 標準差
```

---

## Day 5：配對選擇

### 觀察 Example 5：配對選擇

### 今日知識點
**如何選擇配對**

1. 同行業（如：兩家銀行）
2. 相似業務模式
3. 歷史上高相關
4. 通過協整檢定

---

## Day 6-7：理論閱讀

### 閱讀內容
計劃文檔 **1.3.1 協整**

### 第九週驗證清單
- [ ] 能解釋協整的概念
- [ ] 理解 Engle-Granger 檢定流程
- [ ] 知道如何計算對沖比率
- [ ] 能計算價差和 Z-score

---

# 第十週：統計套利（下）

## 學習目標
- 學習配對交易策略
- 理解半衰期
- 執行配對交易回測

## Day 1：交易信號

### 觀察 Example 4：交易信號

### 今日知識點
**配對交易信號**

```python
# 進場（做多價差）
if zscore < -2.0:
    買入 Y，賣出 β 單位 X

# 進場（做空價差）
if zscore > +2.0:
    賣出 Y，買入 β 單位 X

# 出場
if abs(zscore) < 0.5:
    平倉所有部位
```

---

## Day 2：半衰期

### 觀察 Example 6：半衰期

### 今日知識點
**Half-Life of Mean Reversion**

半衰期 = 價差從偏離位置回歸一半所需的時間

```python
# 解讀
# 半衰期 = 5 天：快速回歸，適合短期交易
# 半衰期 = 50 天：慢速回歸，需要更長持有期
# 半衰期 > 100 天：太慢，可能不適合交易
```

---

## Day 3：策略回測

### 任務
使用網頁介面回測配對交易

### 觀察
- 配對交易的收益曲線
- 勝率和盈虧比

---

## Day 4：風險管理

### 今日知識點
**配對交易的風險**

1. **協整破裂**：兩股票關係改變
2. **單邊風險**：對沖不完美
3. **執行風險**：需要同時交易兩支股票
4. **保證金風險**：做空需要保證金

---

## Day 5：策略組合

### 練習
思考：如何將配對交易與其他策略結合？

---

## Day 6-7：理論與複習

### 閱讀內容
計劃文檔 **1.3.2 配對交易** 和 **1.3.3 半衰期**

### 第十週驗證清單
- [ ] 能說出配對交易的進出場規則
- [ ] 理解半衰期的意義
- [ ] 知道配對交易的風險
- [ ] 能解讀配對交易回測結果

---

# 第十一週：動量策略

## 學習目標
- 學習四種動量策略
- 理解趨勢跟蹤
- 比較動量與均值回歸

## Day 1：動量策略概述

### 任務
```bash
python examples/momentum_example.py
```

### 今日知識點
**動量 vs 均值回歸**

| 策略 | 假設 | 操作 |
|------|------|------|
| 均值回歸 | 價格會回到均值 | 逆勢：低買高賣 |
| 動量 | 趨勢會持續 | 順勢：追漲殺跌 |

---

## Day 2：經典動量策略

### 觀察 Example 1

### 今日知識點
**Classic Momentum**

```python
# 計算過去 N 天的收益率
momentum = (今日價格 / N天前價格) - 1

# 如果動量 > 0，表示上升趨勢
# 如果動量 < 0，表示下降趨勢
```

---

## Day 3：趨勢跟蹤（ADX）

### 觀察 Example 2

### 今日知識點
**ADX (Average Directional Index)**

ADX 衡量趨勢強度（不是方向）：
- ADX > 25：強趨勢
- ADX < 20：無明顯趨勢

使用 ADX 過濾：只在趨勢明顯時交易

---

## Day 4：雙重動量

### 觀察 Example 3

### 今日知識點
**Dual Momentum**

結合兩種動量：
1. **絕對動量**：資產 vs 無風險
2. **相對動量**：資產 vs 其他資產

規則：
- 只有當絕對動量 > 0 時才持有
- 持有相對動量最高的資產

---

## Day 5：突破策略

### 觀察 Example 4

### 今日知識點
**Breakout Strategy**

```python
# 計算通道
upper = 過去 N 天最高價
lower = 過去 N 天最低價

# 信號
if 價格 > upper: 買入（向上突破）
if 價格 < lower: 賣出（向下突破）
```

---

## Day 6-7：策略比較與複習

### 練習
比較動量策略與均值回歸：

| 指標 | 動量策略 | 均值回歸 |
|------|---------|---------|
| 適用市場 | | |
| 持有期間 | | |
| 勝率 | | |
| 盈虧比 | | |

### 第十一週驗證清單
- [ ] 能解釋動量與均值回歸的差異
- [ ] 理解 ADX 的用途
- [ ] 知道雙重動量的邏輯
- [ ] 能解釋突破策略

---

# 第十二週：Walk-Forward 測試

## 學習目標
- 理解過擬合問題
- 學習 Walk-Forward 方法
- 評估策略穩健性

## Day 1：過擬合問題

### 今日知識點
**什麼是過擬合？**

過擬合 = 策略在歷史數據上表現完美，但在新數據上失效

原因：
- 參數太多
- 過度優化
- 數據探勘（測試太多策略）

---

## Day 2：Walk-Forward 概念

### 任務
```bash
python examples/walk_forward_example.py
```

### 今日知識點
**Walk-Forward Optimization**

```
時間軸：
|----訓練1----|--測試1--|
      |----訓練2----|--測試2--|
            |----訓練3----|--測試3--|

步驟：
1. 在訓練期優化參數
2. 在測試期驗證（不能修改參數）
3. 滾動窗口，重複
4. 組合所有測試期結果
```

---

## Day 3：Overfitting Ratio

### 觀察 Example 1 輸出

### 今日知識點
**過擬合比率**

```python
Overfitting Ratio = 測試期績效 / 訓練期績效

# 解讀
# Ratio = 1.0：訓練和測試表現一致，沒有過擬合
# Ratio < 0.5：測試表現只有訓練的一半，嚴重過擬合
# Ratio > 0.7：可接受的水平
```

---

## Day 4：滾動優化

### 觀察 Example 2

### 今日知識點
**Rolling Optimization**

定期重新優化參數，適應市場變化

```python
# 每月重新優化
reoptimize_frequency = 21  # 約一個月交易日

# 使用過去一年數據
lookback = 252
```

---

## Day 5：參數穩定性

### 觀察 Example 4

### 今日知識點
**Parameter Stability**

好的策略特徵：
- 最佳參數在不同窗口穩定
- 參數變化不會導致績效劇烈變化

---

## Day 6-7：綜合評估

### 練習
評估一個策略是否過擬合：

| 檢查項目 | 結果 |
|---------|------|
| Overfitting Ratio > 0.7 | |
| 參數穩定 | |
| 多窗口表現一致 | |

### 第十二週驗證清單
- [ ] 能解釋什麼是過擬合
- [ ] 理解 Walk-Forward 的流程
- [ ] 能解讀 Overfitting Ratio
- [ ] 知道如何評估策略穩健性

---

# 第十三週+：自訂策略開發

## 學習目標
- 開發自己的策略
- 完整回測流程
- 準備實盤交易

## Day 1-2：策略設計

### 任務
設計一個自己的策略

### 思考問題
1. 策略基於什麼假設？
2. 進場條件是什麼？
3. 出場條件是什麼？
4. 如何控制風險？

### 範本
```python
# my_strategy.py
from strategies import BaseStrategy
import pandas as pd
import numpy as np

class MyStrategy(BaseStrategy):
    def __init__(self, param1=10, param2=20, **kwargs):
        super().__init__(name="MyStrategy", **kwargs)
        self.param1 = param1
        self.param2 = param2

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(index=prices.index)

        # 在這裡實現你的策略邏輯
        # signals['signal'] = 1（買入）, -1（賣出）, 0（無操作）

        return signals
```

---

## Day 3-4：策略實現

### 任務
將設計轉換為代碼

### 步驟
1. 創建策略類
2. 實現信號邏輯
3. 測試基本功能

---

## Day 5-6：回測與優化

### 任務
1. 對策略進行回測
2. 進行 Walk-Forward 測試
3. 評估 Overfitting Ratio

### 命令
```bash
# 回測
python cli.py backtest run --strategy my_strategy --symbols AAPL,MSFT

# 生成報告
python cli.py report backtest --strategy my_strategy --output my_report.html
```

---

## Day 7+：持續改進

### 長期任務
1. **模擬交易**：使用 Trade Log 記錄模擬交易
2. **績效追蹤**：比較實際與回測結果
3. **策略改進**：根據結果調整
4. **風險管理**：設定停損和部位限制
5. **實盤準備**：至少 3 個月模擬成功後考慮實盤

---

## 實盤準備清單

### 必須完成
- [ ] 策略經過 Walk-Forward 驗證
- [ ] Overfitting Ratio > 0.7
- [ ] 完成 3 個月模擬交易
- [ ] 模擬結果與回測接近

### 風險管理規則
- [ ] 設定最大單筆虧損（如 2%）
- [ ] 設定最大回撤限制（如 10%）
- [ ] 設定最大持倉比例
- [ ] 設定交易頻率限制

### 心理準備
- [ ] 接受會有虧損
- [ ] 遵守交易紀律
- [ ] 不因短期結果改變策略
- [ ] 持續記錄和檢討

---

# 附錄：快速參考

## 常用命令

```bash
# 啟動網頁
streamlit run app.py

# 執行範例
python examples/basic_usage.py
python examples/backtest_example.py
python examples/optimization_example.py
python examples/risk_analysis_example.py
python examples/pairs_trading_example.py
python examples/momentum_example.py
python examples/walk_forward_example.py

# CLI 命令
python cli.py --help
python cli.py backtest run --help
python cli.py portfolio optimize --help

# 健康檢查
python scripts/health_check.py
```

## 關鍵公式

```
# 收益率
return = (P_t - P_{t-1}) / P_{t-1}

# 夏普比率
Sharpe = (R_p - R_f) / σ_p

# VaR (參數法)
VaR_95% = μ - 1.645 × σ

# Z-score
Z = (X - μ) / σ

# 最大回撤
MDD = min((Value - Peak) / Peak)
```

## 進階學習資源

1. **書籍**
   - 《Quantitative Trading》 - Ernest Chan
   - 《Advances in Financial Machine Learning》 - Marcos Lopez de Prado

2. **線上課程**
   - CQF (Certificate in Quantitative Finance)
   - Coursera: Financial Engineering and Risk Management

3. **工具文檔**
   - VectorBT: https://vectorbt.dev/
   - PyPortfolioOpt: https://pyportfolioopt.readthedocs.io/

---

**恭喜完成課程！繼續學習，持續進步！**
