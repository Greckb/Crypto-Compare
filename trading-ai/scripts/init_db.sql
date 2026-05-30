-- XAU/USD Trading AI Database Schema
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

CREATE TABLE ohlcv_h4 (
    id BIGSERIAL PRIMARY KEY, ts TIMESTAMPTZ NOT NULL,
    open NUMERIC(12,5) NOT NULL, high NUMERIC(12,5) NOT NULL,
    low NUMERIC(12,5) NOT NULL, close NUMERIC(12,5) NOT NULL,
    bid_open NUMERIC(12,5), bid_close NUMERIC(12,5),
    ask_open NUMERIC(12,5), ask_close NUMERIC(12,5),
    source VARCHAR(32) NOT NULL DEFAULT 'oanda',
    CONSTRAINT ohlcv_h4_ts_unique UNIQUE (ts)
);
CREATE TABLE ohlcv_h1 (
    id BIGSERIAL PRIMARY KEY, ts TIMESTAMPTZ NOT NULL,
    open NUMERIC(12,5) NOT NULL, high NUMERIC(12,5) NOT NULL,
    low NUMERIC(12,5) NOT NULL, close NUMERIC(12,5) NOT NULL,
    bid_open NUMERIC(12,5), bid_close NUMERIC(12,5),
    ask_open NUMERIC(12,5), ask_close NUMERIC(12,5),
    source VARCHAR(32) NOT NULL DEFAULT 'oanda',
    CONSTRAINT ohlcv_h1_ts_unique UNIQUE (ts)
);
CREATE INDEX idx_ohlcv_h4_ts ON ohlcv_h4 (ts DESC);
CREATE INDEX idx_ohlcv_h1_ts ON ohlcv_h1 (ts DESC);

CREATE TABLE macro_data (
    id BIGSERIAL PRIMARY KEY, ts TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(32) NOT NULL, value NUMERIC(18,6) NOT NULL, source VARCHAR(32) NOT NULL,
    CONSTRAINT macro_data_ts_symbol UNIQUE (ts, symbol)
);
CREATE INDEX idx_macro_data_symbol_ts ON macro_data (symbol, ts DESC);

CREATE TABLE economic_calendar (
    id BIGSERIAL PRIMARY KEY, event_ts TIMESTAMPTZ NOT NULL,
    event_name VARCHAR(128) NOT NULL, country VARCHAR(8) NOT NULL,
    impact VARCHAR(16) NOT NULL, actual NUMERIC(18,6), forecast NUMERIC(18,6),
    previous NUMERIC(18,6), surprise NUMERIC(18,6),
    source VARCHAR(32) NOT NULL DEFAULT 'finnhub',
    CONSTRAINT economic_calendar_ts_event UNIQUE (event_ts, event_name)
);
CREATE INDEX idx_calendar_ts ON economic_calendar (event_ts DESC);

