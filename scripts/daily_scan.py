# -*- coding: utf-8 -*-
"""
每日自動掃描腳本 (Daily Scan Script) — Phase 4

功能：
1. 從 watchlists.json 讀取觀察清單
2. 基本面掃描 (FundamentalAlertChecker)
3. 新聞情緒掃描 (SentimentAnalyzer)
4. 多因子評分排名 (MultiFactorModel)
5. 產出每日晨報 (HTML + TXT)

使用方式：
    # 手動執行
    python scripts/daily_scan.py

    # 排程（macOS/Linux crontab）
    # 每個交易日早上 08:00 執行：
    # 0 8 * * 1-5 cd /path/to/quant_trading_tool && python scripts/daily_scan.py

    # 只跑基本面掃描
    python scripts/daily_scan.py --fundamental-only

    # 指定股票（不讀 watchlists.json）
    python scripts/daily_scan.py --symbols 2330,AAPL,NVDA
"""

import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime, date

# Setup path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("daily_scan")


def load_watchlist_symbols() -> list:
    """從 watchlists.json 讀取所有股票代碼。"""
    watchlist_path = PROJECT_ROOT / "config" / "watchlists.json"

    if not watchlist_path.exists():
        logger.warning(f"找不到 {watchlist_path}，使用預設清單")
        return ["2330", "AAPL", "NVDA"]

    with open(watchlist_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    symbols = []
    for key, group in data.items():
        if key.startswith("_"):
            continue
        if isinstance(group, dict) and "symbols" in group:
            symbols.extend(group["symbols"].keys())

    unique_symbols = sorted(set(symbols))
    logger.info(f"從觀察清單載入 {len(unique_symbols)} 檔股票: {unique_symbols}")
    return unique_symbols


def run_fundamental_scan(symbols: list) -> dict:
    """Phase 1: 基本面掃描。"""
    logger.info("=== Phase 1: 基本面掃描 ===")
    try:
        from core.fundamental_alerts import (
            FundamentalAlertChecker,
            generate_scan_report,
        )

        checker = FundamentalAlertChecker()
        result = checker.scan_watchlist(symbols)

        alerts = result.get("alerts", [])
        macro_alerts = result.get("macro_alerts", [])

        critical = [a for a in alerts if a.severity == "critical"]
        warnings = [a for a in alerts if a.severity == "warning"]

        logger.info(
            f"基本面掃描完成: {len(alerts)} 個警報 "
            f"(Critical: {len(critical)}, Warning: {len(warnings)})"
        )

        if macro_alerts:
            logger.info(f"總經警報: {len(macro_alerts)} 個")

        return {
            "result": result,
            "report": generate_scan_report(result),
            "critical_count": len(critical),
            "warning_count": len(warnings),
        }

    except Exception as e:
        logger.error(f"基本面掃描失敗: {e}")
        return {"result": {}, "report": f"掃描失敗: {e}", "critical_count": 0, "warning_count": 0}


def run_sentiment_scan(symbols: list) -> dict:
    """Phase 2: 新聞情緒掃描。"""
    logger.info("=== Phase 2: 新聞情緒掃描 ===")
    try:
        from core.sentiment import SentimentAnalyzer

        analyzer = SentimentAnalyzer()
        results = {}

        for symbol in symbols:
            try:
                sentiment = analyzer.get_stock_sentiment(symbol, days_back=3)
                results[symbol] = sentiment
                label = sentiment.get("label", "neutral")
                score = sentiment.get("avg_score", 0)
                total = sentiment.get("total_news", 0)
                logger.info(f"  {symbol}: {label} (score={score:.3f}, news={total})")
            except Exception as e:
                logger.warning(f"  {symbol}: 情緒分析失敗 - {e}")
                results[symbol] = {"label": "unknown", "avg_score": 0, "total_news": 0}

        return results

    except Exception as e:
        logger.error(f"情緒掃描失敗: {e}")
        return {}


def run_multi_factor(symbols: list) -> dict:
    """Phase 3: 多因子評分排名。"""
    logger.info("=== Phase 3: 多因子評分排名 ===")
    try:
        from core.multi_factor import MultiFactorModel

        model = MultiFactorModel()
        ranking = model.rank_watchlist(symbols)

        if ranking is not None and not ranking.empty:
            logger.info("多因子排名 (Top 10):")
            top = ranking.head(10)
            for _, row in top.iterrows():
                logger.info(
                    f"  {row['symbol']:>8s} | "
                    f"總分: {row['total_score']:5.1f} | "
                    f"技術: {row['technical']:5.1f} | "
                    f"基本面: {row['fundamental']:5.1f} | "
                    f"情緒: {row['sentiment']:5.1f} | "
                    f"{row.get('rating', '')}"
                )

            return {"ranking": ranking, "top_picks": top.to_dict("records")}

        return {"ranking": None, "top_picks": []}

    except Exception as e:
        logger.error(f"多因子評分失敗: {e}")
        return {"ranking": None, "top_picks": []}


def generate_daily_report(
    symbols: list,
    fundamental: dict,
    sentiment: dict,
    multi_factor: dict,
) -> str:
    """產出每日晨報文字版。"""
    today = date.today().strftime("%Y-%m-%d")
    weekday_zh = ["一", "二", "三", "四", "五", "六", "日"]
    weekday = weekday_zh[date.today().weekday()]

    lines = []
    lines.append("=" * 60)
    lines.append(f"  📊 每日晨報 — {today} (週{weekday})")
    lines.append("=" * 60)
    lines.append("")

    # --- Section 1: Fundamental Alerts ---
    lines.append("━━━ 1. 基本面警報 ━━━")
    crit = fundamental.get("critical_count", 0)
    warn = fundamental.get("warning_count", 0)
    if crit > 0:
        lines.append(f"  🔴 有 {crit} 個 Critical 警報，請立即檢查！")
    if warn > 0:
        lines.append(f"  🟡 有 {warn} 個 Warning 警報")
    if crit == 0 and warn == 0:
        lines.append("  ✅ 所有股票基本面正常")
    lines.append("")

    # List critical alerts
    result = fundamental.get("result", {})
    for alert in result.get("alerts", []):
        if alert.severity == "critical":
            lines.append(f"  🔴 [{alert.symbol}] {alert.message}")
    for alert in result.get("alerts", []):
        if alert.severity == "warning":
            lines.append(f"  🟡 [{alert.symbol}] {alert.message}")
    lines.append("")

    # --- Section 2: Sentiment ---
    lines.append("━━━ 2. 新聞情緒概覽 ━━━")
    if sentiment:
        positive = [s for s, v in sentiment.items() if v.get("label") == "positive"]
        negative = [s for s, v in sentiment.items() if v.get("label") == "negative"]

        if positive:
            lines.append(f"  📈 正面情緒: {', '.join(positive)}")
        if negative:
            lines.append(f"  📉 負面情緒: {', '.join(negative)}")
        if not positive and not negative:
            lines.append("  ➖ 所有股票情緒中性")
    else:
        lines.append("  （情緒掃描未執行）")
    lines.append("")

    # --- Section 3: Multi-Factor Ranking ---
    lines.append("━━━ 3. 多因子評分 Top 10 ━━━")
    top_picks = multi_factor.get("top_picks", [])
    if top_picks:
        lines.append(f"  {'排名':<4} {'股票':<8} {'總分':>6} {'技術':>6} {'基本面':>6} {'情緒':>6} {'評級'}")
        lines.append("  " + "-" * 55)
        for i, row in enumerate(top_picks, 1):
            lines.append(
                f"  {i:<4} {row['symbol']:<8} "
                f"{row['total_score']:>5.1f} "
                f"{row['technical']:>6.1f} "
                f"{row['fundamental']:>6.1f} "
                f"{row['sentiment']:>6.1f} "
                f"{row.get('rating', '')}"
            )
    else:
        lines.append("  （多因子評分未執行）")
    lines.append("")

    # --- Footer ---
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"  掃描時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  掃描股票: {len(symbols)} 檔")
    lines.append("=" * 60)

    return "\n".join(lines)


