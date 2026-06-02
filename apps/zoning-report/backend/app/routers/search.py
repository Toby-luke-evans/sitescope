"""Search router — address → parcel centroid + zoning summary."""

from fastapi import APIRouter, HTTPException, Query

from app.services.toronto_address_search import search_toronto_parcels
from zoning_core.bylaws import get_zone_params
from zoning_core.spatial import (
    is_loaded,
    lookup_height,
    lookup_lot_coverage,
    lookup_parking_zone,
    lookup_zone,
)

router = APIRouter()


@router.get("/")
async def search_address(
    city: str = Query("toronto", description="City key: toronto | vancouver"),
    q: str = Query(..., description="Address query string"),
    limit: int = Query(10, ge=1, le=50),
):
    """Search for parcels by address string."""
    if city.lower() == "toronto":
        return await _search_toronto(q, limit)
    raise HTTPException(status_code=400, detail=f"City '{city}' not yet supported")


@router.get("/reverse")
async def reverse_search(
    city: str = Query("toronto", description="City key: toronto | vancouver"),
    lat: float = Query(..., description="Latitude (WGS84)"),
    lng: float = Query(..., description="Longitude (WGS84)"),
):
    """Find the nearest/containing zoning parcel for a lat/lng coordinate."""
    if city.lower() == "toronto":
        return await _reverse_toronto(lat, lng)
    raise HTTPException(status_code=400, detail=f"City '{city}' not yet supported")


async def _search_toronto(q: str, limit: int) -> dict:
    try:
        parcels = await search_toronto_parcels(q, limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Toronto parcel search unavailable: {exc}") from exc

    results = []
    for parcel in parcels:
        enriched = _build_search_result(parcel["lat"], parcel["lng"])
        enriched.update({
            "id": parcel["id"],
            "address": parcel["address"],
            "geometry": parcel["geometry"],
        })
        results.append(enriched)

    return {
        "city": "toronto",
        "query": q,
        "results": results,
        "total": len(results),
    }


async def _reverse_toronto(lat: float, lng: float) -> dict:
    if not is_loaded():
        return {
            "city": "toronto",
            "lat": lat,
            "lng": lng,
            "results": [],
            "error": "Zoning index not yet loaded. Try again in ~30 seconds.",
        }

    result = _build_search_result(lat, lng)
    if result.get("zoning") is None:
        return {
            "city": "toronto",
            "lat": lat,
            "lng": lng,
            "results": [],
            "note": "No zoning data found at this location.",
        }

    return {
        "city": "toronto",
        "lat": lat,
        "lng": lng,
        "results": [result],
        "total": 1,
    }


def _build_search_result(lat: float, lng: float) -> dict:
    """Build a search-result shape from a WGS84 point."""
    base = {
        "id": f"tor_{lat:.7f}_{lng:.7f}",
        "lat": lat,
        "lng": lng,
        "zoning": None,
        "overlays": {
            "height": {"height_m": None, "storeys": None},
            "lot_coverage": {"coverage_pct": None},
            "parking_zone": {"zone": None},
        },
    }

    if not is_loaded():
        base["error"] = "Zoning index loading. Please retry in ~30 seconds."
        return base

    zone = lookup_zone(lng, lat)
    height = lookup_height(lng, lat)
    coverage = lookup_lot_coverage(lng, lat)
    parking = lookup_parking_zone(lng, lat)

    base["overlays"] = {
        "height": {
            "height_m": height.height_m if height else None,
            "storeys": height.storeys if height else None,
        },
        "lot_coverage": {"coverage_pct": coverage},
        "parking_zone": {"zone": parking},
    }

    if zone is None:
        return base

    params = get_zone_params("toronto", zone.zone_code)
    max_height_m = height.height_m if height else params.get("max_height_m")
    storeys = height.storeys if height else None
    if not storeys and max_height_m:
        storeys = int(max_height_m / 3.0)

    base["zone_code"] = zone.zone_code
    base["zn_string"] = zone.zn_string
    base["zoning"] = {
        "zone_code": zone.zone_code,
        "zn_string": zone.zn_string,
        "max_fsi": zone.fsi_total or params.get("max_fsi"),
        "max_height_m": max_height_m,
        "storeys": storeys,
        "density": zone.density or params.get("density"),
        "lot_coverage": zone.lot_coverage or coverage,
        "stand_set": zone.stand_set,
    }
    return base
