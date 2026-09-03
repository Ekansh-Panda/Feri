"""
flight_finder.py — flight search + tracking via free public sources (no API keys).
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional


def _http_get(url: str, timeout: int = 12) -> Optional[str]:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124 Safari/537.36"
                ),
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception:
        return None


def _normalize_iata(code: str) -> str:
    return (code or "").upper().strip()[:3]


class FlightFinder:
    """Flight search + tracking via OpenSky, Kiwi (public endpoints) and Google."""

    OPENSKY_BASE = "https://opensky-network.org/api"

    def __init__(self) -> None:
        self._airports_cache: dict[str, dict] = {}

    # ── Search ─────────────────────────────────────────────────────────────

    def search_flights(self, origin: str, destination: str, date: str) -> dict:
        """
        `date` in YYYY-MM-DD. Returns a structured dict that combines:
          - kiwi.com public flight search page metadata
          - opensky nearby live flights (origin bbox)
        """
        origin = _normalize_iata(origin)
        destination = _normalize_iata(destination)
        if not (origin and destination):
            return {"error": "origin and destination (IATA codes) are required"}

        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            return {"error": "date must be YYYY-MM-DD"}

        # Kiwi public landing page (no API, just metadata)
        kiwi_url = (
            "https://www.kiwi.com/en/search/results/"
            f"{origin}/{destination}/{date}"
        )
        live = self._opensky_by_airport(origin)

        return {
            "origin":      origin,
            "destination": destination,
            "date":        date,
            "kiwi_url":    kiwi_url,
            "live_origin": live,
            "ts":          datetime.now().isoformat(timespec="seconds"),
        }

    # ── Live tracking ──────────────────────────────────────────────────────

    def track_flight(self, flight_number: str) -> dict:
        """Live state vector for a flight via OpenSky /states/all."""
        flight_number = (flight_number or "").upper().strip()
        if not flight_number:
            return {"error": "flight_number required"}

        body = _http_get(f"{self.OPENSKY_BASE}/states/all")
        if not body:
            return {"error": "opensky unreachable"}
        try:
            data = json.loads(body)
        except Exception as e:
            return {"error": f"parse error: {e}"}

        for s in data.get("states", []) or []:
            # s format: icao24, callsign, origin_country, time_position, last_contact,
            # longitude, latitude, baro_altitude, on_ground, velocity, true_track,
            # vertical_rate, sensors, geo_altitude, squawk, spi, position_source
            if not s or len(s) < 11:
                continue
            callsign = (s[1] or "").strip().upper()
            if callsign == flight_number:
                return {
                    "icao24":        s[0],
                    "callsign":      callsign,
                    "country":       s[2],
                    "longitude":     s[5],
                    "latitude":      s[6],
                    "baro_alt_m":    s[7],
                    "on_ground":     s[8],
                    "velocity_mps":  s[9],
                    "heading_deg":   s[10],
                    "last_contact":  s[4],
                    "ts":            datetime.now().isoformat(timespec="seconds"),
                }
        return {"error": f"Flight {flight_number} not currently airborne"}

    # ── Airport info ───────────────────────────────────────────────────────

    def get_airport_info(self, code: str) -> dict:
        code = _normalize_iata(code)
        if not code:
            return {"error": "code required"}
        if code in self._airports_cache:
            return self._airports_cache[code]

        # Pull from a tiny GitHub-hosted open dataset (public domain).
        url = (
            "https://raw.githubusercontent.com/jpatokal/"
            "openflights/master/data/airports.dat"
        )
        body = _http_get(url, timeout=15)
        airports: list[dict] = []
        if body:
            for line in body.splitlines():
                fields = line.strip().split(",")
                # CSV format: 1=Name, 2=City, 3=Country, 4=IATA, 5=ICAO,
                # 6=Lat, 7=Lon, 8=Alt, 9=Timezone, 11=Type, 12=Source
                if len(fields) > 4 and fields[4].strip('"') == code:
                    airports.append({
                        "name":    fields[1].strip('"'),
                        "city":    fields[2].strip('"'),
                        "country": fields[3].strip('"'),
                        "iata":    fields[4].strip('"'),
                        "icao":    fields[5].strip('"') if len(fields) > 5 else "",
                        "lat":     float(fields[6]) if len(fields) > 6 and fields[6] else 0.0,
                        "lon":     float(fields[7]) if len(fields) > 7 and fields[7] else 0.0,
                        "alt":     float(fields[8]) if len(fields) > 8 and fields[8] else 0.0,
                        "tz":      fields[9].strip('"') if len(fields) > 9 else "",
                    })
                    break

        info = airports[0] if airports else {"error": f"airport {code} not found"}
        self._airports_cache[code] = info
        return info

    # ── Internals ──────────────────────────────────────────────────────────

    def _opensky_by_airport(self, iata: str) -> list[dict]:
        bbox = _airport_bbox(iata) or {}
        if not bbox:
            return []
        params = urllib.parse.urlencode({
            "lamin": bbox["lat_min"], "lamax": bbox["lat_max"],
            "lomin": bbox["lon_min"], "lomax": bbox["lon_max"],
        })
        body = _http_get(f"{self.OPENSKY_BASE}/states/all?{params}", timeout=15)
        if not body:
            return []
        try:
            data = json.loads(body)
        except Exception:
            return []
        out: list[dict] = []
        for s in (data.get("states") or [])[:20]:
            if not s or len(s) < 11:
                continue
            out.append({
                "callsign":   (s[1] or "").strip(),
                "country":    s[2],
                "lat":        s[6],
                "lon":        s[5],
                "alt_m":      s[7],
                "velocity_mps": s[9],
                "on_ground":  s[8],
            })
        return out


def _airport_bbox(iata: str) -> Optional[dict]:
    finder = FlightFinder()
    info = finder.get_airport_info(iata)
    if "error" in info:
        return None
    lat, lon = info.get("lat", 0.0), info.get("lon", 0.0)
    return {"lat_min": lat - 1.5, "lat_max": lat + 1.5,
            "lon_min": lon - 1.5, "lon_max": lon + 1.5}