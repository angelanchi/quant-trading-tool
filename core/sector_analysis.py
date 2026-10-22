# -*- coding: utf-8 -*-
"""
產業分析模組 (Sector Analysis Module)

功能：
1. SectorMap — 產業分類與股票映射，讀取 config/sectors.json
2. SectorRotationTracker — 產業輪動追蹤（動量、相對強弱）
3. SupplyChainAnalyzer — 供應鏈上下游連動分析
4. PeerComparison — 同產業個股比較
5. SectorNewsTracker — 產業新聞與政策追蹤
6. SectorAnalysisManager — 統一入口

資料來源：
- 台股：FinMind / yfinance（.TW 後綴）
- 美股：yfinance
- 新聞：Google News RSS / Finnhub
"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timedelta
from enum import Enum

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# ============================================================================
# Constants
# ============================================================================
CONFIG_DIR = Path(__file__).parent.parent / "config"
SECTORS_FILE = CONFIG_DIR / "sectors.json"


# ============================================================================
# Data Classes
# ============================================================================
class ChainPosition(Enum):
    UPSTREAM = "upstream"
    MIDSTREAM = "midstream"
    DOWNSTREAM = "downstream"
    REFERENCE_US = "reference_us"


@dataclass
class SectorInfo:
    """產業基本資訊。"""
    key: str
    name: str
    name_en: str
    description: str
    symbols: dict  # {symbol: description}


@dataclass
class SectorMomentum:
    """產業動量指標。"""
    sector_key: str
    sector_name: str
    avg_return_1w: float = 0.0
    avg_return_1m: float = 0.0
    avg_return_3m: float = 0.0
    avg_volume_change: float = 0.0  # vs 20-day avg
    breadth: float = 0.0  # % of stocks above 20MA
    momentum_score: float = 0.0  # 0~100 composite


@dataclass
class PeerMetrics:
    """同業個股比較指標。"""
    symbol: str
    name: str
    price: float = 0.0
    change_1w: float = 0.0
    change_1m: float = 0.0
    change_3m: float = 0.0
    volume_ratio: float = 0.0  # vs 20-day avg
    rsi_14: float = 50.0
    pe_ratio: Optional[float] = None
    revenue_yoy: Optional[float] = None
    relative_strength: float = 0.0  # vs sector avg


@dataclass
class ChainNode:
    """供應鏈節點。"""
    position: ChainPosition
    category: str  # e.g. "晶圓代工", "封測"
    symbols: list
    names: dict = field(default_factory=dict)  # {symbol: name}


# ============================================================================
# 1. SectorMap — 產業分類映射
# ============================================================================
class SectorMap:
    """讀取並管理產業分類設定。"""

    def __init__(self, config_path: Path = SECTORS_FILE):
        self._config_path = config_path
        self._data = {}
        self._sectors: dict[str, SectorInfo] = {}
        self._supply_chains: dict = {}
        self._load()

    def _load(self):
        """載入 sectors.json。"""
        if not self._config_path.exists():
            logger.warning(f"找不到 {self._config_path}，使用空白設定")
            return

        with open(self._config_path, "r", encoding="utf-8") as f:
            self._data = json.load(f)

        # Parse sectors
        for key, info in self._data.get("sectors", {}).items():
            self._sectors[key] = SectorInfo(
                key=key,
                name=info.get("name", key),
                name_en=info.get("name_en", ""),
                description=info.get("description", ""),
                symbols=info.get("symbols", {}),
            )

        # Parse supply chains
        self._supply_chains = self._data.get("supply_chain", {})

        logger.info(
            f"載入 {len(self._sectors)} 個產業, "
            f"{len(self._supply_chains)} 條供應鏈"
        )

    @property
    def sectors(self) -> dict[str, SectorInfo]:
        return self._sectors

    @property
    def sector_names(self) -> list[str]:
        return [s.name for s in self._sectors.values()]

    @property
    def supply_chains(self) -> dict:
        return {
            k: v for k, v in self._supply_chains.items()
            if not k.startswith("_")
        }

    def get_sector(self, key: str) -> Optional[SectorInfo]:
        return self._sectors.get(key)

    def find_sector_by_symbol(self, symbol: str) -> Optional[SectorInfo]:
        """找出某檔股票所屬產業。"""
        for sector in self._sectors.values():
            if symbol in sector.symbols:
                return sector
        return None

    def get_all_symbols(self) -> list[str]:
        """取得所有產業內的股票代碼。"""
        symbols = set()
        for sector in self._sectors.values():
            symbols.update(sector.symbols.keys())
        return sorted(symbols)

    def get_supply_chain(self, chain_key: str) -> Optional[dict]:
        """取得供應鏈定義。"""
        return self.supply_chains.get(chain_key)

    def get_us_reference(self) -> dict:
        """取得美股參考產業。"""
        return self._data.get("us_reference_sectors", {})


# ============================================================================
# 2. SectorRotationTracker — 產業輪動追蹤
# ============================================================================
class SectorRotationTracker:
    """
    追蹤資金在產業間的輪動。

    計算每個產業的：
    - 1W / 1M / 3M 平均報酬
    - 成交量變化（相對 20日均量）
    - 廣度指標（站上 20MA 的比例）
    - 綜合動量分數 (0~100)
    """

    def __init__(self, sector_map: Optional[SectorMap] = None):
        self._sector_map = sector_map or SectorMap()
        # 已確認的上櫃 (OTC/TPEx) 股票快取：symbol -> True
        self._otc_cache: dict = {}

    def _is_taiwan_stock(self, symbol: str) -> bool:
        return symbol.isdigit() or (len(symbol) == 5 and symbol[:4].isdigit())

    def _get_yf_symbol(self, symbol: str) -> str:
        if self._is_taiwan_stock(symbol):
            if self._otc_cache.get(symbol):
                return f"{symbol}.TWO"
            return f"{symbol}.TW"
        return symbol

    def _fetch_price_data(self, symbols: list, period: str = "6mo") -> dict:
        """用 yfinance 取得價格資料，上市失敗自動改試上櫃 (.TWO)。"""
        import yfinance as yf

        result = {}
        yf_symbols = [self._get_yf_symbol(s) for s in symbols]

        try:
            data = yf.download(
                yf_symbols,
                period=period,
                progress=False,
                group_by="ticker",
                threads=True,
            )

            failed_tw = []  # 下載失敗的台股，待重試 .TWO
            for orig, yf_sym in zip(symbols, yf_symbols):
                try:
                    if len(yf_symbols) == 1:
                        df = data
                    else:
                        df = data[yf_sym] if yf_sym in data.columns.get_level_values(0) else None

                    if df is not None and not df.empty:
                        # Flatten columns if needed
                        if isinstance(df.columns, pd.MultiIndex):
                            df.columns = df.columns.get_level_values(-1)
                        df = df.dropna(subset=["Close"])
                        if not df.empty:
                            result[orig] = df
                            continue

                    # 台股且用 .TW 失敗 → 加入重試清單
                    if self._is_taiwan_stock(orig) and yf_sym.endswith('.TW'):
                        failed_tw.append(orig)
                except Exception:
                    if self._is_taiwan_stock(orig) and yf_sym.endswith('.TW'):
                        failed_tw.append(orig)

            # 重試失敗的台股，改用 .TWO（上櫃）
            if failed_tw:
                two_symbols = [f"{s}.TWO" for s in failed_tw]
                logger.info(f"嘗試上櫃 (.TWO) 下載: {', '.join(failed_tw)}")
                try:
                    data2 = yf.download(
                        two_symbols,
                        period=period,
                        progress=False,
                        group_by="ticker",
                        threads=True,
                    )
                    for orig, yf_sym in zip(failed_tw, two_symbols):
                        try:
                            if len(two_symbols) == 1:
                                df = data2
                            else:
                                df = data2[yf_sym] if yf_sym in data2.columns.get_level_values(0) else None
                            if df is not None and not df.empty:
                                if isinstance(df.columns, pd.MultiIndex):
                                    df.columns = df.columns.get_level_values(-1)
                                df = df.dropna(subset=["Close"])
                                if not df.empty:
                                    result[orig] = df
                                    self._otc_cache[orig] = True
                                    logger.info(f"{orig} 確認為上櫃股 (.TWO)")
                        except Exception:
                            pass
                except Exception as e:
                    logger.warning(f"yfinance .TWO 批次下載失敗: {e}")

        except Exception as e:
            logger.warning(f"yfinance 批次下載失敗: {e}")

        return result

    def _calc_return(self, df: pd.DataFrame, days: int) -> float:
        """計算 N 天報酬率。"""
        if df is None or len(df) < days:
            return 0.0
        try:
            close = df["Close"]
            if len(close) < days:
                return 0.0
            return float((close.iloc[-1] / close.iloc[-days] - 1))
        except Exception:
            return 0.0

    def _calc_volume_ratio(self, df: pd.DataFrame, window: int = 20) -> float:
        """計算最近成交量 vs N日均量比。"""
        if df is None or len(df) < window:
            return 1.0
        try:
            vol = df["Volume"]
            avg_vol = vol.iloc[-window:].mean()
            recent_vol = vol.iloc[-5:].mean()
            return float(recent_vol / avg_vol) if avg_vol > 0 else 1.0
        except Exception:
            return 1.0

    def _calc_breadth(self, price_data: dict, ma_window: int = 20) -> float:
        """計算站上 N 日均線的股票比例。"""
        if not price_data:
            return 0.0

        above = 0
        total = 0
        for sym, df in price_data.items():
            if df is None or len(df) < ma_window:
                continue
            try:
                ma = df["Close"].rolling(ma_window).mean().iloc[-1]
                current = df["Close"].iloc[-1]
                total += 1
                if current > ma:
                    above += 1
            except Exception:
                pass

        return above / total if total > 0 else 0.0

    def track_all_sectors(self) -> list[SectorMomentum]:
        """計算所有產業的動量指標。"""
        results = []

        for key, sector in self._sector_map.sectors.items():
            if key == "ETF_指數":
                continue  # 跳過 ETF

            symbols = list(sector.symbols.keys())
            if not symbols:
                continue

            logger.info(f"分析產業: {sector.name} ({len(symbols)} 檔)")

            price_data = self._fetch_price_data(symbols)

            # Calc average returns
            returns_1w = [self._calc_return(price_data.get(s), 5) for s in symbols]
            returns_1m = [self._calc_return(price_data.get(s), 20) for s in symbols]
            returns_3m = [self._calc_return(price_data.get(s), 60) for s in symbols]
            vol_ratios = [self._calc_volume_ratio(price_data.get(s)) for s in symbols]

            avg_1w = np.mean(returns_1w) if returns_1w else 0.0
            avg_1m = np.mean(returns_1m) if returns_1m else 0.0
            avg_3m = np.mean(returns_3m) if returns_3m else 0.0
            avg_vol = np.mean(vol_ratios) if vol_ratios else 1.0
            breadth = self._calc_breadth(price_data)

            # Composite momentum score (0~100)
            # 1W weight=30, 1M weight=30, 3M weight=15, volume=10, breadth=15
            score = 50.0  # neutral baseline
            score += avg_1w * 100 * 3.0   # 1W: ±3% → ±9 points
            score += avg_1m * 100 * 1.5   # 1M: ±5% → ±7.5 points
            score += avg_3m * 100 * 0.5   # 3M
            score += (avg_vol - 1.0) * 10  # volume: above avg → positive
            score += (breadth - 0.5) * 30  # breadth: >50% → positive
            score = max(0, min(100, score))

            results.append(SectorMomentum(
                sector_key=key,
                sector_name=sector.name,
                avg_return_1w=avg_1w,
                avg_return_1m=avg_1m,
                avg_return_3m=avg_3m,
                avg_volume_change=avg_vol,
                breadth=breadth,
                momentum_score=score,
            ))

        # Sort by momentum score descending
        results.sort(key=lambda x: x.momentum_score, reverse=True)
        return results

    def to_dataframe(self, results: list[SectorMomentum]) -> pd.DataFrame:
        """轉換為 DataFrame。"""
        data = []
        for r in results:
            data.append({
                "產業": r.sector_name,
                "動量分數": round(r.momentum_score, 1),
                "1W 報酬": f"{r.avg_return_1w:.2%}",
                "1M 報酬": f"{r.avg_return_1m:.2%}",
                "3M 報酬": f"{r.avg_return_3m:.2%}",
                "量能比": f"{r.avg_volume_change:.2f}x",
                "廣度": f"{r.breadth:.0%}",
            })
        return pd.DataFrame(data)


# ============================================================================
# 3. SupplyChainAnalyzer — 供應鏈上下游分析
# ============================================================================
class SupplyChainAnalyzer:
    """
    分析供應鏈上下游的連動效應。

    輸入一條供應鏈（如 AI 伺服器），輸出：
    - 各層（上游/中游/下游）的表現
    - 層間價格相關性
    - 領先/落後指標
    """

    def __init__(self, sector_map: Optional[SectorMap] = None):
        self._sector_map = sector_map or SectorMap()
        self._rotation_tracker = SectorRotationTracker(self._sector_map)

    def parse_chain(self, chain_key: str) -> list[ChainNode]:
        """解析供應鏈為節點列表。"""
        chain_def = self._sector_map.get_supply_chain(chain_key)
        if not chain_def:
            logger.warning(f"找不到供應鏈: {chain_key}")
            return []

        nodes = []
        # Get symbol names from sector definitions
        all_names = {}
        for sector in self._sector_map.sectors.values():
            all_names.update(sector.symbols)

        for position in [ChainPosition.UPSTREAM, ChainPosition.MIDSTREAM, ChainPosition.DOWNSTREAM]:
            layer = chain_def.get(position.value, {})
            for category, symbols in layer.items():
                names = {s: all_names.get(s, s) for s in symbols}
                nodes.append(ChainNode(
                    position=position,
                    category=category,
                    symbols=symbols,
                    names=names,
                ))

        # US reference
        us_ref = chain_def.get("reference_us", [])
        if us_ref:
            nodes.append(ChainNode(
                position=ChainPosition.REFERENCE_US,
                category="美股參考",
                symbols=us_ref,
                names={s: s for s in us_ref},
            ))

        return nodes

    def analyze_chain(self, chain_key: str) -> dict:
        """分析一條供應鏈的表現。"""
        nodes = self.parse_chain(chain_key)
        if not nodes:
            return {}

        chain_def = self._sector_map.get_supply_chain(chain_key)

        # Collect all symbols
        all_symbols = []
        for node in nodes:
            all_symbols.extend(node.symbols)
        all_symbols = list(set(all_symbols))

        # Fetch price data
        price_data = self._rotation_tracker._fetch_price_data(all_symbols)

        # Analyze per layer
        layer_results = {}
        for position in [ChainPosition.UPSTREAM, ChainPosition.MIDSTREAM,
                         ChainPosition.DOWNSTREAM, ChainPosition.REFERENCE_US]:
            layer_nodes = [n for n in nodes if n.position == position]
            if not layer_nodes:
                continue

            layer_symbols = []
            for n in layer_nodes:
                layer_symbols.extend(n.symbols)

            returns_1w = []
            returns_1m = []
            for s in layer_symbols:
                if s in price_data:
                    returns_1w.append(self._rotation_tracker._calc_return(price_data[s], 5))
                    returns_1m.append(self._rotation_tracker._calc_return(price_data[s], 20))

            layer_results[position.value] = {
                "categories": [n.category for n in layer_nodes],
                "symbols": layer_symbols,
                "avg_return_1w": np.mean(returns_1w) if returns_1w else 0.0,
                "avg_return_1m": np.mean(returns_1m) if returns_1m else 0.0,
                "stock_details": [],
            }

            # Individual stock detail
            for s in layer_symbols:
                if s in price_data:
                    r1w = self._rotation_tracker._calc_return(price_data[s], 5)
                    r1m = self._rotation_tracker._calc_return(price_data[s], 20)
                    layer_results[position.value]["stock_details"].append({
                        "symbol": s,
                        "name": next((n.names.get(s, s) for n in layer_nodes if s in n.symbols), s),
                        "return_1w": r1w,
                        "return_1m": r1m,
                    })

        # Correlation analysis between layers
        correlation = self._calc_layer_correlation(price_data, nodes)

        return {
            "chain_name": chain_def.get("name", chain_key),
            "layers": layer_results,
            "correlation": correlation,
            "total_stocks": len(all_symbols),
        }

    def _calc_layer_correlation(self, price_data: dict, nodes: list[ChainNode]) -> dict:
        """計算不同層之間的價格相關性。"""
        layer_returns = {}

        for position in [ChainPosition.UPSTREAM, ChainPosition.MIDSTREAM, ChainPosition.DOWNSTREAM]:
            layer_nodes = [n for n in nodes if n.position == position]
            all_series = []

            for node in layer_nodes:
                for s in node.symbols:
                    if s in price_data and len(price_data[s]) > 20:
                        ret = price_data[s]["Close"].pct_change().dropna()
                        all_series.append(ret)

            if all_series:
                # Average returns of the layer
                combined = pd.concat(all_series, axis=1).mean(axis=1)
                layer_returns[position.value] = combined

        # Calc pairwise correlation
        corr_results = {}
        positions = list(layer_returns.keys())
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                p1, p2 = positions[i], positions[j]
                try:
                    aligned = pd.concat(
                        [layer_returns[p1], layer_returns[p2]],
                        axis=1,
                        keys=[p1, p2],
                    ).dropna()
                    if len(aligned) > 10:
                        corr = aligned[p1].corr(aligned[p2])
                        corr_results[f"{p1}_vs_{p2}"] = round(corr, 3)
                except Exception:
                    pass

        return corr_results

    def chain_summary_df(self, analysis: dict) -> pd.DataFrame:
        """輸出供應鏈分析摘要 DataFrame。"""
        rows = []
        position_names = {
            "upstream": "上游",
            "midstream": "中游",
            "downstream": "下游",
            "reference_us": "美股參考",
        }

        for pos, data in analysis.get("layers", {}).items():
            for stock in data.get("stock_details", []):
                rows.append({
                    "位置": position_names.get(pos, pos),
                    "類別": ", ".join(data["categories"]),
                    "股票": stock["symbol"],
                    "名稱": stock["name"],
                    "1W 報酬": f"{stock['return_1w']:.2%}",
                    "1M 報酬": f"{stock['return_1m']:.2%}",
                })

        return pd.DataFrame(rows)


# ============================================================================
# 4. PeerComparison — 同產業個股比較
# ============================================================================
class PeerComparison:
    """
    同產業內個股橫向比較。

    比較面向：價格表現、技術指標、基本面指標。
    """

    def __init__(self, sector_map: Optional[SectorMap] = None):
        self._sector_map = sector_map or SectorMap()
        self._rotation_tracker = SectorRotationTracker(self._sector_map)

    def _calc_rsi(self, close: pd.Series, period: int = 14) -> float:
        """計算 RSI。"""
        if len(close) < period + 1:
            return 50.0
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        val = rsi.iloc[-1]
        return float(val) if pd.notna(val) else 50.0

    def compare_sector(self, sector_key: str) -> list[PeerMetrics]:
        """比較指定產業內所有個股。"""
        sector = self._sector_map.get_sector(sector_key)
        if not sector:
            logger.warning(f"找不到產業: {sector_key}")
            return []

        symbols = list(sector.symbols.keys())
        price_data = self._rotation_tracker._fetch_price_data(symbols)

        results = []
        sector_returns_1m = []

        # First pass: calc individual metrics
        for sym in symbols:
            df = price_data.get(sym)
            if df is None or df.empty:
                continue

            close = df["Close"]
            r1w = self._rotation_tracker._calc_return(df, 5)
            r1m = self._rotation_tracker._calc_return(df, 20)
            r3m = self._rotation_tracker._calc_return(df, 60)
            vol_ratio = self._rotation_tracker._calc_volume_ratio(df)
            rsi = self._calc_rsi(close)

            sector_returns_1m.append(r1m)

            results.append(PeerMetrics(
                symbol=sym,
                name=sector.symbols.get(sym, sym).split("—")[0].strip() if "—" in sector.symbols.get(sym, "") else sym,
                price=float(close.iloc[-1]),
                change_1w=r1w,
                change_1m=r1m,
                change_3m=r3m,
                volume_ratio=vol_ratio,
                rsi_14=rsi,
            ))

        # Second pass: calc relative strength vs sector average
        avg_1m = np.mean(sector_returns_1m) if sector_returns_1m else 0.0
        for r in results:
            r.relative_strength = r.change_1m - avg_1m

        # Try to add fundamental data
        self._enrich_fundamentals(results)

        # Sort by relative strength
        results.sort(key=lambda x: x.relative_strength, reverse=True)
        return results

    def _enrich_fundamentals(self, results: list[PeerMetrics]):
        """嘗試補充基本面資料。"""
        try:
            from core.financial_reports import FinancialReportManager
            fm = FinancialReportManager()

            for r in results:
                try:
                    summary = fm.get_financial_summary(r.symbol)
                    if summary:
                        r.pe_ratio = summary.get("pe_ratio") or summary.get("本益比")
                        r.revenue_yoy = summary.get("revenue_yoy") or summary.get("月營收YoY")
                except Exception:
                    pass
        except ImportError:
            logger.debug("FinancialReportManager 不可用，跳過基本面補充")

    def to_dataframe(self, results: list[PeerMetrics]) -> pd.DataFrame:
        """轉為 DataFrame。"""
        data = []
        for r in results:
            row = {
                "股票": r.symbol,
                "名稱": r.name,
                "現價": f"{r.price:.2f}",
                "1W": f"{r.change_1w:.2%}",
                "1M": f"{r.change_1m:.2%}",
                "3M": f"{r.change_3m:.2%}",
                "量能比": f"{r.volume_ratio:.2f}x",
                "RSI": f"{r.rsi_14:.1f}",
                "相對強弱": f"{r.relative_strength:+.2%}",
            }
            if r.pe_ratio is not None:
                row["P/E"] = f"{r.pe_ratio:.1f}"
            if r.revenue_yoy is not None:
                row["營收YoY"] = f"{r.revenue_yoy:.1%}" if abs(r.revenue_yoy) < 10 else f"{r.revenue_yoy:.1f}%"
            data.append(row)
        return pd.DataFrame(data)


# ============================================================================
# 5. SectorNewsTracker — 產業新聞與政策追蹤
# ============================================================================
class SectorNewsTracker:
    """
    追蹤特定產業的新聞與政策動態。
    使用 Google News RSS（免費）。
    """

    # 每個產業對應的搜尋關鍵字（中文 + 英文）
    SECTOR_KEYWORDS = {
        "半導體": ["半導體", "晶圓代工", "IC設計", "台積電", "semiconductor", "foundry", "TSMC"],
        "電子代工_伺服器": ["伺服器", "AI server", "GPU", "鴻海", "廣達", "data center"],
        "電子零組件": ["PCB", "載板", "ABF", "被動元件", "連接器"],
        "金融": ["金控", "升息", "降息", "壽險", "銀行", "Taiwan financial"],
        "傳產_鋼鐵水泥": ["鋼鐵", "水泥", "航運", "塑化", "原物料", "BDI"],
        "生技醫療": ["生技", "新藥", "FDA", "biotech", "臨床試驗"],
        "綠能_電動車": ["電動車", "EV", "太陽能", "風電", "充電樁", "green energy"],
    }

    def __init__(self, sector_map: Optional[SectorMap] = None):
        self._sector_map = sector_map or SectorMap()

    def _fetch_google_news(self, query: str, max_results: int = 10) -> list[dict]:
        """從 Google News RSS 取得新聞。"""
        import urllib.request
        import urllib.parse
        import xml.etree.ElementTree as ET

        encoded_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                xml_data = resp.read()

            root = ET.fromstring(xml_data)
            items = root.findall(".//item")

            results = []
            for item in items[:max_results]:
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                pub_date = item.findtext("pubDate", "")
                source = item.findtext("source", "")

                results.append({
                    "title": title,
                    "url": link,
                    "published": pub_date,
                    "source": source,
                })

            return results

        except Exception as e:
            logger.warning(f"Google News 取得失敗 ({query}): {e}")
            return []

    def get_sector_news(self, sector_key: str, max_per_keyword: int = 5) -> list[dict]:
        """取得特定產業的新聞。"""
        keywords = self.SECTOR_KEYWORDS.get(sector_key, [])
        if not keywords:
            # Fallback: use sector name as keyword
            sector = self._sector_map.get_sector(sector_key)
            if sector:
                keywords = [sector.name]

        all_news = []
        seen_titles = set()

        for kw in keywords[:3]:  # limit to 3 keywords to avoid rate limiting
            news = self._fetch_google_news(kw, max_results=max_per_keyword)
            for item in news:
                title = item["title"]
                if title not in seen_titles:
                    seen_titles.add(title)
                    item["keyword"] = kw
                    item["sector"] = sector_key
                    all_news.append(item)

        return all_news

    def get_policy_news(self, keywords: Optional[list] = None) -> list[dict]:
        """取得政策面新聞。"""
        if keywords is None:
            keywords = [
                "台灣 產業政策",
                "經濟部 補助",
                "美國 關稅 科技",
                "AI regulation",
            ]

        all_news = []
        seen_titles = set()

        for kw in keywords:
            news = self._fetch_google_news(kw, max_results=5)
            for item in news:
                if item["title"] not in seen_titles:
                    seen_titles.add(item["title"])
                    item["keyword"] = kw
                    item["sector"] = "政策"
                    all_news.append(item)

        return all_news

    def scan_all_sectors(self, max_per_sector: int = 8) -> dict[str, list[dict]]:
        """掃描所有產業的新聞。"""
        results = {}
        for sector_key in self.SECTOR_KEYWORDS:
            news = self.get_sector_news(sector_key, max_per_keyword=3)
            results[sector_key] = news[:max_per_sector]
        return results


# ============================================================================
# 6. SectorAnalysisManager — 統一入口
# ============================================================================
class SectorAnalysisManager:
    """
    產業分析統一入口，lazy initialization 所有子模組。
    """

    def __init__(self):
        self._sector_map: Optional[SectorMap] = None
        self._rotation_tracker: Optional[SectorRotationTracker] = None
        self._supply_chain: Optional[SupplyChainAnalyzer] = None
        self._peer_comparison: Optional[PeerComparison] = None
        self._news_tracker: Optional[SectorNewsTracker] = None

    @property
    def sector_map(self) -> SectorMap:
        if self._sector_map is None:
            self._sector_map = SectorMap()
        return self._sector_map

    @property
    def rotation(self) -> SectorRotationTracker:
        if self._rotation_tracker is None:
            self._rotation_tracker = SectorRotationTracker(self.sector_map)
        return self._rotation_tracker

    @property
    def supply_chain(self) -> SupplyChainAnalyzer:
        if self._supply_chain is None:
            self._supply_chain = SupplyChainAnalyzer(self.sector_map)
        return self._supply_chain

    @property
    def peers(self) -> PeerComparison:
        if self._peer_comparison is None:
            self._peer_comparison = PeerComparison(self.sector_map)
        return self._peer_comparison

    @property
    def news(self) -> SectorNewsTracker:
        if self._news_tracker is None:
            self._news_tracker = SectorNewsTracker(self.sector_map)
        return self._news_tracker

    # --- Convenience methods ---

    def get_rotation_ranking(self) -> pd.DataFrame:
        """取得產業輪動排名 DataFrame。"""
        results = self.rotation.track_all_sectors()
        return self.rotation.to_dataframe(results)

    def get_chain_analysis(self, chain_key: str) -> dict:
        """取得供應鏈分析。"""
        return self.supply_chain.analyze_chain(chain_key)

    def get_peer_comparison(self, sector_key: str) -> pd.DataFrame:
        """取得同業比較 DataFrame。"""
        results = self.peers.compare_sector(sector_key)
        return self.peers.to_dataframe(results)

    def get_sector_news(self, sector_key: str) -> list[dict]:
        """取得產業新聞。"""
        return self.news.get_sector_news(sector_key)

    def get_sector_overview(self, sector_key: str) -> dict:
        """取得某產業的完整概覽（輪動 + 個股 + 新聞）。"""
        sector = self.sector_map.get_sector(sector_key)
        if not sector:
            return {"error": f"找不到產業: {sector_key}"}

        peer_results = self.peers.compare_sector(sector_key)
        news = self.news.get_sector_news(sector_key, max_per_keyword=3)

        return {
            "sector": sector,
            "peers": peer_results,
            "peers_df": self.peers.to_dataframe(peer_results),
            "news": news[:10],
            "news_count": len(news),
        }
