"""Economic calendar via Finnhub."""
import os
from datetime import datetime, timezone
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

class CalendarClient:
    def __init__(self):
        self._api_key = os.environ["FINNHUB_API_KEY"]
        self._session = requests.Session()

    @retry(wait=wait_exponential(multiplier=2, min=2, max=16), stop=stop_after_attempt(4))
    def fetch_events(self, from_date, to_date):
        resp = self._session.get("https://finnhub.io/api/v1/calendar/economic",
            params={"from": from_date, "to": to_date, "token": self._api_key}, timeout=20)
        resp.raise_for_status()
        events = []
        for item in resp.json().get("economicCalendar", []):
            if item.get("country") != "US": continue
            if item.get("impact") not in ("high", "medium"): continue
            actual = item.get("actual"); forecast = item.get("estimate"); previous = item.get("prev")
            surprise = None
            if actual is not None and forecast is not None:
                try: surprise = float(actual) - float(forecast)
                except (TypeError, ValueError): pass
            events.append({
                "event_ts": datetime.fromisoformat(item["time"]).replace(tzinfo=timezone.utc)
                            if "T" in item["time"] else datetime.strptime(item["time"], "%Y-%m-%d").replace(tzinfo=timezone.utc),
                "event_name": item.get("event", ""), "country": item.get("country", "US"),
                "impact": item.get("impact", "medium"),
                "actual": float(actual) if actual is not None else None,
                "forecast": float(forecast) if forecast is not None else None,
                "previous": float(previous) if previous is not None else None,
                "surprise": surprise, "source": "finnhub",
            })
        return events
