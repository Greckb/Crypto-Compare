"""Feature engineering for XAU/USD ML model."""
import math
from datetime import timedelta
import numpy as np
import pandas as pd
import pandas_ta as ta

def _sin_cos(val, period):
    angle = 2 * math.pi * val / period
    return math.sin(angle), math.cos(angle)

def build_features(df_h4, df_macro, df_calendar, lookback=60):
    df = df_h4.copy().sort_values("ts").reset_index(drop=True)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    for lag in [1,3,6,12,24]:
        df[f"ret_{lag}"] = np.log(df["close"] / df["close"].shift(lag))
    df["atr_7"]  = ta.atr(df["high"], df["low"], df["close"], length=7)
    df["atr_14"] = ta.atr(df["high"], df["low"], df["close"], length=14)
    bb = ta.bbands(df["close"], length=20, std=2)
    df["bb_width"] = (bb["BBU_20_2.0"] - bb["BBL_20_2.0"]) / bb["BBM_20_2.0"]
    df["bb_pct_b"] = bb["BBP_20_2.0"]
    df["hl_range_norm"] = (df["high"] - df["low"]) / df["atr_14"].replace(0, np.nan)
    df["rsi_7"]  = ta.rsi(df["close"], length=7)
    df["rsi_14"] = ta.rsi(df["close"], length=14)
    macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
    df["macd_hist"] = macd["MACDh_12_26_9"]
    stoch = ta.stoch(df["high"], df["low"], df["close"], k=14, d=3)
    df["stoch_k"] = stoch["STOCHk_14_3_3"]; df["stoch_d"] = stoch["STOCHd_14_3_3"]
    adx = ta.adx(df["high"], df["low"], df["close"], length=14)
    df["adx_14"] = adx["ADX_14"]
    ema20 = ta.ema(df["close"], length=20); ema50 = ta.ema(df["close"], length=50); ema200 = ta.ema(df["close"], length=200)
    df["ema20_50_diff"] = (ema20 - ema50) / df["close"]
    df["ema200_dist"]   = (df["close"] - ema200) / df["close"]
    df["obv_slope_3"] = np.sign(df["ret_1"]).fillna(0).rolling(3).sum()
    candle_range = (df["high"] - df["low"]).replace(0, np.nan)
    body = (df["close"] - df["open"]).abs()
    df["body_ratio"]  = body / candle_range
    df["upper_wick"]  = (df["high"] - df[["open","close"]].max(axis=1)) / candle_range
    df["lower_wick"]  = (df[["open","close"]].min(axis=1) - df["low"]) / candle_range
    df["hour_sin"], df["hour_cos"] = zip(*df["ts"].apply(lambda t: _sin_cos(t.hour, 24)))
    df["dow_sin"],  df["dow_cos"]  = zip(*df["ts"].apply(lambda t: _sin_cos(t.dayofweek, 7)))
    df["day_of_month"] = df["ts"].dt.day
    df = _merge_macro(df, df_macro)
    df = _merge_calendar(df, df_calendar)
    df = df.iloc[200:].reset_index(drop=True)
    df = df.dropna(subset=["rsi_14", "atr_14", "macd_hist"])
    return df

def _merge_macro(df, df_macro):
    if df_macro.empty:
        for col in ["dxy_ret_5d","us10y_chg_5d","yield_curve","vix_level","vix_chg_5d","sp500_ret_5d"]:
            df[col] = np.nan
        return df
    df_macro = df_macro.copy()
    df_macro["ts"] = pd.to_datetime(df_macro["ts"], utc=True)
    def gs(sym): return df_macro[df_macro["symbol"]==sym].set_index("ts")["value"].sort_index()
    dxy=gs("DXY"); us10y=gs("US10Y"); us2y=gs("US2Y"); vix=gs("VIX"); sp500=gs("SP500")
    rows = []
    for ts in df["ts"]:
        d = ts.normalize()
        def ret_nd(s, n):
            try:
                loc = s.index.get_indexer([d], method="ffill")[0]
                if loc < n: return np.nan
                return math.log(s.iloc[loc]/s.iloc[loc-n]) if s.iloc[loc-n] and s.iloc[loc] else np.nan
            except: return np.nan
        def val(s):
            try:
                loc = s.index.get_indexer([d], method="ffill")[0]
                return float(s.iloc[loc]) if loc >= 0 else np.nan
            except: return np.nan
        rows.append({"dxy_ret_5d": ret_nd(dxy,5), "us10y_chg_5d": ret_nd(us10y,5),
                     "yield_curve": val(us10y)-val(us2y) if not np.isnan(val(us10y)) else np.nan,
                     "vix_level": val(vix), "vix_chg_5d": ret_nd(vix,5), "sp500_ret_5d": ret_nd(sp500,5)})
    return pd.concat([df, pd.DataFrame(rows, index=df.index)], axis=1)

def _merge_calendar(df, df_calendar):
    if df_calendar.empty:
        for col in ["nfp_in_24h","fomc_in_48h","cpi_in_24h","last_nfp_surprise","last_cpi_surprise"]:
            df[col] = False if "in_" in col else np.nan
        return df
    df_calendar = df_calendar.copy()
    df_calendar["event_ts"] = pd.to_datetime(df_calendar["event_ts"], utc=True)
    nfp  = df_calendar[df_calendar["event_name"].str.contains("Non Farm|NFP", case=False, na=False)]
    fomc = df_calendar[df_calendar["event_name"].str.contains("FOMC|Fed Rate", case=False, na=False)]
    cpi  = df_calendar[df_calendar["event_name"].str.contains("CPI", case=False, na=False)]
    def within(ev, ts, h): return bool(len(ev[(ev["event_ts"]>=ts)&(ev["event_ts"]<=(ts+timedelta(hours=h)))]))
    def last_surp(ev, ts):
        p = ev[ev["event_ts"]<ts].sort_values("event_ts")
        if p.empty: return np.nan
        v = p.iloc[-1].get("surprise", np.nan)
        return float(v) if pd.notna(v) else np.nan
    df["nfp_in_24h"]        = df["ts"].apply(lambda t: within(nfp, t, 24))
    df["fomc_in_48h"]       = df["ts"].apply(lambda t: within(fomc, t, 48))
    df["cpi_in_24h"]        = df["ts"].apply(lambda t: within(cpi, t, 24))
    df["last_nfp_surprise"] = df["ts"].apply(lambda t: last_surp(nfp, t))
    df["last_cpi_surprise"] = df["ts"].apply(lambda t: last_surp(cpi, t))
    return df
