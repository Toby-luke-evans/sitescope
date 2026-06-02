"""Build Toronto ParcelContext objects for full standards evaluation.

This module adapts SiteScope's lightweight zoning/parcel lookup data into the
HB-YOU-derived Toronto rules engine context. It intentionally records assumptions
used when parcel/street/programme context is unavailable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from shapely.geometry import Polygon, shape

from zoning_core.standards.toronto_rules_engine import ParcelContext
from zoning_core.standards.zn_string_parser import ZnStringParsed


@dataclass
class ParcelGeometryContext:
    """Minimal parcel geometry metrics used by the rules engine."""

    parcel_id: str = "unknown"
    lot_area_sqm: float = 0.0
    lot_frontage_m: float = 0.0
    lot_depth_m: float = 0.0
    is_corner_lot: bool = False
    num_frontages: int = 1
    defaults_used: list[str] = field(default_factory=list)


def _project_lonlat_to_local_m(coords: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Approximate WGS84 lon/lat coordinates to local metres around parcel centroid."""
    if not coords:
        return []
    mean_lat = sum(y for _, y in coords) / len(coords)
    lat_scale = 111_320.0
    lon_scale = 111_320.0 * math.cos(math.radians(mean_lat))
    lon0 = sum(x for x, _ in coords) / len(coords)
    lat0 = mean_lat
    return [((x - lon0) * lon_scale, (y - lat0) * lat_scale) for x, y in coords]


def geometry_metrics(parcel_geometry: dict[str, Any] | None, parcel_id: str = "unknown") -> ParcelGeometryContext:
    """Estimate parcel area/frontage/depth from GeoJSON polygon geometry.

    This is good enough for first-pass zoning standards. Exact frontage and depth
    should later be replaced with the HB-YOU edge-classification service.
    """
    defaults: list[str] = []
    if not parcel_geometry:
        return ParcelGeometryContext(
            parcel_id=parcel_id,
            lot_area_sqm=500.0,
            lot_frontage_m=15.0,
            lot_depth_m=30.0,
            defaults_used=[
                "Parcel geometry: unavailable; using 500 sqm / 15 m frontage / 30 m depth defaults",
            ],
        )

    try:
        geom = shape(parcel_geometry)
        if geom.is_empty:
            raise ValueError("empty geometry")
        if not geom.is_valid:
            geom = geom.buffer(0)
        if geom.geom_type == "MultiPolygon":
            poly = max(list(getattr(geom, "geoms")), key=lambda p: p.area)
        elif isinstance(geom, Polygon):
            poly = geom
        else:
            raise ValueError(f"unsupported geometry type {geom.geom_type}")
        coords = [(float(x), float(y)) for x, y, *_ in list(poly.exterior.coords)]
        local = _project_lonlat_to_local_m(coords)
        if len(local) < 4:
            raise ValueError("too few polygon coordinates")

        # Shoelace area in local metres.
        area = abs(sum(
            local[i][0] * local[(i + 1) % len(local)][1]
            - local[(i + 1) % len(local)][0] * local[i][1]
            for i in range(len(local))
        )) / 2.0

        xs = [p[0] for p in local]
        ys = [p[1] for p in local]
        bbox_w = max(xs) - min(xs)
        bbox_h = max(ys) - min(ys)
        short_side = max(min(bbox_w, bbox_h), 1.0)
        long_side = max(max(bbox_w, bbox_h), short_side)

        # Toronto lots are usually represented close to street-grid axes; this
        # approximation is transparent and marked as derived.
        defaults.append("Frontage/depth: estimated from parcel geometry bounding box")
        return ParcelGeometryContext(
            parcel_id=parcel_id,
            lot_area_sqm=round(area, 1) if area > 0 else 500.0,
            lot_frontage_m=round(short_side, 1),
            lot_depth_m=round(long_side, 1),
            is_corner_lot=False,
            num_frontages=1,
            defaults_used=defaults,
        )
    except Exception:
        return ParcelGeometryContext(
            parcel_id=parcel_id,
            lot_area_sqm=500.0,
            lot_frontage_m=15.0,
            lot_depth_m=30.0,
            defaults_used=[
                "Parcel geometry: could not be parsed; using 500 sqm / 15 m frontage / 30 m depth defaults",
            ],
        )


