"""Zoning router — lat/lng → full zoning + overlay + standards."""

import os
from fastapi import APIRouter, HTTPException, Query

from zoning_core.spatial import (
    lookup_zone,
    lookup_height,
    lookup_lot_coverage,
    lookup_parking_zone,
    is_loaded,
)
from zoning_core.bylaws import get_zone_params

router = APIRouter()


@router.get("/")
async def lookup_zoning(
    city: str = Query("toronto", description="City key: toronto | vancouver"),
    lat: float = Query(..., description="Latitude (WGS84)"),
    lng: float = Query(..., description="Longitude (WGS84)"),
):
    """Get full zoning classification, overlays, and development standards for a parcel."""
    if city.lower() != "toronto":
        raise HTTPException(status_code=400, detail=f"City '{city}' not yet supported")

    if not is_loaded():
        return {
            "parcel": {"lat": lat, "lng": lng},
            "error": "Zoning index loading. Please retry in ~30 seconds.",
        }

    zone = lookup_zone(lng, lat)
    height = lookup_height(lng, lat)
    coverage = lookup_lot_coverage(lng, lat)
    parking = lookup_parking_zone(lng, lat)

    if zone is None:
        return {
            "parcel": {"lat": lat, "lng": lng},
            "zoning": None,
            "note": "No zoning data found at this location (may be water or outside Toronto boundary).",
        }

    params = get_zone_params("toronto", zone.zone_code)

    max_height_m = height.height_m if height else params.get("max_height_m")
    storeys = height.storeys if height else None
    if not storeys and max_height_m:
        storeys = int(max_height_m / 3.0)

    return {
        "parcel": {
            "lat": lat,
            "lng": lng,
            "zone_code": zone.zone_code,
            "zn_string": zone.zn_string,
        },
        "zoning": {
            "zone_code": zone.zone_code,
            "zn_string": zone.zn_string,
            "max_fsi": zone.fsi_total or params.get("max_fsi"),
            "max_height_m": max_height_m,
            "storeys": storeys,
            "density": zone.density or params.get("density"),
            "lot_coverage": zone.lot_coverage or coverage,
            "stand_set": zone.stand_set,
        },
        "overlays": {
            "height": {
                "height_m": height.height_m if height else None,
                "storeys": height.storeys if height else None,
            },
            "lot_coverage": {
                "coverage_pct": coverage,
            },
            "parking_zone": {
                "zone": parking,
            },
        },
        "standards": _build_standards(params, zone.zn_string),
        "city": city.lower(),
    }


def _build_standards(params: dict, zn_string: str) -> dict:
    """Build development standards from zone params."""
    setbacks = params.get("setbacks", {})
    angular_planes = params.get("angular_planes", {})

    return {
        "setbacks": {
            "front_m": setbacks.get("front_m"),
            "rear_m": setbacks.get("rear_m"),
            "side_interior_m": setbacks.get("side_interior_m"),
            "side_exterior_m": setbacks.get("side_exterior_m"),
            "side_total_m": setbacks.get("side_total_m"),
        },
        "angular_planes": {
            "applies": bool(angular_planes),
            "plane_angle_deg": angular_planes.get("angle_deg") if angular_planes else None,
            "start_height_m": angular_planes.get("start_height_m") if angular_planes else None,
        },
        "bylaw_reference": params.get("bylaw_references", []),
    }
