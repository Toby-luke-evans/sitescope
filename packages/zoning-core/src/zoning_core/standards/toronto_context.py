"""Build Toronto ParcelContext objects for full standards evaluation.

This module adapts SiteScope's lightweight zoning/parcel lookup data into the
HB-YOU-derived Toronto rules engine context. It intentionally records assumptions
used when parcel/street/programme context is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from zoning_core.standards.toronto_rules_engine import ParcelContext
from zoning_core.standards.zn_string_parser import ZnStringParsed

try:
    from geometry.parcel_context import build_parcel_spatial_context
except Exception:  # pragma: no cover - package path fallback for isolated installs
    build_parcel_spatial_context = None


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


def geometry_metrics(
    parcel_geometry: dict[str, Any] | None,
    parcel_id: str = "unknown",
    nearby_parcel_geometries: list[dict[str, Any]] | None = None,
) -> ParcelGeometryContext:
    """Calculate parcel area/frontage/depth/corner status from parcel topology."""
    if build_parcel_spatial_context is None:
        return ParcelGeometryContext(
            parcel_id=parcel_id,
            defaults_used=["Parcel spatial engine unavailable; parcel geometry metrics could not be calculated"],
        )

    spatial = build_parcel_spatial_context(
        parcel_geometry,
        nearby_parcel_geometries=nearby_parcel_geometries,
    )
    defaults: list[str] = []
    for warning in spatial.warnings:
        defaults.append(warning)
    if spatial.frontage_source.startswith("estimated_"):
        defaults.append(f"Frontage/depth source: {spatial.frontage_source}")
    elif spatial.frontage_source != "unavailable":
        defaults.append(f"Frontage source: {spatial.frontage_source}")
    if spatial.corner_source == "unavailable_no_neighbour_topology":
        defaults.append("Corner lot status: unavailable from parcel topology; not assumed")
    elif spatial.corner_source != "unavailable":
        defaults.append(f"Corner lot status source: {spatial.corner_source}")
    if spatial.row_width_source == "unavailable":
        if not any("Street ROW width" in item for item in defaults):
            defaults.append("Street ROW width: unavailable from parcel/ROW topology; not defaulted")
    else:
        defaults.append(f"Street ROW width source: {spatial.row_width_source}")

    return ParcelGeometryContext(
        parcel_id=parcel_id,
        lot_area_sqm=float(spatial.lot_area_sqm or 0.0),
        lot_frontage_m=float(spatial.lot_frontage_m or 0.0),
        lot_depth_m=float(spatial.lot_depth_m or 0.0),
        is_corner_lot=bool(spatial.is_corner_lot) if spatial.is_corner_lot is not None else False,
        num_frontages=int(spatial.num_frontages or (2 if spatial.is_corner_lot else 1)),
        defaults_used=defaults,
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
    nearby_parcel_geometries: list[dict[str, Any]] | None = None,
    abutting_zones: dict[str, str | None] | None = None,
    is_corner_lot: bool | None = None,
    row_width_m: float | None = None,
    building_type: str = "detached",
    num_dwelling_units: int = 0,
) -> tuple[ParcelContext, list[str]]:
    """Construct a Toronto rules-engine context from SiteScope lookup data."""
    geom = geometry_metrics(parcel_geometry, parcel_id=parcel_id, nearby_parcel_geometries=nearby_parcel_geometries)
    defaults_used = list(geom.defaults_used)

    abut = abutting_zones or {}
    if not abut:
        defaults_used.append("Abutting zones: unavailable or approximate; neighbour-specific rules may need exact adjacency verification")

    if row_width_m is None:
        # Keep the internal value non-null for legacy rule functions, but do not
        # label it as a defaulted fact. ROW-dependent outputs are flagged above
        # and should be treated as data gaps until a ROW layer/opposite-parcel
        # estimate is available.
        row_width_m = 0.0

    if is_corner_lot is None:
        is_corner_lot = geom.is_corner_lot

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
