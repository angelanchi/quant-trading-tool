# -*- coding: utf-8 -*-
"""
Context Engine 端到端驗證腳本

目的：用完全免費的資料源（yfinance + Google News RSS）
     驗證 context_engine 的時間軸建構能否跑通。

不需要任何 API Key！

使用方式：
    cd quant_trading_tool
    python scripts/verify_context_engine.py

    # 指定股票
    python scripts/verify_context_engine.py --symbol NVDA

    # 台股
    python scripts/verify_context_engine.py --symbol 2330
"""

import sys
import os
from pathlib import Path
from datetime import datetime, date, timedelta
import argparse
import json

# 加入專案根目錄到 path
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)


def print_header(title: str):
    """印出漂亮的標題。"""
    width = 60
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def print_result(name: str, success: bool, detail: str = ""):
    """印出測試結果。"""
    icon = "✅" if success else "❌"
    print(f"  {icon} {name}")
    if detail:
        print(f"     → {detail}")


# =====================================================================
# Step 1: 驗證 yfinance 是否可用
# =====================================================================
def verify_yfinance(symbol: str) -> dict:
    """驗證 yfinance 能否抓到股價和基本財報。"""
    print_header("Step 1: 驗證 yfinance 資料源")
    result = {'price': False, 'financials': False, 'info': False}

    try:
        import yfinance as yf
        print_result("yfinance 已安裝", True, f"版本: {yf.__version__}")
    except ImportError:
        print_result("yfinance 未安裝", False, "請執行: pip install yfinance")
        return result

    # 1a. 股價資料
    try:
        ticker = yf.Ticker(symbol)
        end = date.today()
        start = end - timedelta(days=90)
        hist = ticker.history(start=start.strftime('%Y-%m-%d'),
                              end=end.strftime('%Y-%m-%d'))
        if not hist.empty:
            result['price'] = True
            latest = hist.iloc[-1]
            print_result(
                f"股價資料 ({symbol})", True,
                f"共 {len(hist)} 筆, 最新收盤: {latest['Close']:.2f} "
                f"({hist.index[-1].strftime('%Y-%m-%d')})"
            )
        else:
            print_result(f"股價資料 ({symbol})", False, "回傳空 DataFrame")
    except Exception as e:
        print_result(f"股價資料 ({symbol})", False, str(e))

    # 1b. 基本財報（季度損益表）
    try:
        income = ticker.quarterly_income_stmt
        if income is not None and not income.empty:
            result['financials'] = True
            cols = list(income.columns[:4])
            quarters = [c.strftime('%Y-Q%q') if hasattr(c, 'strftime')
                        else str(c) for c in cols]
            print_result(
                "季度損益表", True,
                f"共 {len(income.columns)} 季, 最近: {quarters[0] if quarters else 'N/A'}"
            )

            # 嘗試取得關鍵數字
            for key in ['Total Revenue', 'Net Income', 'Gross Profit']:
                if key in income.index:
                    val = income.loc[key].iloc[0]
                    if val and not (isinstance(val, float) and val != val):
                        print(f"       {key}: {val:,.0f}")
        else:
            print_result("季度損益表", False, "無資料（台股可能不支援）")
    except Exception as e:
        print_result("季度損益表", False, str(e))

    # 1c. 公司資訊
    try:
        info = ticker.info
        if info and 'shortName' in info:
            result['info'] = True
            print_result(
                "公司資訊", True,
                f"{info.get('shortName', 'N/A')} | "
                f"PE: {info.get('trailingPE', 'N/A')} | "
                f"Market Cap: {info.get('marketCap', 'N/A')}"
            )
        else:
            print_result("公司資訊", False, "info 為空")
    except Exception as e:
        print_result("公司資訊", False, str(e))

    return result


