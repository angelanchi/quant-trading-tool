# -*- coding: utf-8 -*-
"""
輕量級本地儲存 (Local Storage) — 使用 SQLite

不需要 PostgreSQL，資料存在本地 data/local.db 檔案中。
用於交易紀錄、警報設定等需要持久化的資料。
"""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

# 資料庫檔案路徑
DB_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DB_DIR / "local.db"


def get_connection() -> sqlite3.Connection:
    """取得 SQLite 連線，自動建立目錄和資料表。"""
    DB_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _init_tables(conn)
    return conn


def _init_tables(conn: sqlite3.Connection):
    """初始化資料表。"""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            trade_type TEXT NOT NULL,
            shares REAL NOT NULL,
            price REAL NOT NULL,
            trade_date TEXT NOT NULL,
            notes TEXT DEFAULT '',
            pnl REAL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS alerts_config (
            id TEXT PRIMARY KEY,
            config_json TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
        CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(trade_date);
    """)
    conn.commit()


# === 交易紀錄 CRUD ===

def save_trade(symbol: str, trade_type: str, shares: float, price: float,
               trade_date: str, notes: str = "", pnl: float = None) -> int:
    """儲存交易紀錄，回傳 trade ID。"""
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO trades (symbol, trade_type, shares, price, trade_date, notes, pnl) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (symbol, trade_type, shares, price, trade_date, notes, pnl)
    )
    conn.commit()
    trade_id = cursor.lastrowid
    conn.close()
    logger.info(f"已儲存交易: {symbol} {trade_type} {shares}股 @ {price}")
    return trade_id


def get_all_trades() -> List[Dict]:
    """取得所有交易紀錄。"""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM trades ORDER BY trade_date DESC, id DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_trades_by_symbol(symbol: str) -> List[Dict]:
    """依股票代碼查詢交易紀錄。"""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM trades WHERE symbol = ? ORDER BY trade_date DESC", (symbol,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_trade(trade_id: int) -> bool:
    """刪除交易紀錄。"""
    conn = get_connection()
    conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
    conn.commit()
    conn.close()
    return True


def get_trade_statistics() -> Dict:
    """計算交易統計。"""
    trades = get_all_trades()
    if not trades:
        return {"total_trades": 0, "symbols": [], "total_pnl": 0}

    closed = [t for t in trades if t.get("pnl") is not None]
    wins = [t for t in closed if t["pnl"] > 0]
    losses = [t for t in closed if t["pnl"] < 0]

    return {
        "total_trades": len(trades),
        "symbols": list(set(t["symbol"] for t in trades)),
        "total_pnl": sum(t.get("pnl", 0) or 0 for t in trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate": len(wins) / len(closed) * 100 if closed else 0,
    }


# === 警報設定持久化 ===

def save_alerts_config(alerts_json: str):
    """儲存警報設定。"""
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO alerts_config (id, config_json) VALUES (?, ?)",
        ("current", alerts_json)
    )
    conn.commit()
    conn.close()


def load_alerts_config() -> Optional[str]:
    """載入警報設定。"""
    conn = get_connection()
    row = conn.execute("SELECT config_json FROM alerts_config WHERE id = 'current'").fetchone()
    conn.close()
    return row["config_json"] if row else None
