"""LightGBM model with Purged Walk-Forward CV."""
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, brier_score_loss, roc_auc_score
from dataclasses import dataclass, field
from typing import Optional

FEATURE_COLS = ["ret_1","ret_3","ret_6","ret_12","ret_24","atr_7","atr_14","bb_width","bb_pct_b","hl_range_norm","rsi_7","rsi_14","macd_hist","stoch_k","stoch_d","adx_14","ema20_50_diff","ema200_dist","obv_slope_3","body_ratio","upper_wick","lower_wick","hour_sin","hour_cos","dow_sin","dow_cos","day_of_month","dxy_ret_5d","us10y_chg_5d","yield_curve","vix_level","vix_chg_5d","sp500_ret_5d","nfp_in_24h","fomc_in_48h","cpi_in_24h","last_nfp_surprise","last_cpi_surprise"]

LGBM_PARAMS = {"objective":"binary","metric":["binary_logloss","auc"],"verbosity":-1,"boosting_type":"gbdt","num_leaves":31,"max_depth":6,"learning_rate":0.05,"n_estimators":500,"min_child_samples":50,"subsample":0.8,"colsample_bytree":0.7,"reg_alpha":0.1,"reg_lambda":0.1,"random_state":42,"n_jobs":-1}

@dataclass
class WalkForwardResult:
    fold_metrics: list = field(default_factory=list)
    mean_accuracy: float=0.0; mean_precision: float=0.0; mean_recall: float=0.0
    mean_f1: float=0.0; mean_auc: float=0.0; mean_brier: float=0.0
    is_viable: bool=False

class TradingLGBM:
    def __init__(self, params=None):
        self._params=params or LGBM_PARAMS.copy(); self._model=None; self._feature_importances=None
    def fit(self, X_train, y_train):
        self._model=lgb.LGBMClassifier(**self._params)
        self._model.fit(X_train, y_train, callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)])
        self._feature_importances=pd.Series(self._model.feature_importances_, index=X_train.columns).sort_values(ascending=False)
        return self
    def predict_proba(self, X): return self._model.predict_proba(X)[:,1]
    def predict(self, X, threshold=0.5): return (self.predict_proba(X)>=threshold).astype(int)
    @property
    def feature_importances(self): return self._feature_importances

def walk_forward_cv(df, n_folds=5, train_pct=0.70, purge_bars=10, embargo_bars=5):
    df=df.dropna(subset=FEATURE_COLS+["label"]).reset_index(drop=True)
    n=len(df); fold_size=n//n_folds; result=WalkForwardResult()
    for fold in range(n_folds):
        fs=fold*fold_size; fe=fs+fold_size if fold<n_folds-1 else n
        sp=fs+int((fe-fs)*train_pct)
        te=max(0,sp-purge_bars); vs=min(n,sp+embargo_bars)
        if te-fs<100 or fe-vs<20: continue
        Xtr=df.iloc[fs:te][FEATURE_COLS]; ytr=df.iloc[fs:te]["label"]
        Xv=df.iloc[vs:fe][FEATURE_COLS]; yv=df.iloc[vs:fe]["label"]
        m=TradingLGBM(); m.fit(Xtr,ytr)
        probs=m.predict_proba(Xv); preds=(probs>=0.5).astype(int)
        result.fold_metrics.append({"fold":fold,"train_n":len(Xtr),"val_n":len(Xv),
            "accuracy":float(accuracy_score(yv,preds)),"precision":float(precision_score(yv,preds,zero_division=0)),
            "recall":float(recall_score(yv,preds,zero_division=0)),"f1":float(f1_score(yv,preds,zero_division=0)),
            "auc":float(roc_auc_score(yv,probs)) if len(yv.unique())>1 else 0.5,
            "brier":float(brier_score_loss(yv,probs))})
    if result.fold_metrics:
        for k in ["accuracy","precision","recall","f1","auc","brier"]:
            setattr(result, f"mean_{k}", float(np.mean([m[k] for m in result.fold_metrics])))
        acc=[m["accuracy"] for m in result.fold_metrics]
        result.is_viable = result.mean_accuracy>0.52 and np.std(acc)<0.05
    return result

def train_final_model(df):
    df=df.dropna(subset=FEATURE_COLS+["label"])
    m=TradingLGBM(); m.fit(df[FEATURE_COLS], df["label"]); return m
