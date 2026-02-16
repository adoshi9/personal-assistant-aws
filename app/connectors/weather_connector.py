"""Weather connector using OpenWeatherMap API."""

from typing import Any, Dict, Optional

import httpx
import structlog

from app.connectors.base import BaseConnector

logger = structlog.get_logger(__name__)


class WeatherConnector(BaseConnector):
    """Connector for weather information using OpenWeatherMap API."""

    def __init__(self, user_id: str, api_key_secret: str = "openweather/api-key"):
        """Initialize Weather connector.

        Args:
            user_id: User ID for approval notifications
            api_key_secret: AWS Secrets Manager secret name for API key
        """
        super().__init__(user_id)
        self.api_key_secret = api_key_secret
        self.api_key: Optional[str] = None
        self.base_url = "https://api.openweathermap.org/data/2.5"

    async def initialize(self) -> None:
        """Initialize connector with API key from Secrets Manager."""
        try:
            self.api_key = await self.secrets_manager.get_secret(self.api_key_secret)
            self.logger.info("Weather connector initialized")
        except Exception as e:
            self.logger.error("Failed to initialize Weather connector", error=str(e))
            raise

    async def health_check(self) -> bool:
        """Check if OpenWeatherMap API is accessible."""
        try:
            if not self.api_key:
                return False

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/weather",
                    params={"q": "London", "appid": self.api_key},
                    timeout=5.0,
                )
                return response.status_code == 200
        except Exception as e:
            self.logger.error("Weather health check failed", error=str(e))
            return False

    async def get_current_weather(
        self, city: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None
    ) -> Dict[str, Any]:
        """Get current weather information.

        Args:
            city: City name (e.g., "London", "New York")
            lat: Latitude (alternative to city)
            lon: Longitude (must be provided with lat)

        Returns:
            Current weather information
        """
        if not self.api_key:
            raise RuntimeError("Weather connector not initialized")

        if not city and (lat is None or lon is None):
            raise ValueError("Either city or (lat, lon) must be provided")

        try:
            params = {"appid": self.api_key, "units": "metric"}

            if city:
                params["q"] = city
            else:
                params["lat"] = lat
                params["lon"] = lon

            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/weather", params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()

            result = {
                "location": data["name"],
                "country": data["sys"]["country"],
                "temperature": data["main"]["temp"],
                "feels_like": data["main"]["feels_like"],
                "humidity": data["main"]["humidity"],
                "pressure": data["main"]["pressure"],
                "description": data["weather"][0]["description"],
                "wind_speed": data["wind"]["speed"],
                "clouds": data["clouds"]["all"],
            }

            self.logger.info("Retrieved current weather", location=result["location"])
            return result

        except httpx.HTTPError as e:
            self.logger.error("Failed to get current weather", error=str(e))
            raise

    async def get_forecast(
        self, city: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None, days: int = 5
    ) -> Dict[str, Any]:
        """Get weather forecast.

        Args:
            city: City name
            lat: Latitude (alternative to city)
            lon: Longitude (must be provided with lat)
            days: Number of days (1-5)

        Returns:
            Weather forecast information
        """
        if not self.api_key:
            raise RuntimeError("Weather connector not initialized")

        if not city and (lat is None or lon is None):
            raise ValueError("Either city or (lat, lon) must be provided")

        try:
            params = {"appid": self.api_key, "units": "metric", "cnt": min(days * 8, 40)}

            if city:
                params["q"] = city
            else:
                params["lat"] = lat
                params["lon"] = lon

            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/forecast", params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()

            forecasts = []
            for item in data["list"]:
                forecasts.append(
                    {
                        "datetime": item["dt_txt"],
                        "temperature": item["main"]["temp"],
                        "feels_like": item["main"]["feels_like"],
                        "humidity": item["main"]["humidity"],
                        "description": item["weather"][0]["description"],
                        "wind_speed": item["wind"]["speed"],
                        "rain_probability": item.get("pop", 0) * 100,
                    }
                )

            result = {
                "location": data["city"]["name"],
                "country": data["city"]["country"],
                "forecasts": forecasts,
            }

            self.logger.info("Retrieved weather forecast", location=result["location"], count=len(forecasts))
            return result

        except httpx.HTTPError as e:
            self.logger.error("Failed to get weather forecast", error=str(e))
            raise
