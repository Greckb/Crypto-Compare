"""Signal generator — runs after each H4 bar close."""
import os, uuid, json
from datetime import datetime, timezone
import joblib, numpy as np, redis, psycopg2, psycopg2.extras, pandas as pd, structlog
from models.lgbm_model import FEATURE_COLS
log=structlog.get_logger()
CONFIDENCE_THRESHOLD=0.62

def _redis(): return redis.from_url(os.environ["REDIS_URL"], decode_responses=True)

def _load_model():
    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id,artifact_path FROM model_versions WHERE is_active=TRUE AND ensemble_role='direction' ORDER BY created_at DESC LIMIT 1")
            row=cur.fetchone()
    if not row: raise RuntimeError("No active model")
    return joblib.load(row["artifact_path"]), str(row["id"])

def _latest_features():
    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"SELECT {','.join(FEATURE_COLS+['ts','atr_14'])} FROM features ORDER BY ts DESC LIMIT 1")
            row=cur.fetchone()
    if not row: raise RuntimeError("No features")
    return dict(row)

def _has_open_trade():
    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM trades WHERE status IN ('pending','open')")
            return cur.fetchone()[0]>0

def generate_signal():
    try:
        if _has_open_trade(): log.info("signal.skipped",reason="open_trade"); return None
        model,model_id=_load_model()
        feat=_latest_features()
        X=pd.DataFrame([{c:feat.get(c) for c in FEATURE_COLS}])
        if X.isnull().sum().sum()>5: log.warning("signal.skipped",reason="null_features"); return None
        X=X.fillna(0)
        prob=float(model.predict_proba(X)[0])
        if prob>=CONFIDENCE_THRESHOLD: direction,conf=1,prob
        elif (1-prob)>=CONFIDENCE_THRESHOLD: direction,conf=-1,1-prob
        else: log.info("signal.skipped",reason="below_threshold",prob=round(prob,4)); return None
        atr=float(feat.get("atr_14",0))
        if atr==0: return None
        from ingestion.oanda_client import OandaClient
        px=OandaClient().get_current_price()
        entry=px["ask"] if direction==1 else px["bid"]
        tp=entry+direction*2.0*atr; sl=entry-direction*1.0*atr
        sid=str(uuid.uuid4()); ts=datetime.now(timezone.utc)
        signal={"id":sid,"ts":ts.isoformat(),"model_version":model_id,"direction":direction,
                "confidence":round(conf,4),"prob_tp":round(prob,4),"entry_price":round(entry,5),
                "tp_price":round(tp,5),"sl_price":round(sl,5),"atr_at_signal":round(atr,5)}
        with psycopg2.connect(os.environ["DATABASE_URL"]) as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO signals (id,ts,model_version,direction,confidence,prob_tp,entry_price,tp_price,sl_price,atr_at_signal,tp_atr_mult,sl_atr_mult,status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,2.0,1.0,'pending')",
                           (sid,ts,model_id,direction,conf,prob,entry,tp,sl,atr))
            conn.commit()
        r=_redis(); r.setex("latest_signal",3600*5,json.dumps(signal)); r.lpush("signal_history",json.dumps(signal)); r.ltrim("signal_history",0,199)
        log.info("signal.generated",direction=direction,confidence=round(conf,4))
        return signal
    except Exception as e:
        log.error("signal.error",error=str(e)); return None
