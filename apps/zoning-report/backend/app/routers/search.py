"""Search router — address → parcel centroid + zoning summary."""

from fastapi import APIRouter, HTTPException, Query

from app.services.toronto_address_search import search_toronto_parcels
from app.services.zoning_payload import build_zoning_payload

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
    """Find the containing zoning parcel for a lat/lng coordinate."""
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
        enriched = build_zoning_payload(
            lat=parcel["lat"],
            lng=parcel["lng"],
            city="toronto",
            parcel=parcel,
        )
        result = {
            "id": parcel["id"],
            "address": parcel["address"],
            "lat": parcel["lat"],
            "lng": parcel["lng"],
            "geometry": parcel["geometry"],
            "zone_code": enriched.get("parcel", {}).get("zone_code"),
            "zn_string": enriched.get("parcel", {}).get("zn_string"),
            "zoning": enriched.get("zoning"),
            "overlays": enriched.get("overlays"),
            "standards": enriched.get("standards"),
            "development_standards": enriched.get("development_standards"),
        }
        if enriched.get("error"):
            result["error"] = enriched["error"]
        if enriched.get("note"):
            result["note"] = enriched["note"]
        results.append(result)

    return {
        "city": "toronto",
        "query": q,
        "results": results,
        "total": len(results),
    }


async def _reverse_toronto(lat: float, lng: float) -> dict:
    result = build_zoning_payload(lat=lat, lng=lng, city="toronto")
    if result.get("zoning") is None:
        return {
            "city": "toronto",
            "lat": lat,
            "lng": lng,
            "results": [],
            "note": result.get("note") or "No zoning data found at this location.",
            "error": result.get("error"),
        }

    search_result = {
        "id": result.get("parcel", {}).get("id") or f"tor_{lat:.7f}_{lng:.7f}",
        "lat": lat,
        "lng": lng,
        "zone_code": result.get("parcel", {}).get("zone_code"),
        "zn_string": result.get("parcel", {}).get("zn_string"),
        "zoning": result.get("zoning"),
        "overlays": result.get("overlays"),
        "standards": result.get("standards"),
        "development_standards": result.get("development_standards"),
    }
    return {
        "city": "toronto",
        "lat": lat,
        "lng": lng,
        "results": [search_result],
        "total": 1,
    }
