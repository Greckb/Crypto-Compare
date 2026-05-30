"""PostgreSQL persistence layer."""
import os
from contextlib import contextmanager
import psycopg2
import psycopg2.extras
import structlog

log = structlog.get_logger()

@contextmanager
def get_conn():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def upsert_ohlcv(candles, table):
    if not candles: return 0
    sql = f"INSERT INTO {table} (ts,open,high,low,close,bid_open,bid_close,ask_open,ask_close,source) VALUES %s ON CONFLICT (ts) DO NOTHING"
    rows = [(c["ts"],c["open"],c["high"],c["low"],c["close"],c.get("bid_open"),c.get("bid_close"),c.get("ask_open"),c.get("ask_close"),c.get("source","oanda")) for c in candles]
    with get_conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, sql, rows)
            return cur.rowcount

def upsert_macro(rows):
    if not rows: return 0
    sql = "INSERT INTO macro_data (ts,symbol,value,source) VALUES %s ON CONFLICT (ts,symbol) DO UPDATE SET value=EXCLUDED.value"
    with get_conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, sql, [(r["ts"],r["symbol"],r["value"],r["source"]) for r in rows])
            return cur.rowcount

def upsert_calendar(events):
    if not events: return 0
    sql = "INSERT INTO economic_calendar (event_ts,event_name,country,impact,actual,forecast,previous,surprise,source) VALUES %s ON CONFLICT (event_ts,event_name) DO UPDATE SET actual=EXCLUDED.actual,forecast=EXCLUDED.forecast,surprise=EXCLUDED.surprise"
    with get_conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, sql, [(e["event_ts"],e["event_name"],e["country"],e["impact"],e.get("actual"),e.get("forecast"),e.get("previous"),e.get("surprise"),e.get("source","finnhub")) for e in events])
            return cur.rowcount

def get_latest_ts(table):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT MAX(ts) FROM {table}")
            row = cur.fetchone()
            return row[0] if row else None

def audit(service, action, details=None, severity="info"):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO audit_log (service,action,details,severity) VALUES (%s,%s,%s,%s)",
                       (service, action, psycopg2.extras.Json(details or {}), severity))
