"""Global tracker plugin: OpenSky, SpaceX, USGS, AIS, weather, network."""

import json
import socket
import subprocess
import urllib.request
import urllib.error
from typing import Any

from ._template import PLUGIN_DESCRIPTION, PLUGIN_NAME, PLUGIN_VERSION


class GlobalTracker:
    """Global tracker for airspace, space, seismic, weather, and network data."""

    def get_airspace(self, lat: float = 0.0, lon: float = 0.0, radius_km: int = 50) -> dict:
        """Get aircraft within radius_km using OpenSky API."""
        try:
            url = f"https://opensky-network.org/api/states/all?lamin={lat-0.5}&lomin={lon-0.5}&lamax={lat+0.5}&lomax={lon+0.5}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            states = data.get("states", [])
            aircraft = []
            for s in states:
                icao24 = s[0]
                callsign = s[1].strip() if s[1] else ""
                origin_country = s[2]
                altitude = s[7]
                speed = s[9]
                heading = s[10]
                aircraft.append({
                    "icao24": icao24,
                    "callsign": callsign,
                    "country": origin_country,
                    "altitude_m": altitude,
                    "speed_ms": speed,
                    "heading_deg": heading,
                })
            return {"status": "success", "count": len(aircraft), "aircraft": aircraft}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_spacex_next_launch(self) -> dict:
        """Get next SpaceX launch."""
        try:
            url = "https://api.spacexdata.com/v4/launches/next"
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return {
                "status": "success",
                "name": data.get("name"),
                "date": data.get("date_utc"),
                "rocket": data.get("rocket"),
                "success": data.get("success"),
                "details": data.get("details"),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_earthquakes(self, min_magnitude: float = 2.5, hours: int = 24) -> dict:
        """Get USGS earthquake feed."""
        try:
            url = f"https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_{hours}h.geojson"
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            quakes = []
            for feat in data.get("features", []):
                props = feat["properties"]
                quakes.append({
                    "mag": props.get("mag"),
                    "place": props.get("place"),
                    "time": props.get("time"),
                    "depth_km": feat["geometry"]["coordinates"][2],
                })
            return {"status": "success", "count": len(quakes), "earthquakes": quakes}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_weather(self, city: str) -> dict:
        """Get weather from wttr.in (no API key required)."""
        try:
            city_enc = city.replace(" ", "+")
            url = f"https://wttr.in/{city_enc}?format=j1"
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            current = data.get("current_condition", [{}])[0]
            return {
                "status": "success",
                "city": city,
                "temp_c": current.get("temp_C"),
                "humidity": current.get("humidity"),
                "description": current.get("weatherDesc", [{}])[0].get("value"),
                "wind_kph": current.get("windspeedKmph"),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_public_ip(self) -> dict:
        """Get public IP address."""
        try:
            with urllib.request.urlopen("https://ifconfig.me/ip", timeout=10) as resp:
                ip = resp.read().decode("utf-8").strip()
            return {"status": "success", "ip": ip}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_network_interfaces(self) -> dict:
        """Get network interfaces via `ip addr`."""
        try:
            result = subprocess.run(
                ["ip", "addr"], capture_output=True, text=True, check=True, timeout=10
            )
            return {"status": "success", "interfaces": result.stdout}
        except Exception as e:
            return {"status": "error", "message": str(e)}


def get_tools() -> list[dict]:
    return [
        {"name": "get_airspace", "description": "Get aircraft within 50km via OpenSky.", "parameters": {"type": "object", "properties": {"lat": {"type": "number"}, "lon": {"type": "number"}}, "required": ["lat", "lon"]}},
        {"name": "get_spacex_next_launch", "description": "Get next SpaceX launch."},
        {"name": "get_earthquakes", "description": "Get USGS earthquake feed.", "parameters": {"type": "object", "properties": {"min_magnitude": {"type": "number"}, "hours": {"type": "integer"}}, "required": []}},
        {"name": "get_weather", "description": "Get weather for a city.", "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}},
        {"name": "get_public_ip", "description": "Get public IP address."},
        {"name": "get_network_interfaces", "description": "Get network interfaces."},
    ]


def execute(tool_name: str, params: dict) -> dict:
    instance = GlobalTracker()
    method = getattr(instance, tool_name, None)
    if method and callable(method):
        try:
            return method(**params)
        except TypeError as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "error": f"Unknown tool: {tool_name}"}


if __name__ == "__main__":
    print(json.dumps(execute("get_weather", {"city": "London"}), indent=2))