def save_report(report_text: str, report_dir: Path):
    """儲存報告到檔案。"""
    report_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().strftime("%Y%m%d")

    # Text version
    txt_path = report_dir / f"daily_{today}.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    logger.info(f"報告已儲存: {txt_path}")

    return txt_path


def main():
    parser = argparse.ArgumentParser(description="每日自動掃描腳本")
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="指定股票（逗號分隔），例: 2330,AAPL,NVDA"
    )
    parser.add_argument(
        "--fundamental-only",
        action="store_true",
        help="只跑基本面掃描"
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="不儲存報告檔案"
    )
    args = parser.parse_args()

    logger.info("🚀 開始每日掃描...")

    # Load symbols
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",")]
    else:
        symbols = load_watchlist_symbols()

    if not symbols:
        logger.error("沒有股票可掃描，結束。")
        sys.exit(1)

    # Run scans
    fundamental = run_fundamental_scan(symbols)

    if args.fundamental_only:
        sentiment_results = {}
        mf_results = {"ranking": None, "top_picks": []}
    else:
        sentiment_results = run_sentiment_scan(symbols)
        mf_results = run_multi_factor(symbols)

    # Generate report
    report = generate_daily_report(symbols, fundamental, sentiment_results, mf_results)
    print("\n" + report)

    # Save
    if not args.no_save:
        report_dir = PROJECT_ROOT / "reports"
        save_report(report, report_dir)

    # Summary
    crit = fundamental.get("critical_count", 0)
    if crit > 0:
        logger.warning(f"⚠️ 有 {crit} 個 Critical 警報，建議立即處理！")
    else:
        logger.info("✅ 掃描完成，無緊急事項。")


if __name__ == "__main__":
    main()
