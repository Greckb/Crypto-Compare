"""OANDA v20 REST client for XAU/USD OHLCV ingestion."""
import os
from datetime import datetime, timezone
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

OANDA_HOSTS = {"practice": "https://api-fxpractice.oanda.com", "live": "https://api-fxtrade.oanda.com"}
INSTRUMENT = "XAU_USD"
MAX_CANDLES_PER_REQUEST = 5000

class OandaError(Exception): pass
class OandaRateLimitError(OandaError): pass

class OandaClient:
    def __init__(self):
        env = os.environ["OANDA_ENV"]
        self._base = OANDA_HOSTS[env]
        self._account_id = os.environ["OANDA_ACCOUNT_ID"]
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {os.environ['OANDA_API_KEY']}",
            "Content-Type": "application/json",
            "Accept-Datetime-Format": "RFC3339",
        })

    @retry(retry=retry_if_exception_type(OandaRateLimitError),
           wait=wait_exponential(multiplier=2, min=2, max=30), stop=stop_after_attempt(5))
    def _get(self, path, params):
        resp = self._session.get(f"{self._base}{path}", params=params, timeout=30)
        if resp.status_code == 429: raise OandaRateLimitError("Rate limit hit")
        if not resp.ok: raise OandaError(f"OANDA API {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    def fetch_candles(self, granularity, from_ts, to_ts):
        candles = []
        cursor = from_ts
        while cursor < to_ts:
            data = self._get(f"/v3/instruments/{INSTRUMENT}/candles", params={
                "granularity": granularity, "price": "MBA",
                "from": cursor.isoformat(), "to": to_ts.isoformat(), "count": MAX_CANDLES_PER_REQUEST,
            })
            batch = data.get("candles", [])
            if not batch: break
            candles.extend(batch)
            last_ts = datetime.fromisoformat(batch[-1]["time"].replace("Z", "+00:00"))
            cursor = last_ts
            if len(batch) < MAX_CANDLES_PER_REQUEST: break
        return [self._parse_candle(c) for c in candles if c.get("complete")]

    def _parse_candle(self, raw):
        mid = raw.get("mid", {}); bid = raw.get("bid", {}); ask = raw.get("ask", {})
        ts = datetime.fromisoformat(raw["time"].replace("Z", "+00:00"))
        return {
            "ts": ts, "open": float(mid.get("o", 0)), "high": float(mid.get("h", 0)),
            "low": float(mid.get("l", 0)), "close": float(mid.get("c", 0)),
            "bid_open": float(bid.get("o", 0)) if bid else None,
            "bid_close": float(bid.get("c", 0)) if bid else None,
            "ask_open": float(ask.get("o", 0)) if ask else None,
            "ask_close": float(ask.get("c", 0)) if ask else None, "source": "oanda",
        }

    def get_current_price(self):
        data = self._get(f"/v3/accounts/{self._account_id}/pricing", params={"instruments": INSTRUMENT})
        prices = data["prices"][0]
        bid = float(prices["bids"][0]["price"]); ask = float(prices["asks"][0]["price"])
        return {"bid": bid, "ask": ask, "mid": (bid + ask) / 2, "ts": datetime.now(timezone.utc)}
