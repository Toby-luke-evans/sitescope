"""Zoning router — lat/lng → full zoning + overlays + standards."""

from fastapi import APIRouter, HTTPException, Query

from app.services.toronto_address_search import get_toronto_parcel_at_point
from app.services.zoning_payload import build_zoning_payload

router = APIRouter()


@router.get("/")
async def lookup_zoning(
    city: str = Query("toronto", description="City key: toronto | vancouver"),
    lat: float = Query(..., description="Latitude (WGS84)"),
    lng: float = Query(..., description="Longitude (WGS84)"),
):
    """Get zoning classification, overlays, and full development standards for a parcel."""
    if city.lower() != "toronto":
        raise HTTPException(status_code=400, detail=f"City '{city}' not yet supported")

    parcel = None
    try:
        parcel = await get_toronto_parcel_at_point(lat, lng)
    except Exception:
        # ArcGIS parcel lookup is useful context, but zoning lookup can still run
        # from the coordinate alone. Don't fail the whole endpoint over city GIS.
        parcel = None

    return build_zoning_payload(lat=lat, lng=lng, city=city, parcel=parcel)
