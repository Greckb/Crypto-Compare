"""Pipeline orchestrator — H4 schedule + daily macro/calendar refresh."""
import os, schedule, time
from datetime import datetime, timedelta, timezone
import structlog
from dotenv import load_dotenv
from ingestion.oanda_client import OandaClient
from ingestion.macro_client import MacroClient
from ingestion.calendar_client import CalendarClient
from ingestion import db
from features.engineer import build_features
from features.labeler import label_triple_barrier, check_label_balance
from validation.quality import validate_ohlcv, validate_features
load_dotenv()
log = structlog.get_logger()
H4_HOURS = [0,4,8,12,16,20]

def run_ohlcv_ingestion():
    log.info("pipeline.ohlcv.start")
    try:
        client = OandaClient()
        for table, gran in [("ohlcv_h4","H4"),("ohlcv_h1","H1")]:
            latest = db.get_latest_ts(table)
            from_ts = (latest+timedelta(seconds=1)) if latest else (datetime.now(timezone.utc)-timedelta(days=365*5))
            to_ts = datetime.now(timezone.utc)
            if from_ts >= to_ts: continue
            candles = client.fetch_candles(gran, from_ts, to_ts)
            n = db.upsert_ohlcv(candles, table)
            log.info("pipeline.ohlcv.inserted", table=table, count=n)
            db.audit("pipeline", f"ohlcv_{gran}", {"count": n})
    except Exception as e:
        log.error("pipeline.ohlcv.error", error=str(e))
        db.audit("pipeline", "ohlcv_error", {"error": str(e)}, severity="error")

def run_macro_ingestion():
    log.info("pipeline.macro.start")
    try:
        rows = MacroClient().fetch_all(datetime.now(timezone.utc)-timedelta(days=30), datetime.now(timezone.utc))
        n = db.upsert_macro(rows)
        log.info("pipeline.macro.inserted", count=n)
        db.audit("pipeline", "macro_ingestion", {"count": n})
    except Exception as e:
        log.error("pipeline.macro.error", error=str(e))

def run_calendar_ingestion():
    log.info("pipeline.calendar.start")
    try:
        today = datetime.now(timezone.utc).date()
        events = CalendarClient().fetch_events((today-timedelta(days=14)).isoformat(), (today+timedelta(days=28)).isoformat())
        n = db.upsert_calendar(events)
        log.info("pipeline.calendar.inserted", count=n)
        db.audit("pipeline", "calendar_ingestion", {"count": n})
    except Exception as e:
        log.error("pipeline.calendar.error", error=str(e))

def run_feature_computation():
    log.info("pipeline.features.start")
    import psycopg2, pandas as pd, psycopg2.extras, numpy as np
    from ingestion.db import get_conn
    try:
        with get_conn() as conn:
            df_h4 = pd.read_sql("SELECT ts,open,high,low,close FROM ohlcv_h4 ORDER BY ts ASC", conn)
            df_macro = pd.read_sql("SELECT ts,symbol,value FROM macro_data ORDER BY ts ASC", conn)
            df_cal = pd.read_sql("SELECT event_ts,event_name,impact,surprise FROM economic_calendar ORDER BY event_ts ASC", conn)
        if len(df_h4) < 210: log.warning("pipeline.features.insufficient", rows=len(df_h4)); return
        qr = validate_ohlcv(df_h4)
        if not qr.passed: log.error("pipeline.features.validation_failed", errors=qr.errors); return
        df = build_features(df_h4, df_macro, df_cal)
        df = label_triple_barrier(df, tp_atr_mult=2.0, sl_atr_mult=1.0, max_bars=30)
        balance = check_label_balance(df)
        log.info("pipeline.features.balance", **balance)
        qr2 = validate_features(df)
        if not qr2.passed: log.error("pipeline.features.feat_validation_failed", errors=qr2.errors); return
        _upsert_features(df)
        log.info("pipeline.features.done", rows=len(df))
        db.audit("pipeline", "feature_computation", {"rows": len(df), **balance})
    except Exception as e:
        log.error("pipeline.features.error", error=str(e))
        db.audit("pipeline", "feature_error", {"error": str(e)}, severity="error")

def _upsert_features(df):
    import psycopg2.extras, numpy as np
    from ingestion.db import get_conn
    cols=["ts","ret_1","ret_3","ret_6","ret_12","ret_24","atr_7","atr_14","bb_width","bb_pct_b","hl_range_norm","rsi_7","rsi_14","macd_hist","stoch_k","stoch_d","adx_14","ema20_50_diff","ema200_dist","obv_slope_3","body_ratio","upper_wick","lower_wick","hour_sin","hour_cos","dow_sin","dow_cos","day_of_month","dxy_ret_5d","us10y_chg_5d","yield_curve","vix_level","vix_chg_5d","sp500_ret_5d","nfp_in_24h","fomc_in_48h","cpi_in_24h","last_nfp_surprise","last_cpi_surprise"]
    c=[x for x in cols if x in df.columns]
    sql=f"INSERT INTO features ({','.join(c)}) VALUES %s ON CONFLICT (ts) DO UPDATE SET {', '.join(f'{x}=EXCLUDED.{x}' for x in c if x!='ts')}"
    def clean(v): return None if (v is None or (isinstance(v,float) and (np.isnan(v) or np.isinf(v)))) else v
    rows=[tuple(clean(row[x]) for x in c) for _,row in df[c].iterrows()]
    with get_conn() as conn:
        with conn.cursor() as cur: psycopg2.extras.execute_values(cur, sql, rows)

def run_full_pipeline():
    run_ohlcv_ingestion(); run_macro_ingestion(); run_calendar_ingestion(); run_feature_computation()

def main():
    log.info("pipeline.start")
    run_full_pipeline()
    for h in H4_HOURS:
        schedule.every().day.at(f"{h:02d}:05").do(run_ohlcv_ingestion)
        schedule.every().day.at(f"{h:02d}:06").do(run_feature_computation)
    schedule.every().day.at("02:00").do(run_macro_ingestion)
    schedule.every().day.at("02:10").do(run_calendar_ingestion)
    while True: schedule.run_pending(); time.sleep(30)

if __name__ == "__main__": main()