def build_toronto_context(
    *,
    parcel_id: str,
    zone_code: str,
    zn_string: str | None,
    parsed_zn: ZnStringParsed | None,
    max_height_m: float | None,
    lot_coverage_pct: float | None,
    parcel_geometry: dict[str, Any] | None = None,
    abutting_zones: dict[str, str | None] | None = None,
    is_corner_lot: bool | None = None,
    row_width_m: float | None = None,
    building_type: str = "detached",
    num_dwelling_units: int = 1,
) -> tuple[ParcelContext, list[str]]:
    """Construct a Toronto rules-engine context from SiteScope lookup data."""
    geom = geometry_metrics(parcel_geometry, parcel_id=parcel_id)
    defaults_used = list(geom.defaults_used)

    abut = abutting_zones or {}
    if not abut:
        defaults_used.append("Abutting zones: unknown or approximate; neighbour-specific rules may be conservative")

    if row_width_m is None:
        row_width_m = 20.0
        defaults_used.append("Street ROW width: 20.0 m default")

    if is_corner_lot is None:
        is_corner_lot = geom.is_corner_lot
        defaults_used.append("Corner lot status: assumed false unless parcel context says otherwise")

    defaults_used.append(f"Building type: {building_type} default")
    defaults_used.append(f"Dwelling units: {num_dwelling_units} default")

    zone_label_d = parsed_zn.d if parsed_zn else None
    zone_label_f = parsed_zn.f if parsed_zn else None
    zone_label_a = parsed_zn.a if parsed_zn else None
    zone_label_au = parsed_zn.au if parsed_zn else None
    zone_label_u = parsed_zn.u if parsed_zn else None
    zone_label_c = parsed_zn.c if parsed_zn else None
    zone_label_r = parsed_zn.r if parsed_zn else None
    dev_standard_set = parsed_zn.ss if parsed_zn else 0

    if parsed_zn is None and not zn_string:
        defaults_used.append("Zone label parameters: unavailable because zn_string is missing")

    ctx = ParcelContext(
        parcel_id=parcel_id,
        zone_code=zone_code,
        development_standard_set=dev_standard_set,
        lot_area_sqm=geom.lot_area_sqm,
        lot_depth_m=geom.lot_depth_m,
        lot_frontage_m=geom.lot_frontage_m,
        is_corner_lot=is_corner_lot,
        num_frontages=2 if is_corner_lot else 1,
        abutting_front_zone=abut.get("front"),
        abutting_rear_zone=abut.get("rear"),
        abutting_side_1_zone=abut.get("side_1") or abut.get("side"),
        abutting_side_2_zone=abut.get("side_2") or abut.get("side"),
        abutting_flanking_zone=abut.get("flanking"),
        front_street_row_width_m=row_width_m,
        flanking_street_row_width_m=row_width_m if is_corner_lot else None,
        zone_label_d=zone_label_d,
        zone_label_f=zone_label_f,
        zone_label_a=zone_label_a,
        zone_label_au=zone_label_au,
        zone_label_u=zone_label_u,
        zone_label_c=zone_label_c,
        zone_label_r=zone_label_r,
        overlay_height_m=max_height_m,
        overlay_lot_coverage=(lot_coverage_pct / 100.0) if lot_coverage_pct and lot_coverage_pct > 1 else lot_coverage_pct,
        overlay_fsi=zone_label_d,
        building_type=building_type,
        num_dwelling_units=num_dwelling_units,
    )
    return ctx, defaults_used
