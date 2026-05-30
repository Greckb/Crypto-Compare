"""Macro data: DXY, VIX, US yields, SP500 via Yahoo Finance."""
import os
from datetime import datetime, timezone
import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

MACRO_SYMBOLS = {"DXY": "DX-Y.NYB", "VIX": "^VIX", "US10Y": "^TNX", "US2Y": "^IRX", "SP500": "^GSPC", "GLD": "GLD"}
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

class MacroClient:
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; TradingAI/1.0)"})

    @retry(wait=wait_exponential(multiplier=2, min=2, max=16), stop=stop_after_attempt(4))
    def _fetch_yahoo(self, symbol, from_ts, to_ts):
        resp = self._session.get(YAHOO_URL.format(symbol=symbol), params={
            "period1": int(from_ts.timestamp()), "period2": int(to_ts.timestamp()),
            "interval": "1d", "includePrePost": "false",
        }, timeout=30)
        resp.raise_for_status()
        result = resp.json()["chart"]["result"][0]
        df = pd.DataFrame({"ts": [datetime.fromtimestamp(t, tz=timezone.utc) for t in result["timestamp"]],
                           "value": result["indicators"]["quote"][0]["close"]})
        return df.dropna(subset=["value"])

    def fetch_all(self, from_ts, to_ts):
        rows = []
        for name, sym in MACRO_SYMBOLS.items():
            try:
                df = self._fetch_yahoo(sym, from_ts, to_ts)
                for _, row in df.iterrows():
                    rows.append({"ts": row["ts"], "symbol": name, "value": float(row["value"]), "source": "yahoo_finance"})
            except Exception as exc:
                import structlog
                structlog.get_logger().warning("macro_fetch_failed", symbol=name, error=str(exc))
        return rows
