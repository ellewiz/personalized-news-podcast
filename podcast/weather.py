import requests

# The National Weather Service API is free, keyless, and official U.S. government
# data — no signup, no rate-limit headaches. It does ask for a descriptive
# User-Agent identifying the app (not a real API key, just good citizenship).
USER_AGENT = "personalized-news-podcast (https://github.com/ellewiz/personalized-news-podcast)"
NWS_POINTS_URL = "https://api.weather.gov/points/{lat},{lon}"


def fetch_forecast(lat: float, lon: float) -> dict:
    """Fetch today's daytime forecast period for a lat/lon from the NWS API."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/geo+json"}

    points_resp = requests.get(
        NWS_POINTS_URL.format(lat=lat, lon=lon), headers=headers, timeout=30
    )
    points_resp.raise_for_status()
    forecast_url = points_resp.json()["properties"]["forecast"]

    forecast_resp = requests.get(forecast_url, headers=headers, timeout=30)
    forecast_resp.raise_for_status()
    periods = forecast_resp.json()["properties"]["periods"]

    today = next((p for p in periods if p.get("isDaytime")), periods[0])
    return {
        "period_name": today["name"],
        "temperature": today["temperature"],
        "temperature_unit": today["temperatureUnit"],
        "short_forecast": today["shortForecast"],
        "detailed_forecast": today["detailedForecast"],
    }
