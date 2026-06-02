"""Shared zoning response builder for search and coordinate lookup routes."""

from __future__ import annotations

from typing import Any

from shapely.geometry import shape

from zoning_core.bylaws import get_zone_params
from zoning_core.spatial import (
    is_loaded,
    lookup_height,
    lookup_lot_coverage,
    lookup_parking_zone,
    lookup_zone,
)
from zoning_core.standards import (
    build_toronto_context,
    evaluate_all_standards,
    parse_zn_string,
)


def _sample_abutting_zones(parcel_geometry: dict[str, Any] | None) -> dict[str, str | None]:
    """Approximate neighbouring zoning by sampling just outside parcel bbox.

    This is a first-pass substitute for exact parcel-edge adjacency. It is
    deliberately surfaced in `defaults_used` by the standards context builder.
    """
    if not parcel_geometry:
        return {}
    try:
        geom = shape(parcel_geometry)
        if geom.is_empty:
            return {}
        minx, miny, maxx, maxy = geom.bounds
        dx = max((maxx - minx) * 0.20, 0.000035)
        dy = max((maxy - miny) * 0.20, 0.000035)
        samples = {
            "front": ((minx + maxx) / 2, miny - dy),
            "rear": ((minx + maxx) / 2, maxy + dy),
            "side_1": (maxx + dx, (miny + maxy) / 2),
            "side_2": (minx - dx, (miny + maxy) / 2),
        }
        result: dict[str, str | None] = {}
        for edge, (lng, lat) in samples.items():
            z = lookup_zone(lng, lat)
            result[edge] = z.zone_code if z else None
        return result
    except Exception:
        return {}


def _legacy_standards(params: dict, zn_string: str | None) -> dict[str, Any]:
    """Preserve the original frontend/PDF standards shape."""
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


def build_zoning_payload(
    *,
    lat: float,
    lng: float,
    city: str = "toronto",
    parcel: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build complete zoning payload for a point/parcel."""
    base: dict[str, Any] = {
        "parcel": {"lat": lat, "lng": lng},
        "zoning": None,
        "overlays": {
            "height": {"height_m": None, "storeys": None},
            "lot_coverage": {"coverage_pct": None},
            "parking_zone": {"zone": None},
        },
        "standards": _legacy_standards({}, None),
        "development_standards": None,
        "city": city.lower(),
    }

    if parcel:
        base["parcel"].update({
            "id": parcel.get("id"),
            "address": parcel.get("address"),
            "geometry": parcel.get("geometry"),
        })

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
        base["note"] = "No zoning data found at this location (may be water or outside Toronto boundary)."
        return base

    params = get_zone_params("toronto", zone.zone_code)
    max_height_m = height.height_m if height else params.get("max_height_m")
    storeys = height.storeys if height else None
    if not storeys and max_height_m:
        storeys = int(max_height_m / 3.0)

    max_fsi = zone.fsi_total or params.get("max_fsi")
    lot_coverage = zone.lot_coverage or coverage
    abutting_zones = _sample_abutting_zones(parcel.get("geometry") if parcel else None)

    base["parcel"].update({
        "zone_code": zone.zone_code,
        "zn_string": zone.zn_string,
    })
    base["zoning"] = {
        "zone_code": zone.zone_code,
        "zn_string": zone.zn_string,
        "max_fsi": max_fsi,
        "max_height_m": max_height_m,
        "storeys": storeys,
        "density": zone.density or params.get("density"),
        "lot_coverage": lot_coverage,
        "stand_set": zone.stand_set,
        "abutting_zones": abutting_zones,
    }
    base["overlays"]["abutting_zones"] = abutting_zones

    legacy = _legacy_standards(params, zone.zn_string)
    try:
        parsed = parse_zn_string(zone.zn_string)
        ctx, defaults = build_toronto_context(
            parcel_id=str(parcel.get("id") if parcel else f"tor_{lat:.7f}_{lng:.7f}"),
            zone_code=zone.zone_code,
            zn_string=zone.zn_string,
            parsed_zn=parsed,
            max_height_m=max_height_m,
            lot_coverage_pct=lot_coverage,
            parcel_geometry=parcel.get("geometry") if parcel else None,
            abutting_zones=abutting_zones,
        )
        dev = evaluate_all_standards(ctx, defaults)
        base["development_standards"] = dev.model_dump(mode="json")
        legacy["development_standards"] = base["development_standards"]
    except Exception as exc:
        base["development_standards_error"] = str(exc)

    base["standards"] = legacy
    return base
