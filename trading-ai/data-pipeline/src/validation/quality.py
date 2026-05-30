"""Data quality checks."""
import numpy as np
import pandas as pd
from dataclasses import dataclass, field

@dataclass
class QualityReport:
    passed: bool
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)

def validate_ohlcv(df):
    r = QualityReport(passed=True)
    required=["ts","open","high","low","close"]
    missing=[c for c in required if c not in df.columns]
    if missing: r.errors.append(f"Missing: {missing}"); r.passed=False; return r
    nulls=df[required].isnull().sum()
    if nulls.any(): r.errors.append(f"Nulls: {nulls[nulls>0].to_dict()}"); r.passed=False
    if len(df[df["high"]<df["low"]]): r.errors.append("high < low rows"); r.passed=False
    if len(df[(df["open"]>df["high"])|(df["open"]<df["low"])]): r.errors.append("open outside range"); r.passed=False
    if len(df[(df["close"]>df["high"])|(df["close"]<df["low"])]): r.errors.append("close outside range"); r.passed=False
    outliers=df[(df["close"]<500)|(df["close"]>5000)]
    if len(outliers): r.warnings.append(f"{len(outliers)} prices outside [500,5000]")
    extreme=df["close"].pct_change().abs()[lambda x: x>0.05]
    if len(extreme): r.warnings.append(f"{len(extreme)} bars with >5% return")
    r.stats={"rows": len(df), "price_min": float(df["close"].min()), "price_max": float(df["close"].max())}
    return r

def validate_features(df):
    r = QualityReport(passed=True)
    feat_cols=[c for c in df.columns if c not in ["ts","label","tp_price","sl_price","bars_to_exit"]]
    null_pct=df[feat_cols].isnull().mean()
    high=null_pct[null_pct>0.10]
    if len(high): r.warnings.append(f">10% nulls: {high.to_dict()}")
    crit=null_pct[null_pct>0.30]
    if len(crit): r.errors.append(f">30% nulls: {crit.to_dict()}"); r.passed=False
    inf_cols=[c for c in feat_cols if np.isinf(df[c].replace([np.inf,-np.inf],np.nan)).any()]
    if inf_cols: r.errors.append(f"Inf values: {inf_cols}"); r.passed=False
    r.stats={"feature_count": len(feat_cols), "rows": len(df), "avg_null_pct": float(null_pct.mean())}
    return r
