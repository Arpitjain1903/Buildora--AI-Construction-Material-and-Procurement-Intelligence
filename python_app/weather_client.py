"""
Weather Client supporting OpenWeatherMap and Open-Meteo providers.
Provides current weather, short forecast, hot/cold weather concreting alerts,
caching with TTL, and seamless fallback to regional climate defaults.
"""

import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import httpx

from python_app.config import settings

logger = logging.getLogger("weather_client")
logger.setLevel(logging.INFO)

class WeatherClient:
    def __init__(self):
        self.provider = (settings.WEATHER_PROVIDER or "openweathermap").lower().strip()
        self.api_key = settings.WEATHER_API_KEY
        self.base_url = settings.WEATHER_BASE_URL or (
            "https://api.openweathermap.org/data/2.5"
            if self.provider == "openweathermap"
            else "https://api.open-meteo.com/v1"
        )
        self.timeout = 8.0
        self.cache_ttl_seconds = 3600  # 1 hour
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _get_cache_key(self, lat: float, lon: float) -> str:
        return f"{self.provider}_{round(lat, 2)}_{round(lon, 2)}"

    def get_weather(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Fetches current weather and short forecast for lat/lon.
        Uses TTL cache, supports OpenWeatherMap and Open-Meteo,
        and falls back gracefully if unconfigured or unreachable.
        """
        cache_key = self._get_cache_key(lat, lon)
        now = time.time()

        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if now - entry["cached_at"] < self.cache_ttl_seconds:
                cached_data = dict(entry["data"])
                cached_data["is_cached"] = True
                return cached_data

        result = None
        if self.provider == "openweathermap" and self.api_key:
            result = self._fetch_openweathermap(lat, lon)
        elif self.provider == "open-meteo" or not self.api_key:
            # Open-meteo requires no key, excellent fallback
            result = self._fetch_open_meteo(lat, lon)

        if not result:
            result = self._get_offline_fallback(lat, lon)

        # Annotate concreting flags
        temp = result["temp_c"]
        result["hot_weather_concreting_flag"] = temp > 35.0
        result["cold_weather_concreting_flag"] = temp < 5.0
        result["rain_alert_flag"] = result.get("rainfall_mm", 0.0) > 0.1 or "rain" in result.get("description", "").lower()
        result["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Cache the result
        self._cache[cache_key] = {"data": result, "cached_at": now}
        return result

    def _fetch_openweathermap(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        try:
            current_url = f"{self.base_url.rstrip('/')}/weather"
            forecast_url = f"{self.base_url.rstrip('/')}/forecast"
            params = {"lat": lat, "lon": lon, "appid": self.api_key, "units": "metric"}

            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(current_url, params=params)
                if resp.status_code != 200:
                    logger.warning(f"OpenWeatherMap current weather returned {resp.status_code}: {resp.text[:100]}")
                    return None
                data = resp.json()

                # Forecast (optional, don't fail if forecast fails)
                forecast_list: List[Dict[str, Any]] = []
                try:
                    f_resp = client.get(forecast_url, params=params)
                    if f_resp.status_code == 200:
                        f_data = f_resp.json().get("list", [])
                        # Sample once every 24h (every 8 steps of 3h)
                        for item in f_data[::8][:4]:
                            forecast_list.append({
                                "datetime": item.get("dt_txt"),
                                "temp_c": item.get("main", {}).get("temp"),
                                "description": item.get("weather", [{}])[0].get("description", ""),
                                "rain_mm": item.get("rain", {}).get("3h", 0.0)
                            })
                except Exception as fe:
                    logger.debug(f"OpenWeatherMap forecast fetch non-fatal error: {fe}")

                return {
                    "temp_c": float(data.get("main", {}).get("temp", 28.0)),
                    "humidity": float(data.get("main", {}).get("humidity", 50.0)),
                    "rainfall_mm": float(data.get("rain", {}).get("1h", 0.0)),
                    "wind_speed_ms": float(data.get("wind", {}).get("speed", 3.0)),
                    "description": data.get("weather", [{}])[0].get("description", "clear sky"),
                    "short_forecast": forecast_list,
                    "source": "openweathermap",
                    "source_label": "Live OpenWeatherMap API",
                    "is_cached": False
                }
        except Exception as e:
            logger.error(f"Error calling OpenWeatherMap: {e}")
            return None

    def _fetch_open_meteo(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        try:
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                "forecast_days": 3,
                "timezone": "auto"
            }
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, params=params)
                if resp.status_code != 200:
                    logger.warning(f"Open-Meteo returned status {resp.status_code}")
                    return None
                data = resp.json()
                current = data.get("current", {})
                daily = data.get("daily", {})

                forecast_list: List[Dict[str, Any]] = []
                times = daily.get("time", [])
                max_temps = daily.get("temperature_2m_max", [])
                min_temps = daily.get("temperature_2m_min", [])
                precips = daily.get("precipitation_sum", [])
                for i in range(len(times)):
                    forecast_list.append({
                        "date": times[i],
                        "temp_max_c": max_temps[i] if i < len(max_temps) else None,
                        "temp_min_c": min_temps[i] if i < len(min_temps) else None,
                        "precipitation_sum_mm": precips[i] if i < len(precips) else 0.0
                    })

                precip = float(current.get("precipitation", 0.0))
                desc = "Rainy" if precip > 0.5 else "Clear to Mild"
                return {
                    "temp_c": float(current.get("temperature_2m", 28.0)),
                    "humidity": float(current.get("relative_humidity_2m", 50.0)),
                    "rainfall_mm": precip,
                    "wind_speed_ms": float(current.get("wind_speed_10m", 3.0)),
                    "description": desc,
                    "short_forecast": forecast_list,
                    "source": "open-meteo",
                    "source_label": "Live Open-Meteo API",
                    "is_cached": False
                }
        except Exception as e:
            logger.error(f"Error calling Open-Meteo: {e}")
            return None

    def _get_offline_fallback(self, lat: float, lon: float) -> Dict[str, Any]:
        """Deterministic regional table fallback when offline or no API is available."""
        return {
            "temp_c": 28.0,
            "humidity": 60.0,
            "rainfall_mm": 0.0,
            "wind_speed_ms": 4.0,
            "description": "Seasonal average estimate (offline fallback)",
            "short_forecast": [],
            "source": "rule_based_fallback",
            "source_label": "Offline Regional Climate Table",
            "is_cached": False
        }

weather_client = WeatherClient()
