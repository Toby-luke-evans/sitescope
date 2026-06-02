"""City-specific zoning bylaw parameters."""

from .toronto import ZONE_PARAMS as TORONTO_ZONE_PARAMS

try:
    from .vancouver import ZONE_PARAMS as VANCOUVER_ZONE_PARAMS
except ImportError:
    VANCOUVER_ZONE_PARAMS = {}

CITY_PARAMS = {
    "toronto": TORONTO_ZONE_PARAMS,
    "vancouver": VANCOUVER_ZONE_PARAMS,
}

def get_zone_params(city: str, zone_code: str) -> dict:
    """Get zone parameters for a city and zone code."""
    params = CITY_PARAMS.get(city, {})
    return params.get(zone_code, {})

__all__ = [
    "TORONTO_ZONE_PARAMS",
    "VANCOUVER_ZONE_PARAMS",
    "CITY_PARAMS",
    "get_zone_params",
]
