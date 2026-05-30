"""Triple-Barrier labeling (Lopez de Prado, 2018)."""
import numpy as np
import pandas as pd

def label_triple_barrier(df, tp_atr_mult=2.0, sl_atr_mult=1.0, max_bars=30, atr_col="atr_14"):
    df = df.copy().reset_index(drop=True)
    closes=df["close"].values; highs=df["high"].values; lows=df["low"].values; atrs=df[atr_col].values
    labels=np.full(len(df),np.nan); tp_prices=np.full(len(df),np.nan)
    sl_prices=np.full(len(df),np.nan); bars_to_exit=np.full(len(df),np.nan)
    for i in range(len(df)-1):
        atr=atrs[i]
        if np.isnan(atr) or atr==0: continue
        entry=closes[i]; tp=entry+tp_atr_mult*atr; sl=entry-sl_atr_mult*atr
        outcome=np.nan
        for j in range(i+1, min(i+1+max_bars, len(df))):
            if lows[j]<=sl: outcome=0.0; bars_to_exit[i]=j-i; break
            if highs[j]>=tp: outcome=1.0; bars_to_exit[i]=j-i; break
        labels[i]=outcome; tp_prices[i]=tp; sl_prices[i]=sl
    df["label"]=labels; df["tp_price"]=tp_prices; df["sl_price"]=sl_prices; df["bars_to_exit"]=bars_to_exit
    df=df.dropna(subset=["label"]).reset_index(drop=True)
    df["label"]=df["label"].astype(int)
    return df

def check_label_balance(df):
    counts=df["label"].value_counts(normalize=True)
    tp_rate=float(counts.get(1,0)); sl_rate=float(counts.get(0,0))
    return {"total": len(df), "tp_rate": round(tp_rate,4), "sl_rate": round(sl_rate,4), "imbalanced": min(tp_rate,sl_rate)<0.35}