CREATE TABLE features (
    id BIGSERIAL PRIMARY KEY, ts TIMESTAMPTZ NOT NULL UNIQUE,
    timeframe VARCHAR(8) NOT NULL DEFAULT 'H4',
    ret_1 NUMERIC(12,8), ret_3 NUMERIC(12,8), ret_6 NUMERIC(12,8),
    ret_12 NUMERIC(12,8), ret_24 NUMERIC(12,8),
    atr_7 NUMERIC(12,5), atr_14 NUMERIC(12,5),
    bb_width NUMERIC(12,8), bb_pct_b NUMERIC(12,8), hl_range_norm NUMERIC(12,8),
    rsi_7 NUMERIC(8,4), rsi_14 NUMERIC(8,4), macd_hist NUMERIC(12,8),
    stoch_k NUMERIC(8,4), stoch_d NUMERIC(8,4), adx_14 NUMERIC(8,4),
    ema20_50_diff NUMERIC(12,8), ema200_dist NUMERIC(12,8), obv_slope_3 NUMERIC(18,4),
    body_ratio NUMERIC(8,6), upper_wick NUMERIC(8,6), lower_wick NUMERIC(8,6),
    hour_sin NUMERIC(8,6), hour_cos NUMERIC(8,6), dow_sin NUMERIC(8,6), dow_cos NUMERIC(8,6),
    day_of_month SMALLINT,
    dxy_ret_5d NUMERIC(12,8), us10y_chg_5d NUMERIC(12,8), yield_curve NUMERIC(12,8),
    vix_level NUMERIC(8,4), vix_chg_5d NUMERIC(12,8), sp500_ret_5d NUMERIC(12,8),
    nfp_in_24h BOOLEAN DEFAULT FALSE, fomc_in_48h BOOLEAN DEFAULT FALSE, cpi_in_24h BOOLEAN DEFAULT FALSE,
    last_nfp_surprise NUMERIC(12,6), last_cpi_surprise NUMERIC(12,6),
    label SMALLINT, tp_price NUMERIC(12,5), sl_price NUMERIC(12,5), bars_to_exit SMALLINT,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_features_ts ON features (ts DESC);

CREATE TABLE model_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    version VARCHAR(32) NOT NULL UNIQUE, model_type VARCHAR(32) NOT NULL,
    ensemble_role VARCHAR(32) NOT NULL, train_start TIMESTAMPTZ NOT NULL, train_end TIMESTAMPTZ NOT NULL,
    val_accuracy NUMERIC(8,6), val_precision NUMERIC(8,6), val_recall NUMERIC(8,6),
    val_f1 NUMERIC(8,6), val_brier NUMERIC(8,6), sharpe_backtest NUMERIC(8,4),
    is_active BOOLEAN NOT NULL DEFAULT FALSE, artifact_path VARCHAR(256),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), ts TIMESTAMPTZ NOT NULL,
    model_version UUID REFERENCES model_versions(id),
    direction SMALLINT NOT NULL, confidence NUMERIC(6,4) NOT NULL, prob_tp NUMERIC(6,4) NOT NULL,
    entry_price NUMERIC(12,5) NOT NULL, tp_price NUMERIC(12,5) NOT NULL, sl_price NUMERIC(12,5) NOT NULL,
    atr_at_signal NUMERIC(12,5) NOT NULL, tp_atr_mult NUMERIC(6,3) NOT NULL DEFAULT 2.0,
    sl_atr_mult NUMERIC(6,3) NOT NULL DEFAULT 1.0, status VARCHAR(16) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_signals_ts ON signals (ts DESC);
CREATE INDEX idx_signals_status ON signals (status);

CREATE TABLE trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), signal_id UUID REFERENCES signals(id),
    mt4_ticket BIGINT UNIQUE, symbol VARCHAR(16) NOT NULL DEFAULT 'XAUUSD',
    direction SMALLINT NOT NULL, lots NUMERIC(8,4) NOT NULL,
    entry_price NUMERIC(12,5), tp_price NUMERIC(12,5), sl_price NUMERIC(12,5), exit_price NUMERIC(12,5),
    pnl_usd NUMERIC(12,4), pnl_pips NUMERIC(10,2), outcome VARCHAR(16),
    open_ts TIMESTAMPTZ, close_ts TIMESTAMPTZ, status VARCHAR(16) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_trades_status ON trades (status);
CREATE INDEX idx_trades_open_ts ON trades (open_ts DESC);

CREATE TABLE performance_metrics (
    id BIGSERIAL PRIMARY KEY, computed_at TIMESTAMPTZ NOT NULL, window VARCHAR(8) NOT NULL,
    total_trades INTEGER NOT NULL, win_rate NUMERIC(6,4), avg_pnl_usd NUMERIC(12,4),
    total_pnl_usd NUMERIC(12,4), max_drawdown NUMERIC(8,6), sharpe_ratio NUMERIC(8,4),
    profit_factor NUMERIC(8,4), avg_rr_ratio NUMERIC(8,4),
    CONSTRAINT perf_metrics_ts_window UNIQUE (computed_at, window)
);

CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY, ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    service VARCHAR(32) NOT NULL, action VARCHAR(64) NOT NULL,
    details JSONB, severity VARCHAR(8) NOT NULL DEFAULT 'info'
);
CREATE INDEX idx_audit_ts ON audit_log (ts DESC);
CREATE INDEX idx_audit_severity ON audit_log (severity, ts DESC);
