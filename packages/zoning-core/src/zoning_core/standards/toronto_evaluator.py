"""Evaluate all Toronto rules engine functions for a ParcelContext.

Takes a populated ParcelContext and calls every rules_engine function,
organizing results by category (A–Q). Functions that return None (not
applicable) are omitted. Categories with no applicable standards are
omitted entirely.

Usage:
    from app.plugins.toronto.context_builder import build_parcel_context
    from app.services.rules_evaluation_service import evaluate_all_standards

    ctx, defaults = build_parcel_context(lot_data, parsed_zn)
    dev_standards = evaluate_all_standards(ctx, defaults)
"""

from __future__ import annotations

import logging
from typing import Any

from zoning_core.standards import toronto_rules_engine as re
from zoning_core.standards.toronto_rules_engine import ParcelContext
from zoning_core.standards.models import (
    DevelopmentStandardCategory,
    DevelopmentStandards,
    DevelopmentStandardValue,
)

logger = logging.getLogger(__name__)


def _v(
    value: Any,
    unit: str | None = None,
    bylaw_ref: str | None = None,
    is_default: bool = False,
    note: str | None = None,
) -> DevelopmentStandardValue:
    """Shorthand constructor for a development standard value."""
    return DevelopmentStandardValue(
        value=value,
        unit=unit,
        bylaw_ref=bylaw_ref,
        is_default=is_default,
        note=note,
    )


def _category(
    cat_id: str,
    cat_name: str,
    standards: dict[str, DevelopmentStandardValue | None],
) -> DevelopmentStandardCategory | None:
    """Build a category, filtering out None values. Returns None if empty."""
    filtered = {k: v for k, v in standards.items() if v is not None}
    if not filtered:
        return None
    return DevelopmentStandardCategory(
        category_id=cat_id,
        category_name=cat_name,
        standards=filtered,
    )


def _bylaw_ref_for_zone(zone: str, refs: dict[str, str]) -> str | None:
    """Look up bylaw reference based on zone code."""
    return refs.get(zone, refs.get("default"))


# ── Bylaw reference mappings by zone ───────────────────────────
# These map zone codes to the specific bylaw section for each function.
# For brevity, only the chapter section prefix is given.

_HEIGHT_REFS: dict[str, str] = {
    "R": "10.10.40.10", "RD": "10.20.40.10", "RS": "10.40.40.10",
    "RT": "10.60.40.10", "RM": "10.80.40.10", "RA": "15.10.40.10",
    "RAC": "15.10.40.10", "CR": "40.10.40.10", "CRE": "40.10.40.10",
    "CR-T": "40.10.40.10", "default": "10.10.40.10",
}

_SETBACK_REFS: dict[str, str] = {
    "R": "10.10.40.70", "RD": "10.20.40.70", "RS": "10.40.40.70",
    "RT": "10.60.40.70", "RM": "10.80.40.70", "RA": "15.10.40.70",
    "RAC": "15.10.40.70", "CR": "40.10.40.70", "CRE": "40.10.40.70",
    "CR-T": "40.10.40.70", "default": "10.10.40.70",
}

_LOT_REFS: dict[str, str] = {
    "R": "10.10.30", "RD": "10.20.30", "RS": "10.40.30",
    "RT": "10.60.30", "RM": "10.80.30", "RA": "15.10.30",
    "RAC": "15.10.30", "CR": "40.10.30", "CRE": "40.10.30",
    "CR-T": "40.10.30", "default": "10.10.30",
}

_FSI_REFS: dict[str, str] = {
    "R": "10.10.40.40", "RD": "10.20.40.40", "RS": "10.40.40.40",
    "RT": "10.60.40.40", "RM": "10.80.40.40", "RA": "15.10.40.40",
    "RAC": "15.10.40.40", "CR": "40.10.40.40", "CRE": "40.10.40.40",
    "CR-T": "40.10.40.40", "default": "10.10.40.40",
}


