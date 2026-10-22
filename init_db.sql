-- init_db.sql
-- PostgreSQL initialization script for Quantitative Trading Tool
-- This script runs automatically when the container is first created

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create exchanges table
CREATE TABLE IF NOT EXISTS exchanges (
    id SERIAL PRIMARY KEY,
    code VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    name_zh VARCHAR(100),
    timezone VARCHAR(50) DEFAULT 'UTC',
    currency CHAR(3) NOT NULL,
    trading_hours VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default exchanges
INSERT INTO exchanges (code, name, name_zh, timezone, currency, trading_hours) VALUES
('TWSE', 'Taiwan Stock Exchange', 'Taiwan Stock Exchange', 'Asia/Taipei', 'TWD', '09:00-13:30'),
('TPEx', 'Taipei Exchange', 'Taipei Exchange', 'Asia/Taipei', 'TWD', '09:00-13:30'),
('NYSE', 'New York Stock Exchange', 'New York Stock Exchange', 'America/New_York', 'USD', '09:30-16:00'),
('NASDAQ', 'NASDAQ', 'NASDAQ', 'America/New_York', 'USD', '09:30-16:00')
ON CONFLICT (code) DO NOTHING;

-- Create securities table
CREATE TABLE IF NOT EXISTS securities (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    exchange_id INTEGER REFERENCES exchanges(id),
    name VARCHAR(200),
    name_zh VARCHAR(200),
    sector VARCHAR(100),
    industry VARCHAR(100),
    asset_type VARCHAR(20) DEFAULT 'stock',
    market_cap DECIMAL(20, 2),
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, exchange_id)
);

-- Create indexes for securities
CREATE INDEX IF NOT EXISTS idx_securities_symbol ON securities(symbol);
CREATE INDEX IF NOT EXISTS idx_securities_asset_type ON securities(asset_type);

-- Create prices table (partitioned by date)
CREATE TABLE IF NOT EXISTS prices (
    id BIGSERIAL,
    security_id INTEGER NOT NULL REFERENCES securities(id),
    date DATE NOT NULL,
    timeframe VARCHAR(10) DEFAULT '1D',
    open DECIMAL(18, 6),
    high DECIMAL(18, 6),
    low DECIMAL(18, 6),
    close DECIMAL(18, 6),
    adj_close DECIMAL(18, 6),
    volume BIGINT,
    turnover DECIMAL(20, 2),
    data_source VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, date)
) PARTITION BY RANGE (date);

-- Create partitions for years 2020-2030
DO $$
BEGIN
    FOR year IN 2020..2030 LOOP
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS prices_%s
            PARTITION OF prices
            FOR VALUES FROM (%L) TO (%L)',
            year,
            year || '-01-01',
            (year + 1) || '-01-01'
        );
    END LOOP;
END $$;

-- Create indexes for prices
CREATE INDEX IF NOT EXISTS idx_prices_security_date ON prices(security_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date DESC);

-- Create trades table
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    security_id INTEGER NOT NULL REFERENCES securities(id),
    strategy_name VARCHAR(100),
    trade_type VARCHAR(10) NOT NULL CHECK (trade_type IN ('BUY', 'SELL', 'SHORT', 'COVER')),
    quantity DECIMAL(18, 6) NOT NULL,
    order_price DECIMAL(18, 6),
    fill_price DECIMAL(18, 6),
    commission DECIMAL(18, 6) DEFAULT 0,
    tax DECIMAL(18, 6) DEFAULT 0,
    slippage DECIMAL(18, 6) DEFAULT 0,
    order_time TIMESTAMP,
    fill_time TIMESTAMP,
    status VARCHAR(20) DEFAULT 'FILLED' CHECK (status IN ('PENDING', 'PARTIAL', 'FILLED', 'CANCELLED', 'REJECTED')),
    notes TEXT,
    backtest_id INTEGER,
    is_paper_trade BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for trades
CREATE INDEX IF NOT EXISTS idx_trades_security ON trades(security_id);
CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy_name);
CREATE INDEX IF NOT EXISTS idx_trades_backtest ON trades(backtest_id);
CREATE INDEX IF NOT EXISTS idx_trades_fill_time ON trades(fill_time DESC);

-- Create positions table
CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    security_id INTEGER NOT NULL REFERENCES securities(id) UNIQUE,
    quantity DECIMAL(18, 6) NOT NULL,
    avg_cost DECIMAL(18, 6) NOT NULL,
    market_price DECIMAL(18, 6),
    market_value DECIMAL(18, 6),
    unrealized_pnl DECIMAL(18, 6),
    unrealized_pnl_pct DECIMAL(10, 6),
    realized_pnl DECIMAL(18, 6) DEFAULT 0,
    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create trigger for positions update
CREATE OR REPLACE FUNCTION update_position_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_position_update ON positions;
CREATE TRIGGER trg_position_update
    BEFORE UPDATE ON positions
    FOR EACH ROW
    EXECUTE FUNCTION update_position_timestamp();

