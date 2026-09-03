"""
weather_report.py — current weather, forecast and severe-weather alerts.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Optional


_WTTR_URL = "https://wttr.in/{query}?format=j1"


def _http_get(url: str, timeout: int = 12) -> Optional[str]:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "curl/7.88 JARVIS/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception:
        return None


def _slug(city: str) -> str:
    return re.sub(r"\s+", "+", city.strip())


class WeatherReport:
    """wttr.in + OpenWeatherMap fallback."""

    def __init__(self, openweathermap_key: Optional[str] = None):
        self.owm_key = (
            openweathermap_key
            or os.environ.get("OPENWEATHERMAP_API_KEY")
            or _cfg_get("openweathermap_api_key")
        )

    def get_current(self, city: str) -> dict:
        if not city:
            return {"error": "city is required"}
        url = _WTTR_URL.format(query=_slug(city))
        body = _http_get(url)
        if not body:
            if self.owm_key:
                return self._owm_current(city)
            return {"error": "weather service unreachable"}
        try:
            data = json.loads(body)
            cur = data["current_condition"][0]
            area = data.get("nearest_area", [{}])[0]
            return {
                "city":        city,
                "description": ", ".join(cur.get("weatherDesc", [{"value": ""}])[0].get("value", "").split()),
                "temp_c":      int(cur.get("temp_C", 0)),
                "temp_f":      int(cur.get("temp_F", 0)),
                "feels_like_c": int(cur.get("FeelsLikeC", 0)),
                "humidity":    int(cur.get("humidity", 0)),
                "wind_kph":    int(cur.get("windspeedKmph", 0)),
                "wind_dir":    cur.get("winddir16", ""),
                "pressure_mb": int(cur.get("pressure", 0)),
                "visibility_km": int(cur.get("visibility", 0)),
                "observed":    cur.get("observation_time", ""),
                "area":        ", ".join(
                    a for v, a in (
                        (area.get("areaName", [{}])[0].get("value", ""), "city"),
                        (area.get("region",   [{}])[0].get("value", ""), "region"),
                        (area.get("country",  [{}])[0].get("value", ""), "country"),
                    ) if a and v
                ),
                "ts":          datetime.now().isoformat(timespec="seconds"),
            }
        except Exception as e:
            return {"error": f"wttr.in parse error: {e}"}

    def get_forecast(self, city: str, days: int = 5) -> list[dict]:
        url = _WTTR_URL.format(query=_slug(city))
        body = _http_get(url)
        if not body:
            return []
        try:
            data = json.loads(body)
            out: list[dict] = []
            for day in data.get("weather", [])[: max(1, days)]:
                out.append({
                    "date":        day.get("date", ""),
                    "min_c":       int(day.get("mintempC", 0)),
                    "max_c":       int(day.get("maxtempC", 0)),
                    "min_f":       int(day.get("mintempF", 0)),
                    "max_f":       int(day.get("maxtempF", 0)),
                    "uv_index":    int(day.get("uvIndex", 0)),
                    "sunrise":     day.get("astronomy", [{}])[0].get("sunrise", ""),
                    "sunset":      day.get("astronomy", [{}])[0].get("sunset", ""),
                    "hourly":      self._summarise_hourly(day.get("hourly", [])),
                })
            return out
        except Exception:
            return []

    def get_weather_alerts(self) -> list[dict]:
        """Best-effort: scrape wttr.in for current 'severe' lines."""
        body = _http_get("https://wttr.in/?format=j1")
        if not body:
            return []
        try:
            data = json.loads(body)
            alerts: list[dict] = []
            for cur in data.get("current_condition", []):
                for desc in cur.get("weatherDesc", []):
                    text = desc.get("value", "")
                    if any(k in text.lower() for k in ("thunder", "storm", "snow",
                                                       "fog", "hurricane", "tornado")):
                        alerts.append({"type": text, "observed": cur.get("observation_time", "")})
            return alerts
        except Exception:
            return []

    # ── OpenWeatherMap fallback ────────────────────────────────────────────

    def _owm_current(self, city: str) -> dict:
        if not self.owm_key:
            return {"error": "no fallback key"}
        url = (
            "https://api.openweathermap.org/data/2.5/weather?"
            + urllib.parse.urlencode({"q": city, "appid": self.owm_key, "units": "metric"})
        )
        body = _http_get(url)
        if not body:
            return {"error": "owm unreachable"}
        try:
            d = json.loads(body)
            main = d.get("main", {})
            wind = d.get("wind", {})
            return {
                "city":        city,
                "description": d.get("weather", [{}])[0].get("description", ""),
                "temp_c":      main.get("temp", 0),
                "feels_like_c": main.get("feels_like", 0),
                "humidity":    main.get("humidity", 0),
                "wind_kph":    round(wind.get("speed", 0) * 3.6, 1),
                "pressure_mb": main.get("pressure", 0),
                "ts":          datetime.now().isoformat(timespec="seconds"),
            }
        except Exception as e:
            return {"error": f"owm parse error: {e}"}

    @staticmethod
    def _summarise_hourly(hourly: list[dict]) -> list[dict]:
        out: list[dict] = []
        for h in hourly:
            out.append({
                "time":   h.get("time", ""),
                "temp_c": int(h.get("tempC", 0)),
                "chance_of_rain": int(h.get("chanceofrain", 0)),
                "desc":   h.get("weatherDesc", [{}])[0].get("value", ""),
            })
        return out


def _cfg_get(key: str) -> Optional[str]:
    try:
        from config import get_config
        return get_config().get(key)
    except Exception:
        return None