def evaluate_all_standards(
    ctx: ParcelContext,
    defaults_used: list[str] | None = None,
) -> DevelopmentStandards:
    """Evaluate all rules engine functions and return structured results.

    Args:
        ctx: Fully populated ParcelContext.
        defaults_used: List of default assumptions from context_builder.

    Returns:
        DevelopmentStandards with all applicable categories.
    """
    ss = ctx.development_standard_set
    zone = ctx.zone_code
    ht = re.max_height(ctx)

    categories: list[DevelopmentStandardCategory] = []

    # ── A. Lot Requirements ────────────────────────────────────
    lot_ref = _bylaw_ref_for_zone(zone, _LOT_REFS)
    cat = _category("A", "Lot Requirements", {
        "min_lot_frontage": _v(
            re.min_lot_frontage(ctx), "m", f"{lot_ref}.20" if lot_ref else None,
        ),
        "min_lot_area": _v(
            re.min_lot_area(ctx), "sqm", f"{lot_ref}.10" if lot_ref else None,
        ),
        "max_lot_coverage": _v(
            re.max_lot_coverage(ctx), "fraction", f"{lot_ref}.40" if lot_ref else None,
        ),
    })
    if cat:
        categories.append(cat)

    # ── B. Height ──────────────────────────────────────────────
    ht_ref = _bylaw_ref_for_zone(zone, _HEIGHT_REFS)
    height_standards: dict[str, DevelopmentStandardValue | None] = {
        "max_height": _v(ht, "m", ht_ref),
        "max_main_wall_height": _v(
            re.max_main_wall_height(ctx), "m", ht_ref,
        ),
    }

    flat_roof = re.flat_roof_main_wall_exception(ctx)
    if flat_roof is not None:
        height_standards["flat_roof_main_wall_exception"] = _v(
            flat_roof, note="Flat roof exception rules",
        )

    min_ht = re.min_height(ctx)
    if min_ht > 0:
        height_standards["min_height"] = _v(min_ht, "m", "40.10.40.10(4)")

    min_st = re.min_storeys(ctx)
    if min_st > 0:
        height_standards["min_storeys"] = _v(min_st, "storeys", "40.10.40.10(4)")

    max_st = re.max_storeys(ctx)
    if max_st is not None:
        height_standards["max_storeys"] = _v(max_st, "storeys", ht_ref)

    min_1st = re.min_first_storey_height(ctx)
    if min_1st > 0:
        height_standards["min_first_storey_height"] = _v(
            min_1st, "m", "40.10.40.10(5)",
        )

    height_standards["rooftop_exceedance_rules"] = _v(
        re.rooftop_exceedance_rules(ctx),
        note="Max height exceedances by element type",
    )

    cat = _category("B", "Height", height_standards)
    if cat:
        categories.append(cat)

    # ── C. Floor Area / Density ────────────────────────────────
    fsi_ref = _bylaw_ref_for_zone(zone, _FSI_REFS)
    floor_area_standards: dict[str, DevelopmentStandardValue | None] = {}

    max_fsi = re.max_fsi_total(ctx)
    if max_fsi is not None:
        floor_area_standards["max_fsi_total"] = _v(max_fsi, None, fsi_ref)
    else:
        floor_area_standards["max_fsi_total"] = _v(
            "Exempt", None, fsi_ref,
            note="Multiplex/RM — no FSI limit",
        )

    max_fsi_c = re.max_fsi_commercial(ctx)
    if max_fsi_c is not None:
        floor_area_standards["max_fsi_commercial"] = _v(
            max_fsi_c, None, fsi_ref, note="Non-residential FSI cap",
        )

    max_fsi_r = re.max_fsi_residential(ctx)
    if max_fsi_r is not None:
        floor_area_standards["max_fsi_residential"] = _v(
            max_fsi_r, None, fsi_ref, note="Residential FSI cap",
        )

    transit_bonus = re.transit_corridor_bonus_fsi(ctx)
    if transit_bonus > 0:
        floor_area_standards["transit_corridor_bonus_fsi"] = _v(
            transit_bonus, None, note="CR-T transit corridor bonus",
        )

    floor_area_standards["gfa_exclusions"] = _v(
        re.gfa_calculation_exclusions(ctx),
        note="Floor area items excluded from FSI calculation",
    )

    cat = _category("C", "Floor Area / Density", floor_area_standards)
    if cat:
        categories.append(cat)

    # ── D. Setbacks ────────────────────────────────────────────
    sb_ref = _bylaw_ref_for_zone(zone, _SETBACK_REFS)
    setback_standards: dict[str, DevelopmentStandardValue | None] = {
        "front_setback": _v(re.front_setback(ctx, ss), "m", sb_ref),
    }

    front_max = re.front_setback_maximum(ctx, ss)
    if front_max is not None:
        setback_standards["front_setback_maximum"] = _v(
            front_max, "m", sb_ref,
            note="75% of main wall must be within this distance",
        )

    setback_standards["rear_setback"] = _v(
        re.rear_setback(ctx, ss, ctx.abutting_rear_zone, ht), "m", sb_ref,
    )

    # Side setbacks — evaluate for each side
    setback_standards["side_1_setback"] = _v(
        re.side_setback(ctx, ss, ctx.abutting_side_1_zone, ctx.has_windows_on_side_1, ht),
        "m", sb_ref,
    )
    setback_standards["side_2_setback"] = _v(
        re.side_setback(ctx, ss, ctx.abutting_side_2_zone, ctx.has_windows_on_side_2, ht),
        "m", sb_ref,
    )

    # Flanking setback (corner lots only)
    if ctx.is_corner_lot:
        setback_standards["flanking_setback"] = _v(
            re.flanking_setback(ctx, ss, ctx.abutting_flanking_zone), "m", sb_ref,
        )

    setback_standards["lane_setback"] = _v(
        re.lane_setback(ctx), "m", "10.5.40.70(2)",
        note="Min distance from lane centreline",
    )

    res_1st = re.residential_first_storey_front_setback(ctx, ss)
    if res_1st is not None:
        setback_standards["residential_first_storey_front_setback"] = _v(
            res_1st, "m", "40.10.40.70(4)",
            note="Dwelling units on first storey",
        )

    cat = _category("D", "Setbacks", setback_standards)
    if cat:
        categories.append(cat)

    # ── E. Angular Planes ──────────────────────────────────────
    angular_standards: dict[str, DevelopmentStandardValue | None] = {}

    rear_ap = re.rear_angular_plane(ctx, ss, ctx.abutting_rear_zone)
    if rear_ap is not None:
        angular_standards["rear_angular_plane"] = _v(
            rear_ap, None, rear_ap.get("bylaw_ref"),
            note=f"Start {rear_ap['start_height_m']}m, {rear_ap['angle_deg']}°",
        )
    else:
        angular_standards["rear_angular_plane"] = _v(
            "None", None, None,
            note="No rear angular plane applies to this zone/context",
        )

    side_ap = re.side_angular_plane(ctx, ss, ctx.abutting_side_1_zone)
    # Side AP is always None in 569-2013, but include for completeness
    if side_ap is not None:
        angular_standards["side_angular_plane"] = _v(side_ap)

    street_ap = re.street_facing_angular_plane(ctx, ss)
    if street_ap is not None:
        angular_standards["street_facing_angular_plane"] = _v(
            street_ap, None, street_ap.get("bylaw_ref"),
            note=f"Start {street_ap['start_height_m']:.1f}m, {street_ap['angle_deg']}°",
        )

    angular_standards["encroachments_can_penetrate"] = _v(
        re.angular_plane_encroachment_allowed(ctx), None, None,
        note="Whether building encroachments may penetrate angular planes",
    )

    cat = _category("E", "Angular Planes", angular_standards)
    if cat:
        categories.append(cat)

    # ── F. Building Separation ─────────────────────────────────
    sep_standards: dict[str, DevelopmentStandardValue | None] = {}

    w2w = re.building_separation_window_to_window(ctx, ht, ht)
    if w2w > 0:
        sep_standards["window_to_window"] = _v(w2w, "m", note="Between windowed walls on same lot")

    w2b = re.building_separation_window_to_blank(ctx, ht, ht)
    if w2b > 0:
        sep_standards["window_to_blank_wall"] = _v(w2b, "m", note="Windowed wall to blank wall")

    b2b = re.building_separation_blank_to_blank(ctx)
    if b2b > 0:
        sep_standards["blank_to_blank"] = _v(b2b, "m")

    # Zone boundary separation — check all abutting zones
    for edge, abut_zone in [
        ("rear", ctx.abutting_rear_zone),
        ("side_1", ctx.abutting_side_1_zone),
        ("side_2", ctx.abutting_side_2_zone),
    ]:
        zbs = re.zone_boundary_separation(ctx, abut_zone)
        if zbs > 0:
            sep_standards[f"zone_boundary_{edge}"] = _v(
                zbs, "m", note=f"From {abut_zone} zone boundary",
            )

    cat = _category("F", "Building Separation", sep_standards)
    if cat:
        categories.append(cat)

    # ── G. Encroachments ───────────────────────────────────────
    encr_standards: dict[str, DevelopmentStandardValue | None] = {
        "balcony": _v(re.balcony_encroachment(ctx), note="Deck/porch/balcony"),
        "canopy": _v(re.canopy_encroachment(ctx)),
        "stairs": _v(re.stairs_encroachment(ctx)),
        "bay_window": _v(re.bay_window_encroachment(ctx)),
        "roof_projection": _v(re.roof_projection_encroachment(ctx)),
        "architectural_feature": _v(re.architectural_feature_encroachment(ctx)),
        "cladding": _v(
            re.cladding_encroachment(0.0), "m",
            note="Insulation/cladding (building 5+ years old: 0.15m)",
            is_default=True,
        ),
        "equipment": _v(re.equipment_encroachment(ctx), note="A/C units"),
    }
    cat = _category("G", "Encroachments", encr_standards)
    if cat:
        categories.append(cat)

    # ── H. Amenity Space ───────────────────────────────────────
    amenity_standards: dict[str, DevelopmentStandardValue | None] = {}

    indoor = re.indoor_amenity_space_sqm(ctx)
    if indoor > 0:
        amenity_standards["indoor_amenity_space"] = _v(indoor, "sqm")
    outdoor = re.outdoor_amenity_space_sqm(ctx)
    if outdoor > 0:
        amenity_standards["outdoor_amenity_space"] = _v(outdoor, "sqm")
    adj = re.outdoor_amenity_adjacency_min_sqm(ctx)
    if adj > 0:
        amenity_standards["outdoor_adjacency_min"] = _v(
            adj, "sqm", note="Min outdoor amenity adjoining indoor",
        )
    amenity_standards["green_roof_amenity_max_fraction"] = _v(
        re.green_roof_amenity_max_fraction(), "fraction",
        note="Max outdoor amenity as green roof",
    )

    nr_amenity = re.non_residential_outdoor_amenity(ctx)
    if nr_amenity is not None:
        amenity_standards["non_residential_outdoor_amenity"] = _v(
            nr_amenity, note="CR SS1 non-residential outdoor amenity rates",
        )

    cat = _category("H", "Amenity Space", amenity_standards)
    if cat:
        categories.append(cat)

    # ── I. Landscaping ─────────────────────────────────────────
    land_standards: dict[str, DevelopmentStandardValue | None] = {}

    # Check landscaping strip for each abutting edge
    for edge, abut_zone in [
        ("rear", ctx.abutting_rear_zone),
        ("side_1", ctx.abutting_side_1_zone),
        ("side_2", ctx.abutting_side_2_zone),
    ]:
        lsw = re.landscaping_strip_width(ctx, abut_zone)
        if lsw > 0:
            land_standards[f"landscaping_strip_{edge}"] = _v(
                lsw, "m", note=f"Landscape buffer toward {abut_zone or 'unknown'}",
            )

    land_standards["soft_landscaping_rates"] = _v(
        re.soft_landscaping_rates(ctx), note="Yard landscaping requirements",
    )

    # Check fencing for each abutting edge
    for edge, abut_zone in [
        ("rear", ctx.abutting_rear_zone),
        ("side_1", ctx.abutting_side_1_zone),
        ("side_2", ctx.abutting_side_2_zone),
    ]:
        if re.fencing_required(ctx, abut_zone):
            land_standards[f"fencing_required_{edge}"] = _v(
                True, note=f"Fencing required toward {abut_zone}",
            )

    cat = _category("I", "Landscaping", land_standards)
    if cat:
        categories.append(cat)

    # ── J. Parking ─────────────────────────────────────────────
    park_standards: dict[str, DevelopmentStandardValue | None] = {
        "location_restrictions": _v(
            re.parking_location_restrictions(ctx),
            note="Where surface parking is prohibited",
        ),
        "setback_from_lot_lines": _v(
            re.parking_setback_from_lot_lines(ctx), "m",
        ),
    }

    # Check parking setback from residential for each edge
    for edge, abut_zone in [
        ("rear", ctx.abutting_rear_zone),
        ("side_1", ctx.abutting_side_1_zone),
    ]:
        psb = re.parking_setback_from_residential_zones(ctx, abut_zone)
        if psb > 0:
            park_standards[f"parking_setback_residential_{edge}"] = _v(
                psb, "m", note=f"Parking setback from {abut_zone}",
            )

    cat = _category("J", "Parking", park_standards)
    if cat:
        categories.append(cat)

    # ── K. Loading ─────────────────────────────────────────────
    load_standards: dict[str, DevelopmentStandardValue | None] = {
        "location_restrictions": _v(
            re.loading_location_restrictions(ctx),
            note="Where loading spaces are prohibited",
        ),
        "access_requirements": _v(
            re.loading_access_requirements(ctx),
            note="Loading access rules",
        ),
    }

    mixed_sub = re.mixed_use_loading_substitution(ctx)
    if mixed_sub is not None:
        load_standards["mixed_use_substitution"] = _v(
            mixed_sub, note="Type G → Type A/B substitution",
        )

    cat = _category("K", "Loading", load_standards)
    if cat:
        categories.append(cat)

    # ── L. Vehicle Access ──────────────────────────────────────
    access_standards: dict[str, DevelopmentStandardValue | None] = {
        "must_access_from_lane": _v(
            re.must_access_from_lane(ctx),
            note="Vehicle access must use lane if available",
        ),
        "max_access_points": _v(
            re.max_vehicle_access_points(ctx),
            note=f"Frontage {'>' if ctx.lot_frontage_m > 18 else '<='} 18m",
        ),
    }

    if ctx.is_corner_lot:
        access_standards["access_from_non_major_street"] = _v(
            re.corner_lot_access_from_non_major_street(ctx),
            note="Corner lot: access from flanking (non-major) street",
        )

    cat = _category("L", "Vehicle Access", access_standards)
    if cat:
        categories.append(cat)

    # ── M. Mixed-Use Rules ─────────────────────────────────────
    mixed_standards: dict[str, DevelopmentStandardValue | None] = {}

    if re.residential_must_be_above_commercial(ctx):
        mixed_standards["residential_above_commercial"] = _v(
            True, None, "40.10.40.1(1)",
            note="Residential uses must be above non-residential",
        )

    gf_level = re.ground_floor_non_residential_level_m(ctx)
    if gf_level is not None:
        mixed_standards["ground_floor_level"] = _v(
            gf_level, "m", "40.10.40.1(2)",
            note="Non-residential floor within this distance of grade",
        )

    ramp_slope = re.pedestrian_access_ramp_max_slope(ctx)
    if ramp_slope is not None:
        mixed_standards["pedestrian_ramp_max_slope"] = _v(
            f"1:{ramp_slope:.0f}", None, "40.10.40.1(3)",
        )

    if ctx.is_corner_lot:
        mixed_standards["corner_ground_floor_residential"] = _v(
            re.corner_lot_ground_floor_residential_allowed(ctx),
            None, "40.10.40.1(4)",
            note="Ground-floor residential on non-major flanking street",
        )

    cat = _category("M", "Mixed-Use Rules", mixed_standards)
    if cat:
        categories.append(cat)

    # ── N. Waste Storage ───────────────────────────────────────
    waste_standards: dict[str, DevelopmentStandardValue | None] = {
        "must_be_enclosed": _v(re.waste_must_be_enclosed(ctx)),
        "location_restrictions": _v(re.waste_location_restrictions(ctx)),
    }

    wsb = re.waste_setback_from_residential_m(ctx)
    if wsb > 0:
        waste_standards["setback_from_residential"] = _v(
            wsb, "m", note="From R/RA/OS lot lines",
        )

    cat = _category("N", "Waste Storage", waste_standards)
    if cat:
        categories.append(cat)

    # ── O. Energy Devices ──────────────────────────────────────
    energy_standards: dict[str, DevelopmentStandardValue | None] = {
        "solar_height_exceedance": _v(
            re.solar_device_height_exceedance_m(ctx), "m",
            note="Solar panels may exceed max height by this amount",
        ),
        "wind_device_rules": _v(re.wind_device_rules(ctx)),
        "geo_energy_rules": _v(re.geo_energy_rules(ctx)),
        "cogeneration_rules": _v(re.cogeneration_rules(ctx)),
    }
    cat = _category("O", "Energy Devices", energy_standards)
    if cat:
        categories.append(cat)

    # ── P. Tall Building Overlay ───────────────────────────────
    tall_standards: dict[str, DevelopmentStandardValue | None] = {}

    is_tall = re.is_tall_building(ctx)
    tall_standards["is_tall_building"] = _v(
        is_tall, None, "600.10.10(1)",
        note=f"Height {'>' if is_tall else '<='} 36m",
    )

    if is_tall:
        tall_standards["tower_definition"] = _v(
            re.tower_definition(), note="Tower = above 24m, max 750 sqm/floor avg",
        )
        tall_standards["tower_setback"] = _v(
            re.tower_setback_m(ctx), "m", "600.10.10(1)(A)",
            note="Tower portion setback from side/rear lot lines",
        )
        tall_standards["tower_separation"] = _v(
            re.tower_separation_m(ctx), "m", "600.10.10(1)(B)",
            note="Between tower portions on same or adjacent lots",
        )
        tall_standards["tower_encroachment_angular_plane"] = _v(
            re.tower_encroachments_cannot_penetrate_angular_planes(),
            None, "600.10.10(1)(F)",
            note="Encroachments must not penetrate angular planes",
        )

    cat = _category("P", "Tall Building Overlay", tall_standards)
    if cat:
        categories.append(cat)

    # ── Q. Category-Level Rules ────────────────────────────────
    cat_rules: dict[str, DevelopmentStandardValue | None] = {}

    if re.front_yard_averaging_allowed(ctx):
        cat_rules["front_yard_averaging"] = _v(
            True, None, "10.5.40.70(1)",
            note="Front setback may be averaged with abutting buildings",
        )

    mplex = re.multiplex_conversion_exemptions(ctx)
    if mplex is not None:
        cat_rules["multiplex_conversion_exemptions"] = _v(
            mplex, note="Pre-2023-05-15 building conversion exemptions",
        )

    cr_lane = re.cr_category_lane_setback(ctx)
    if cr_lane is not None:
        cat_rules["cr_lane_setback"] = _v(
            cr_lane, "m", "40.5.40.70",
            note="Min distance from lane centreline",
        )

    cr_ht = re.cr_category_height_measurement(ctx)
    if cr_ht is not None:
        cat_rules["cr_height_measurement"] = _v(
            cr_ht, None, "40.5.40.10(1)",
        )

    cat = _category("Q", "Category-Level Rules", cat_rules)
    if cat:
        categories.append(cat)

    # ── Build context summary ──────────────────────────────────
    context_summary: dict[str, Any] = {
        "zone_code": zone,
        "development_standard_set": ss if ss > 0 else None,
        "lot_area_sqm": round(ctx.lot_area_sqm, 1),
        "lot_frontage_m": round(ctx.lot_frontage_m, 1),
        "lot_depth_m": round(ctx.lot_depth_m, 1),
        "is_corner_lot": ctx.is_corner_lot,
        "num_frontages": ctx.num_frontages,
        "abutting_rear_zone": ctx.abutting_rear_zone,
        "front_street_row_width_m": ctx.front_street_row_width_m if ctx.front_street_row_width_m > 0 else None,
    }

    return DevelopmentStandards(
        categories=categories,
        defaults_used=defaults_used or [],
        context_summary=context_summary,
    )
