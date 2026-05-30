"""Weekly model training pipeline with SHAP interpretability."""
import os, uuid, joblib
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd, shap, structlog
from prometheus_client import Gauge
from models.lgbm_model import FEATURE_COLS, walk_forward_cv, train_final_model
log=structlog.get_logger()
MODEL_DIR=Path(os.environ.get("MODEL_DIR","/app/models")); MODEL_DIR.mkdir(parents=True, exist_ok=True)
g_acc=Gauge("trading_model_val_accuracy","Walk-forward OOS accuracy")
g_auc=Gauge("trading_model_val_auc","Walk-forward OOS AUC")
g_viable=Gauge("trading_model_viable","1 if model passed viability")

def load_features_from_db():
    import psycopg2
    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn:
        return pd.read_sql(f"SELECT ts,{','.join(FEATURE_COLS)},label FROM features WHERE label IS NOT NULL ORDER BY ts ASC", conn)

def run_training():
    log.info("trainer.start")
    df=load_features_from_db()
    if len(df)<500: log.warning("trainer.insufficient", rows=len(df)); return {"status":"skipped"}
    wf=walk_forward_cv(df)
    g_acc.set(wf.mean_accuracy); g_auc.set(wf.mean_auc); g_viable.set(1 if wf.is_viable else 0)
    log.info("trainer.wf", accuracy=round(wf.mean_accuracy,4), auc=round(wf.mean_auc,4), viable=wf.is_viable)
    if not wf.is_viable:
        log.warning("trainer.not_viable", accuracy=wf.mean_accuracy)
        return {"status":"not_viable","accuracy":wf.mean_accuracy}
    model=train_final_model(df)
    X_s=df[FEATURE_COLS].dropna().head(500)
    expl=shap.TreeExplainer(model._model); sv=expl.shap_values(X_s)
    if isinstance(sv,list): sv=sv[1]
    shap_imp=pd.Series(np.abs(sv).mean(axis=0),index=FEATURE_COLS).sort_values(ascending=False)
    log.info("trainer.shap_top10", features=shap_imp.head(10).to_dict())
    version=f"v{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}"
    path=MODEL_DIR/f"lgbm_direction_{version}.joblib"; joblib.dump(model, path)
    mid=_register_model(version, df["ts"].min(), df["ts"].max(), wf, str(path))
    log.info("trainer.done", version=version)
    return {"status":"success","version":version,"model_id":str(mid),
            "metrics":{"accuracy":wf.mean_accuracy,"auc":wf.mean_auc},"shap_top5":shap_imp.head(5).to_dict()}

def _register_model(version, train_start, train_end, wf, artifact_path):
    import psycopg2
    mid=uuid.uuid4()
    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE model_versions SET is_active=FALSE WHERE ensemble_role='direction'")
            cur.execute("INSERT INTO model_versions (id,version,model_type,ensemble_role,train_start,train_end,val_accuracy,val_precision,val_recall,val_f1,val_brier,is_active,artifact_path) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE,%s)",
                       (str(mid),version,"lgbm_classifier","direction",train_start,train_end,wf.mean_accuracy,wf.mean_precision,wf.mean_recall,wf.mean_f1,wf.mean_brier,artifact_path))
        conn.commit()
    return mid
