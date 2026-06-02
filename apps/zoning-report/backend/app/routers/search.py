"""Search router — address → lat/lng + parcel metadata."""

from fastapi import APIRouter, HTTPException, Query

from zoning_core.spatial import lookup_zone, is_loaded

router = APIRouter()

TORONTO_CKAN_BASE = "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action"


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
    """Find the nearest parcel for a lat/lng coordinate."""
    if city.lower() == "toronto":
        return await _reverse_toronto(lat, lng)
    raise HTTPException(status_code=400, detail=f"City '{city}' not yet supported")


async def _search_toronto(q: str, limit: int) -> dict:
    return {
        "city": "toronto",
        "query": q,
        "results": [],
        "note": "Address search integration pending — use reverse geocode for now",
    }


async def _reverse_toronto(lat: float, lng: float) -> dict:
    if not is_loaded():
        return {
            "city": "toronto",
            "lat": lat,
            "lng": lng,
            "error": "Zoning index not yet loaded. Try again in ~30 seconds.",
        }

    zone = lookup_zone(lng, lat)
    if zone is None:
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
        "results": [
            {
                "id": f"tor_{lat}_{lng}",
                "lat": lat,
                "lng": lng,
                "zone_code": zone.zone_code,
                "zn_string": zone.zn_string,
                "fsi_total": zone.fsi_total,
                "density": zone.density,
                "stand_set": zone.stand_set,
            }
        ],
    }
