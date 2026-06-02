"""Toronto parcel address search.

Uses the City of Toronto ArcGIS parcel layer to resolve an address string to
actual parcel geometry. This is intentionally parcel-first: we use the parcel
centroid for zoning lookup instead of generic geocoding so users don't get
random "no zoning data" because a geocoder point landed in the street, sidewalk,
water, or general vibes district.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx
from shapely.geometry import Polygon

logger = logging.getLogger(__name__)

ARCGIS_PARCEL_URL = "https://gis.toronto.ca/arcgis/rest/services/cot_geospatial27/MapServer/36/query"

_STREET_ABBREVS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bStreet\b", re.IGNORECASE), "St"),
    (re.compile(r"\bAvenue\b", re.IGNORECASE), "Ave"),
    (re.compile(r"\bBoulevard\b", re.IGNORECASE), "Blvd"),
    (re.compile(r"\bDrive\b", re.IGNORECASE), "Dr"),
    (re.compile(r"\bRoad\b", re.IGNORECASE), "Rd"),
    (re.compile(r"\bCrescent\b", re.IGNORECASE), "Cres"),
    (re.compile(r"\bCourt\b", re.IGNORECASE), "Ct"),
    (re.compile(r"\bPlace\b", re.IGNORECASE), "Pl"),
    (re.compile(r"\bCircle\b", re.IGNORECASE), "Cir"),
    (re.compile(r"\bTerrace\b", re.IGNORECASE), "Terr"),
    (re.compile(r"\bParkway\b", re.IGNORECASE), "Pkwy"),
    (re.compile(r"\bEast\b", re.IGNORECASE), "E"),
    (re.compile(r"\bWest\b", re.IGNORECASE), "W"),
    (re.compile(r"\bNorth\b", re.IGNORECASE), "N"),
    (re.compile(r"\bSouth\b", re.IGNORECASE), "S"),
]


def normalize_street_name(name: str) -> str:
    """Normalize street text to Toronto ArcGIS's title-cased abbreviated style."""
    result = name.split(",")[0].strip().title()
    for pattern, replacement in _STREET_ABBREVS:
        result = pattern.sub(replacement, result)
    return " ".join(result.split())


def parse_address(address: str) -> tuple[str | None, str]:
    """Split an address into (street_number | None, normalized_street_name)."""
    cleaned = address.strip()
    cleaned = re.sub(r"\bToronto\b.*$", "", cleaned, flags=re.IGNORECASE).strip(" ,")
    match = re.match(r"^(\d+[A-Za-z]?)\s+(.+)$", cleaned)
    if match:
        return match.group(1).upper(), normalize_street_name(match.group(2))
    return None, normalize_street_name(cleaned)


def _sql_literal(value: str) -> str:
    """Escape a value for ArcGIS SQL where clauses."""
    return value.replace("'", "''")


def _parcel_from_feature(feature: dict[str, Any]) -> dict[str, Any] | None:
    geometry = feature.get("geometry") or {}
    rings = geometry.get("rings") or []
    if not rings:
        return None

    try:
        polygon = Polygon(rings[0])
        if polygon.is_empty:
            return None
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        centroid = polygon.centroid
    except Exception as exc:  # pragma: no cover - defensive against bad city data
        logger.warning("Bad ArcGIS parcel geometry: %s", exc)
        return None

    attrs = feature.get("attributes") or {}
    addr_num = str(attrs.get("ADDRESS_NUMBER") or "").strip()
    street = str(attrs.get("LINEAR_NAME_FULL") or "").strip()
    address = f"{addr_num} {street}, Toronto, ON".strip()
    if address.startswith(","):
        address = address.lstrip(", ")

    return {
        "id": str(attrs.get("OBJECTID") or f"{addr_num}-{street}"),
        "address": address,
        "lat": centroid.y,
        "lng": centroid.x,
        "geometry": {
            "type": "Polygon",
            "coordinates": [list(polygon.exterior.coords)],
        },
    }


async def get_toronto_parcel_at_point(lat: float, lng: float) -> dict[str, Any] | None:
    """Return the Toronto parcel containing a WGS84 point, if available."""
    params: dict[str, Any] = {
        "geometry": f"{lng},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "OBJECTID,ADDRESS_NUMBER,LINEAR_NAME_FULL,FEATURE_TYPE",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
        "resultRecordCount": 1,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(ARCGIS_PARCEL_URL, params=params)
        response.raise_for_status()
        data = response.json()

    if data.get("error"):
        raise RuntimeError(data["error"].get("message") or "ArcGIS parcel point lookup failed")

    features = data.get("features") or []
    if not features:
        return None
    return _parcel_from_feature(features[0])


async def search_toronto_parcels(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search Toronto parcels by civic address."""
    number, street = parse_address(query)
    if not street:
        return []

    street_upper = _sql_literal(street.upper())
    if number:
        where = f"ADDRESS_NUMBER = '{_sql_literal(number)}' AND UPPER(LINEAR_NAME_FULL) = '{street_upper}'"
    else:
        where = f"UPPER(LINEAR_NAME_FULL) LIKE '{street_upper}%'"

    params: dict[str, Any] = {
        "where": where,
        "outFields": "OBJECTID,ADDRESS_NUMBER,LINEAR_NAME_FULL,FEATURE_TYPE",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
        "resultRecordCount": limit,
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        logger.info("Toronto ArcGIS parcel search where=%s", where)
        response = await client.get(ARCGIS_PARCEL_URL, params=params)
        response.raise_for_status()
        data = response.json()

    if data.get("error"):
        raise RuntimeError(data["error"].get("message") or "ArcGIS parcel search failed")

    features = data.get("features") or []
    parcels = []
    for feature in features:
        parcel = _parcel_from_feature(feature)
        if parcel:
            parcels.append(parcel)
    return parcels