-- Create backtest_runs table
CREATE TABLE IF NOT EXISTS backtest_runs (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    strategy_name VARCHAR(100) NOT NULL,
    strategy_class VARCHAR(100),
    parameters JSONB,
    symbols JSONB,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_capital DECIMAL(18, 2),
    final_value DECIMAL(18, 2),
    total_return DECIMAL(10, 6),
    cagr DECIMAL(10, 6),
    sharpe_ratio DECIMAL(10, 6),
    sortino_ratio DECIMAL(10, 6),
    calmar_ratio DECIMAL(10, 6),
    max_drawdown DECIMAL(10, 6),
    avg_drawdown DECIMAL(10, 6),
    total_trades INTEGER,
    winning_trades INTEGER,
    losing_trades INTEGER,
    win_rate DECIMAL(10, 6),
    profit_factor DECIMAL(10, 6),
    avg_trade_return DECIMAL(10, 6),
    avg_win DECIMAL(10, 6),
    avg_loss DECIMAL(10, 6),
    max_consecutive_wins INTEGER,
    max_consecutive_losses INTEGER,
    volatility DECIMAL(10, 6),
    var_95 DECIMAL(10, 6),
    cvar_95 DECIMAL(10, 6),
    execution_time_ms INTEGER,
    notes TEXT,
    tags JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for backtest_runs
CREATE INDEX IF NOT EXISTS idx_backtest_strategy ON backtest_runs(strategy_name);
CREATE INDEX IF NOT EXISTS idx_backtest_created ON backtest_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_backtest_sharpe ON backtest_runs(sharpe_ratio DESC);

-- Create equity_curves table
CREATE TABLE IF NOT EXISTS equity_curves (
    id SERIAL PRIMARY KEY,
    backtest_id INTEGER NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    equity DECIMAL(18, 6),
    cash DECIMAL(18, 6),
    drawdown DECIMAL(10, 6),
    drawdown_pct DECIMAL(10, 6),
    daily_return DECIMAL(10, 6),
    cumulative_return DECIMAL(10, 6),
    UNIQUE(backtest_id, date)
);

-- Create index for equity_curves
CREATE INDEX IF NOT EXISTS idx_equity_backtest_date ON equity_curves(backtest_id, date);

-- Create optimization_results table
CREATE TABLE IF NOT EXISTS optimization_results (
    id SERIAL PRIMARY KEY,
    method VARCHAR(50) NOT NULL,
    symbols JSONB NOT NULL,
    weights JSONB NOT NULL,
    expected_return DECIMAL(10, 6),
    expected_volatility DECIMAL(10, 6),
    sharpe_ratio DECIMAL(10, 6),
    constraints JSONB,
    risk_free_rate DECIMAL(10, 6),
    views JSONB,
    market_caps JSONB,
    total_investment DECIMAL(18, 2),
    discrete_allocation JSONB,
    leftover_cash DECIMAL(18, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

-- Create indexes for optimization_results
CREATE INDEX IF NOT EXISTS idx_optimization_method ON optimization_results(method);
CREATE INDEX IF NOT EXISTS idx_optimization_created ON optimization_results(created_at DESC);

-- Create watchlists table
CREATE TABLE IF NOT EXISTS watchlists (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    symbols JSONB,
    is_default BOOLEAN DEFAULT FALSE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create data_sync_status table
CREATE TABLE IF NOT EXISTS data_sync_status (
    id SERIAL PRIMARY KEY,
    security_id INTEGER REFERENCES securities(id),
    data_type VARCHAR(50) NOT NULL,
    last_sync_date DATE,
    last_sync_time TIMESTAMP,
    status VARCHAR(20) DEFAULT 'SUCCESS',
    error_message TEXT,
    records_synced INTEGER DEFAULT 0,
    UNIQUE(security_id, data_type)
);

-- Create views for convenient queries

-- Portfolio summary view
CREATE OR REPLACE VIEW v_portfolio_summary AS
SELECT
    s.symbol,
    s.name,
    s.name_zh,
    e.currency,
    p.quantity,
    p.avg_cost,
    p.market_price,
    p.market_value,
    p.unrealized_pnl,
    p.unrealized_pnl_pct,
    p.realized_pnl,
    p.last_updated
FROM positions p
JOIN securities s ON p.security_id = s.id
JOIN exchanges e ON s.exchange_id = e.id
WHERE p.quantity != 0;

-- Backtest ranking view
CREATE OR REPLACE VIEW v_backtest_ranking AS
SELECT
    id,
    strategy_name,
    symbols,
    start_date,
    end_date,
    total_return,
    sharpe_ratio,
    sortino_ratio,
    max_drawdown,
    win_rate,
    total_trades,
    created_at
FROM backtest_runs
WHERE sharpe_ratio IS NOT NULL
ORDER BY sharpe_ratio DESC;

-- Grant permissions (adjust as needed)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO quant_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO quant_user;

COMMENT ON TABLE exchanges IS 'Exchange reference data';
COMMENT ON TABLE securities IS 'Securities master data';
COMMENT ON TABLE prices IS 'Historical OHLCV price data (partitioned by year)';
COMMENT ON TABLE trades IS 'Trade execution records';
COMMENT ON TABLE positions IS 'Current portfolio positions';
COMMENT ON TABLE backtest_runs IS 'Backtest execution results';
COMMENT ON TABLE equity_curves IS 'Backtest equity curves';
COMMENT ON TABLE optimization_results IS 'Portfolio optimization results';
COMMENT ON TABLE watchlists IS 'User watchlists';
COMMENT ON TABLE data_sync_status IS 'Data synchronization status tracking';