# =====================================================================
# Step 2: 驗證 Google News RSS
# =====================================================================
def verify_google_news(symbol: str) -> dict:
    """驗證 Google News RSS 能否抓到新聞。"""
    print_header("Step 2: 驗證 Google News RSS（免費，無需 Key）")
    result = {'news_en': False, 'news_zh': False}

    import urllib.request
    import urllib.parse
    import xml.etree.ElementTree as ET

    # 2a. 英文新聞
    try:
        query = f"{symbol} stock"
        encoded_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_data = resp.read()

        root = ET.fromstring(xml_data)
        items = root.findall('.//item')

        if items:
            result['news_en'] = True
            print_result(
                f"英文新聞 ({query})", True,
                f"共 {len(items)} 則"
            )
            # 顯示前 3 則
            for item in items[:3]:
                title = item.find('title').text or ""
                pub_date = item.find('pubDate').text or ""
                print(f"       • {title[:60]}...")
                print(f"         {pub_date}")
        else:
            print_result(f"英文新聞 ({query})", False, "找不到新聞")
    except Exception as e:
        print_result(f"英文新聞", False, str(e))

    # 2b. 中文新聞（如果是台股）
    clean_sym = symbol.replace('.TW', '').replace('.TWO', '')
    if clean_sym.isdigit():
        try:
            # 台股用股票代號搜尋
            query_zh = f"{symbol} 台股"
            encoded_query_zh = urllib.parse.quote(query_zh)
            url_zh = f"https://news.google.com/rss/search?q={encoded_query_zh}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
            req = urllib.request.Request(url_zh, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                xml_data = resp.read()

            root = ET.fromstring(xml_data)
            items = root.findall('.//item')

            if items:
                result['news_zh'] = True
                print_result(
                    f"中文新聞 ({query_zh})", True,
                    f"共 {len(items)} 則"
                )
                for item in items[:3]:
                    title = item.find('title').text or ""
                    print(f"       • {title[:60]}")
            else:
                print_result(f"中文新聞", False, "找不到新聞")
        except Exception as e:
            print_result(f"中文新聞", False, str(e))

    return result


# =====================================================================
# Step 3: 驗證 Context Engine 整合
# =====================================================================
def verify_context_engine(symbol: str) -> dict:
    """驗證 context_engine 能否建構時間軸。"""
    print_header("Step 3: 驗證 Context Engine 時間軸建構")
    result = {'timeline': False, 'events_count': 0, 'card': False}

    try:
        from core.context_engine import ContextEngine
        print_result("ContextEngine 匯入成功", True)
    except ImportError as e:
        print_result("ContextEngine 匯入失敗", False, str(e))
        return result

    engine = ContextEngine()

    # 3a. 建構時間軸
    try:
        timeline = engine.build_timeline(
            symbol,
            days_back=30,
            include_news=True,
            include_financials=True,
            include_macro=False,  # 先不測總經（需要 FRED Key）
            include_price_events=True,
        )

        result['events_count'] = len(timeline.events)

        if timeline.events:
            result['timeline'] = True
            print_result(
                f"時間軸建構 ({symbol})", True,
                f"共 {len(timeline.events)} 個事件"
            )

            # 按類型統計
            from collections import Counter
            type_counts = Counter(e.event_type.value for e in timeline.events)
            print("       事件類型分布:")
            for etype, count in type_counts.most_common():
                print(f"         {etype}: {count}")

            # 顯示最近 5 個事件
            timeline.sort_events()
            print("\n       最近 5 個事件:")
            for event in timeline.events[:5]:
                date_str = (event.date.strftime('%Y-%m-%d')
                            if isinstance(event.date, datetime) else str(event.date))
                impact_icon = {'positive': '📈', 'negative': '📉', 'neutral': '➖'}.get(
                    event.impact, '❓'
                )
                print(f"         {date_str} {impact_icon} {event.title[:50]}")

            # 有價格資料嗎？
            if timeline.price_data is not None and not timeline.price_data.empty:
                print_result(
                    "價格資料", True,
                    f"共 {len(timeline.price_data)} 筆交易日"
                )
            else:
                print_result("價格資料", False, "timeline.price_data 為空")
        else:
            print_result(
                f"時間軸建構 ({symbol})", False,
                "事件數為 0，可能是資料源連線問題"
            )

    except Exception as e:
        print_result(f"時間軸建構", False, str(e))
        import traceback
        traceback.print_exc()

    # 3b. 背景卡片
    try:
        card = engine.get_context_card(symbol)
        if card and card.get('symbol'):
            result['card'] = True
            print_result("背景卡片", True)
            # 顯示卡片內容
            ratios = card.get('key_ratios', {})
            if ratios:
                print(f"       關鍵比率: {json.dumps(ratios, indent=2, default=str)[:200]}")
            news = card.get('recent_news', [])
            print(f"       近期新聞: {len(news)} 則")
        else:
            print_result("背景卡片", False, "回傳為空")
    except Exception as e:
        print_result("背景卡片", False, str(e))

    return result


# =====================================================================
# Step 4: 驗證情緒分析
# =====================================================================
def verify_sentiment() -> dict:
    """驗證情緒分析模組。"""
    print_header("Step 4: 驗證情緒分析（Level 1 關鍵字）")
    result = {'sentiment': False}

    try:
        from core.sentiment import SentimentAnalyzer
        analyzer = SentimentAnalyzer()

        test_cases = [
            ("台積電法說會釋出正面展望，AI 營收大幅成長", "positive"),
            ("NVIDIA beats earnings expectations with record revenue", "positive"),
            ("公司宣布大規模裁員，營收連續衰退", "negative"),
            ("Fed raises interest rates, market sells off", "negative"),
            ("公司召開例行股東會", "neutral"),
        ]

        all_pass = True
        for text, expected in test_cases:
            res = analyzer.analyze(text)
            label = res.get('label', 'unknown')
            score = res.get('score', 0)
            match = (label == expected)
            if not match:
                all_pass = False
            icon = "✓" if match else "✗"
            print(f"     {icon} [{label:8s}] (score: {score:+.2f}) {text[:40]}...")

        result['sentiment'] = all_pass
        print_result(
            "情緒分析", all_pass,
            "所有測試通過" if all_pass else "部分測試未通過（可接受，關鍵字規則有限制）"
        )

    except Exception as e:
        print_result("情緒分析", False, str(e))

    return result


# =====================================================================
# 總結報告
# =====================================================================
def print_summary(results: dict):
    """印出總結。"""
    print_header("驗證總結")

    total = 0
    passed = 0
    for category, checks in results.items():
        for name, ok in checks.items():
            if isinstance(ok, bool):
                total += 1
                if ok:
                    passed += 1

    print(f"\n  通過: {passed}/{total}")
    print(f"  通過率: {passed/total*100:.0f}%\n" if total > 0 else "")

    # 下一步建議
    print("  📋 下一步建議:")

    yf = results.get('yfinance', {})
    if not yf.get('price'):
        print("     1. 安裝 yfinance: pip install yfinance")
    elif not results.get('context', {}).get('timeline'):
        print("     1. 檢查 context_engine 的資料源連接")
        print("        可能需要調整 DataManager 的 fallback 邏輯")
    else:
        print("     1. ✅ 基本功能正常！可以開始增強時間軸視覺化")

    print("     2. 申請免費 API Keys 以取得更完整資料:")
    print("        - FinMind: https://finmindtrade.com (台股財報)")
    print("        - FRED: https://fred.stlouisfed.org/docs/api/api_key.html (總經)")
    print("        - Finnhub: https://finnhub.io (美股新聞)")
    print("     3. 設定 .env 檔案（參考 docs/API_KEY_SETUP_GUIDE.md）")
    print("")


# =====================================================================
# Main
# =====================================================================
def main():
    parser = argparse.ArgumentParser(description='Context Engine 端到端驗證')
    parser.add_argument('--symbol', default='AAPL',
                        help='測試用股票代號 (預設: AAPL)')
    args = parser.parse_args()

    symbol = args.symbol

    print("\n" + "🔍" * 30)
    print(f"  Context Engine 端到端驗證")
    print(f"  測試股票: {symbol}")
    print(f"  時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🔍" * 30)

    results = {}

    # Step 1: yfinance
    results['yfinance'] = verify_yfinance(symbol)

    # Step 2: Google News RSS
    results['news'] = verify_google_news(symbol)

    # Step 3: Context Engine
    results['context'] = verify_context_engine(symbol)

    # Step 4: Sentiment
    results['sentiment'] = verify_sentiment()

    # 總結
    print_summary(results)


if __name__ == '__main__':
    main()
