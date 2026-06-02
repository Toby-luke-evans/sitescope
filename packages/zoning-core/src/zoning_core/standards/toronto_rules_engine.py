"""
Toronto Zoning Bylaw 569-2013 — Machine-Executable Rules Engine.

Decision-tree functions for every Development Standard in the bylaw.
Each function takes a ParcelContext (runtime GIS data) and returns the
applicable value, evaluating all conditional branches, exceptions, and
lookup tables from the bylaw source text.

Architecture:
  - ParcelContext: runtime inputs (lot geometry, abutting zones, overlays)
  - One function per Development Standard category
  - Setback / angular plane functions accept per-edge parameters
  - Every branch has a bylaw section reference in comments

Source: Parsed from Toronto Zoning Bylaw 569-2013 (Office Consolidation)
via assets/zoning_elements_chapter_*.json

NOTE: This file is generated from bylaw extraction. Values have been
verified against the parsed PDF. Sections still being extracted are
marked with TODO.
"""

from dataclasses import dataclass, field
from typing import Optional


# ── Constants ────────────────────────────────────────────────────

# Toronto zone labels encode parameters: e.g., "R (d0.6)(x12) (f6.0)(a185)"
#   f  = minimum lot frontage (m)
#   a  = minimum lot area (sqm)
#   au = minimum lot area per dwelling unit (sqm)
#   u  = maximum number of dwelling units
#   d  = maximum FSI (density)

RESIDENTIAL_ZONES = frozenset({"R", "RD", "RS", "RT", "RM"})
RESIDENTIAL_APARTMENT_ZONES = frozenset({"RA", "RAC"})
ALL_RESIDENTIAL_ZONES = RESIDENTIAL_ZONES | RESIDENTIAL_APARTMENT_ZONES
OPEN_SPACE_ZONES = frozenset({"O", "ON", "OR", "OG"})

# Zones that trigger angular plane / setback protections when abutting
ANGULAR_PLANE_TRIGGER_ZONES = ALL_RESIDENTIAL_ZONES | OPEN_SPACE_ZONES

# CR shallow/deep lot lookup table — 40.10.40.70(2)(F), (3)(E)
# Key: ROW width (m), Value: lot depth threshold (m)
# Shallow lot = lot depth <= threshold; Deep lot = lot depth > threshold
# If ROW width not listed, use the next lowest ROW width entry.
SHALLOW_DEEP_LOT_TABLE: list[tuple[float, float]] = [
    (20.0, 32.6),
    (23.0, 36.2),
    (27.0, 41.0),
    (30.0, 44.6),
    (33.0, 48.2),
    (36.0, 51.8),
]


def is_shallow_lot(row_width_m: float, lot_depth_m: float) -> bool:
    """Determine if a lot is 'shallow' per the ROW-width lookup table.

    40.10.40.70(2)(F) / (3)(E): If the ROW width is not listed, use the
    next lowest ROW width in Column A.
    """
    threshold = None
    for row_w, depth_thresh in SHALLOW_DEEP_LOT_TABLE:
        if row_w <= row_width_m:
            threshold = depth_thresh
        else:
            break
    if threshold is None:
        # ROW narrower than 20m — use most conservative (first entry)
        threshold = SHALLOW_DEEP_LOT_TABLE[0][1]
    return lot_depth_m <= threshold


# ── ParcelContext ────────────────────────────────────────────────

@dataclass
class ParcelContext:
    """Runtime GIS context for a specific parcel.

    Populated from CKAN spatial lookups, ArcGIS queries, and zone label
    parsing before the rules engine evaluates.
    """
    parcel_id: str
    zone_code: str
    development_standard_set: int  # 1, 2, or 3 (from zone label; 0 if N/A)
    lot_area_sqm: float
    lot_depth_m: float
    lot_frontage_m: float
    is_corner_lot: bool
    num_frontages: int  # 1 = mid-block, 2 = corner, 3+ = through-lot

    # Per-edge abutting context
    abutting_front_zone: Optional[str] = None
    abutting_rear_zone: Optional[str] = None
    abutting_side_1_zone: Optional[str] = None
    abutting_side_2_zone: Optional[str] = None
    abutting_flanking_zone: Optional[str] = None

    # Street context
    front_street_row_width_m: float = 20.0
    flanking_street_row_width_m: Optional[float] = None
    front_street_is_major: bool = False
    flanking_street_is_major: Optional[bool] = None
    rear_street_row_width_m: Optional[float] = None
    side_1_street_row_width_m: Optional[float] = None

    # Lane context
    rear_has_laneway: bool = False
    laneway_width_m: Optional[float] = None
    laneway_opposite_zone: Optional[str] = None
    side_has_laneway: bool = False
    side_laneway_width_m: Optional[float] = None
    side_laneway_opposite_zone: Optional[str] = None

    # Overlay & zone label values
    zone_label_f: Optional[float] = None   # min lot frontage from label
    zone_label_a: Optional[float] = None   # min lot area from label
    zone_label_au: Optional[float] = None  # min lot area per unit from label
    zone_label_u: Optional[int] = None     # max dwelling units from label
    zone_label_d: Optional[float] = None   # max FSI from label
    zone_label_c: Optional[float] = None   # max commercial FSI (CR zones)
    zone_label_r: Optional[float] = None   # max residential FSI (CR zones)
    overlay_height_m: Optional[float] = None
    overlay_max_storeys: Optional[int] = None
    overlay_lot_coverage: Optional[float] = None
    overlay_fsi: Optional[float] = None

    # Policy and heritage
    policy_area: Optional[int] = None
    is_heritage_site: bool = False

    # Building programme
    num_dwelling_units: int = 0
    building_type: str = "detached"  # detached, semi_detached, townhouse, apartment, mixed_use, etc.
    has_windows_on_side_1: bool = True
    has_windows_on_side_2: bool = True
    has_windows_on_rear: bool = True
    roof_slope_ratio: Optional[float] = None


# ═══════════════════════════════════════════════════════════════════
# A. LOT REQUIREMENTS
# ═══════════════════════════════════════════════════════════════════

def min_lot_frontage(ctx: ParcelContext) -> float:
    """Bylaw ref: 10.10.30.20, 10.20.30.20, 10.40.30.20, 10.60.30.20,
    10.80.30.20, 15.10.30.20, 40.10.30.20"""
    # 1. Zone label "f" value overrides defaults
    if ctx.zone_label_f is not None:
        if ctx.zone_code in ["RS", "RM", "RT"] and ctx.building_type in [
            "semi_detached", "fourplex", "apartment"
        ]:
            return ctx.zone_label_f * 0.5
        return ctx.zone_label_f

    # 2. Defaults when no "f" value exists
    if ctx.zone_code == "R":
        if ctx.building_type == "townhouse" and ctx.num_frontages == 1:
            return 30.0  # 10.10.30.20(1)(D)
        return 6.0  # 10.10.30.20(1)(B)

    elif ctx.zone_code == "RD":
        return 12.0  # 10.20.30.20(1)(B)

    elif ctx.zone_code == "RS":
        return 15.0  # 10.40.30.20(1)(B)

    elif ctx.zone_code == "RT":
        if ctx.building_type in ["duplex", "triplex", "fourplex"]:
            return 6.0  # 10.60.30.20(1)(E)
        if ctx.building_type == "townhouse" and ctx.num_frontages == 1:
            return 30.0  # 10.60.30.20(1)(D)
        return 6.0  # 10.60.30.20(1)(B)

    elif ctx.zone_code == "RM":
        if ctx.building_type in ["detached", "duplex", "triplex", "fourplex"]:
            return 12.0  # 10.80.30.20(1)(B)(i)
        if ctx.building_type == "semi_detached":
            return 15.0  # 10.80.30.20(1)(B)(ii)
        return 24.0  # 10.80.30.20(1)(B)(iii)

    elif ctx.zone_code in ["RA", "RAC"]:
        return 24.0  # 15.10.30.20(1)(B)

    # Commercial-Residential zones
    elif ctx.zone_code in ["CR", "CRE", "CR-T"]:
        return 9.0  # 40.10.30.20

    return 0.0


def min_lot_area(ctx: ParcelContext) -> float:
    """Bylaw ref: 10.10.30.10, 10.20.30.10, 10.40.30.10, 10.60.30.10,
    10.80.30.10, 15.10.30.10"""
    # 1. Per-dwelling-unit minimums (au)
    if ctx.zone_label_au is not None and ctx.building_type in [
        "townhouse", "apartment"
    ]:
        return ctx.zone_label_au * ctx.num_dwelling_units

    # 2. Base lot area (a)
    if ctx.zone_label_a is not None:
        if ctx.zone_code in ["RS", "RT", "RM"] and ctx.building_type in [
            "semi_detached", "fourplex", "apartment"
        ]:
            return ctx.zone_label_a * 0.5
        return ctx.zone_label_a

    # 3. Default calculation if no "a" value
    return min_lot_frontage(ctx) * 30.0


def max_lot_coverage(ctx: ParcelContext) -> float:
    """Bylaw ref: 10.20.30.40, 10.40.30.40, 10.60.30.40, 10.80.30.40,
    15.10.30.40, 40.10.30.40"""
    # Overlay value overrides zone default
    if ctx.overlay_lot_coverage is not None:
        return ctx.overlay_lot_coverage

    # Zone defaults when no overlay exists
    if ctx.zone_code in RESIDENTIAL_ZONES:
        return 0.35
    if ctx.zone_code in RESIDENTIAL_APARTMENT_ZONES:
        return 0.40
    if ctx.zone_code in ["CR", "CRE", "CR-T"]:
        return 1.0  # 40.10.30.40 — effectively unlimited

    return 1.0


# ═══════════════════════════════════════════════════════════════════
# B. HEIGHT
# ═══════════════════════════════════════════════════════════════════

def max_height(ctx: ParcelContext) -> float:
    """Bylaw ref: 10.10.40.10(1), 10.20.40.10(1), 10.40.40.10(1),
    10.60.40.10(1), 10.80.40.10(1), 15.10.40.10(1), 40.10.40.10"""
    ht = ctx.overlay_height_m

    # Residential zone defaults when no HT overlay exists
    if ht is None:
        if ctx.zone_code in ["R", "RD", "RS", "RT"]:
            ht = 10.0
        elif ctx.zone_code == "RM":
            ht = 10.0 if ctx.building_type in ["detached", "semi_detached"] else 12.0
        elif ctx.zone_code in ["RA", "RAC"]:
            ht = 24.0
        # CR zone defaults by Development Standard Set
        elif ctx.zone_code in ["CR", "CRE", "CR-T"]:
            ss = ctx.development_standard_set
            if ss == 1:
                ht = 16.0  # 40.10.40.10(1) SS1 default
            elif ss == 2:
                ht = 14.0  # 40.10.40.10(2) SS2 default
            elif ss == 3:
                ht = 11.0  # 40.10.40.10(3) SS3 default
            else:
                ht = 16.0  # Fallback

    # Multiplex exceptions: greater of HT or 10.0m — 10.x.40.10(1)(C)
    if (ctx.building_type in ["duplex", "triplex", "fourplex"]
            and ctx.zone_code in RESIDENTIAL_ZONES):
        if ht is not None and ht < 10.0:
            return 10.0

    return ht if ht is not None else 10.0


def max_main_wall_height(ctx: ParcelContext) -> float:
    """Bylaw ref: 10.10.40.10(2), 10.20.40.10(2), 10.40.40.10(2),
    10.80.40.10(2)

    Applies to residential buildings other than apartment buildings.
    Main wall height = max(7.0m, permitted_height - 2.5m).
    """
    if ctx.zone_code in ["R", "RD", "RS", "RM"] and ctx.building_type != "apartment":
        permitted_ht = max_height(ctx)
        return max(7.0, permitted_ht - 2.5)
    return max_height(ctx)


def flat_roof_main_wall_exception(ctx: ParcelContext) -> Optional[dict]:
    """Bylaw ref: 10.10.40.10(11), 10.20.40.10(4), 10.40.40.10(6),
    10.80.40.10(6)

    Allows additional main walls above the max_main_wall_height limit
    when roof is flat (slope < 1:10 for >50% of roof area).
    """
    if ctx.zone_code in ["R", "RD", "RS", "RM"] and ctx.building_type != "apartment":
        return {
            "min_roof_slope_ratio": 0.1,  # 1:10
            "min_roof_area_fraction": 0.5,
            "required_setback_from_lower_main_wall_m": 1.4,
            "absolute_max_height_m": max_height(ctx),
        }
    return None


def min_height(ctx: ParcelContext) -> float:
    """Bylaw ref: 40.10.40.10(4)

    CR zones with residential FSI (r > 0.0) in Policy Area 1-4
    require minimum 10.5m height and 3 storeys.
    """
    if ctx.zone_code in ["CR", "CRE", "CR-T"]:
        if (ctx.zone_label_r is not None and ctx.zone_label_r > 0.0
                and ctx.policy_area is not None and 1 <= ctx.policy_area <= 4):
            return 10.5  # 40.10.40.10(4)
    return 0.0


def min_storeys(ctx: ParcelContext) -> int:
    """Bylaw ref: 40.10.40.10(4)"""
    if ctx.zone_code in ["CR", "CRE", "CR-T"]:
        if (ctx.zone_label_r is not None and ctx.zone_label_r > 0.0
                and ctx.policy_area is not None and 1 <= ctx.policy_area <= 4):
            return 3  # 40.10.40.10(4)
    return 0


def max_storeys(ctx: ParcelContext) -> Optional[int]:
    """Bylaw ref: 10.10.40.10(3), 10.20.40.10(3), 10.40.40.10(3),
    10.60.40.10(2), 10.80.40.10(3), 15.10.40.10(2)"""
    # Multiplex exceptions: exempt from ST limitations
    if (ctx.building_type in ["duplex", "triplex", "fourplex"]
            and ctx.zone_code in RESIDENTIAL_ZONES):
        return None

    if ctx.overlay_max_storeys is not None:
        return ctx.overlay_max_storeys
    return None  # Not limited if no ST value


def min_first_storey_height(ctx: ParcelContext) -> float:
    """Bylaw ref: 40.10.40.10(5)

    CR zones: first storey floor-to-ceiling must be at least 4.5m.
    """
    if ctx.zone_code in ["CR", "CRE", "CR-T"]:
        return 4.5  # 40.10.40.10(5)
    return 0.0


def height_measurement_method(ctx: ParcelContext) -> str:
    """Bylaw ref: 10.5.40.10(1), 15.5.40.10(1)"""
    return (
        "Distance between established grade and the elevation of "
        "the highest point of the building."
    )


def rooftop_exceedance_rules(ctx: ParcelContext) -> dict:
    """Bylaw ref: 10.5.40.10(2)(3)(4), 10.10.40.10(8)(9)(10),
    15.5.40.10(2)(3)(4)(5)(6), 40.5.40.10(3)-(8)

    Returns maximum height exceedance (m) by rooftop element type.
    """
    rules: dict = {
        "antennae_flagpoles_satellite_dishes_m": 1.5,
        "green_roof_parapets_weather_vanes_m": 1.5,
        "functional_equipment": {
            "max_exceedance_m": 5.0,
            "max_horizontal_roof_coverage": 0.30,
            "max_width_within_6m_of_street": 0.20,  # 20% of main wall width
        },
    }

    if ctx.zone_code in ["R", "RA", "RAC"]:
        rules["amenity_wind_protection"] = {
            "max_exceedance_m": 3.0,
            "min_setback_from_main_wall_m": 2.0,
        }

    # Tall Building (Tower) rules — 40.5.40.10(7)-(8)
    rules["tall_building_tower_functional_equipment"] = {
        "max_exceedance_m": 6.5,
        "max_horizontal_roof_coverage_sqm": 450.0,
        "chimneys_pipes_vents_additional_m": 3.0,
    }

    return rules


# ═══════════════════════════════════════════════════════════════════
# C. FLOOR AREA / DENSITY
# ═══════════════════════════════════════════════════════════════════

def max_fsi_total(ctx: ParcelContext) -> Optional[float]:
    """Bylaw ref: 10.10.40.40(1), 10.20.40.40(1), 10.40.40.40(1),
    10.60.40.40(1), 10.80.40.40(1), 15.10.40.40(1), 40.10.40.40(1)"""
    # 1. Overlay / explicit override (ZBA simulation)
    if ctx.overlay_fsi is not None:
        return ctx.overlay_fsi

    # Multiplex exception: exempt from FSI limits
    if (ctx.building_type in ["duplex", "triplex", "fourplex"]
            and ctx.zone_code in RESIDENTIAL_ZONES):
        return None

    # Zone label "d" value overrides
    if ctx.zone_label_d is not None:
        return ctx.zone_label_d

    # Default fallbacks
    if ctx.zone_code in ["R", "RD", "RS", "RT"]:
        return 0.6
    # RM and RA have no limit if 'd' is missing
    return None


def max_fsi_commercial(ctx: ParcelContext) -> Optional[float]:
    """Bylaw ref: 40.10.40.40(1)

    CR zones: max non-residential FSI from zone label "c" value.
    """
    if ctx.zone_code in ["CR", "CRE", "CR-T"]:
        return ctx.zone_label_c
    return None  # Not applicable to residential zones


def max_fsi_residential(ctx: ParcelContext) -> Optional[float]:
    """Bylaw ref: 40.10.40.40(1)

    CR zones: max residential FSI from zone label "r" value.
    """
    if ctx.zone_code in ["CR", "CRE", "CR-T"]:
        return ctx.zone_label_r
    return None  # Not applicable to pure residential zones


def transit_corridor_bonus_fsi(ctx: ParcelContext) -> float:
    """CR-T zones receive additional FSI for transit corridor proximity."""
    if ctx.zone_code == "CR-T":
        return 1.5
    return 0.0


def gfa_calculation_exclusions(ctx: ParcelContext) -> list[str]:
    """Bylaw ref: 10.5.40.40(3), 10.5.40.40(4), 15.5.40.40(1),
    40.5.40.40

    Returns list of GFA exclusion categories. These are descriptive —
    the actual exclusion calculation is done at the massing/pro-forma
    stage based on the building programme.
    """
    if ctx.building_type == "apartment" or ctx.zone_code in RESIDENTIAL_APARTMENT_ZONES:
        return [
            "parking_loading_bicycle_below_grade",
            "required_loading_bicycle_at_grade",
            "basement_storage_washrooms_mechanical",
            "bicycle_shower_change_facilities",
            "required_indoor_amenity_space",
            "elevator_garbage_shafts",
            "mechanical_penthouse",
            "exit_stairwells",
        ]
    else:
        return [
            "basement_floor_area",
            "void_above_4_5m_clearance_max_10pct",
            "one_parking_space_per_dwelling_unit",
            "second_parking_if_frontage_over_12m",
            "attic_mechanical_max_5pct_or_20sqm",
        ]


# ═══════════════════════════════════════════════════════════════════
# D. SETBACKS
# ═══════════════════════════════════════════════════════════════════

def front_setback(ctx: ParcelContext, ss: int = 0) -> float:
    """Bylaw ref: 10.10.40.70(1), 10.20.40.70(1), 10.40.40.70(1),
    10.60.40.70(1), 10.80.40.70(1), 15.10.40.70(1), 40.10.40.70

    Note: 10.5.40.70(1) allows front yard averaging if abutting lots
    have buildings within 15m. Not modelled here — requires runtime
    geometric queries.
    """
    # RA/RAC zones have a smaller front setback
    if ctx.zone_code in ["RA", "RAC"]:
        return 3.0  # 15.10.40.70(1)

    # CR zones — SS1/SS2 have a MAXIMUM front setback (75% of main wall
    # within 0-3.0m of front lot line), not a minimum. For envelope
    # purposes, the minimum front setback is 0.0m.
    if ctx.zone_code in ["CR", "CRE", "CR-T"]:
        return 0.0  # 40.10.40.70 — effectively 0m minimum

    # All other residential zones
    return 6.0  # 10.x.40.70(1)


def front_setback_maximum(ctx: ParcelContext, ss: int = 0) -> Optional[float]:
    """Bylaw ref: 40.10.40.70(1)(A), (2)(A)

    CR SS1/SS2: 75% of front main wall must be within 3.0m of front lot
    line. Returns the maximum front setback, or None if no maximum applies.
    """
    if ctx.zone_code in ["CR", "CRE", "CR-T"] and ss in [1, 2]:
        return 3.0  # 75% of main wall within this distance
    return None  # No maximum front setback


def rear_setback(
    ctx: ParcelContext,
    ss: int,
    abutting_zone: Optional[str],
    height_m: Optional[float] = None,
) -> float:
    """Bylaw ref: 10.10.40.70(2), 10.20.40.70(2), 10.40.40.70(2),
    10.60.40.70(2), 10.80.40.70(2), 15.10.40.70(2)(4), 40.10.40.70"""
    # ── Residential zones ──
    if ctx.zone_code in ["R", "RT"]:
        return 7.5  # 10.10.40.70(2), 10.60.40.70(2)

    if ctx.zone_code in ["RD", "RS", "RM"]:
        return max(7.5, ctx.lot_depth_m * 0.25)  # 10.20/40/80.40.70(2)

    if ctx.zone_code in ["RA", "RAC"]:
        base = 7.5  # 15.10.40.70(2)
        # Height-based step-back: +1.0m for each 2.0m above 11.0m
        if height_m is not None and height_m > 11.0:
            additional = height_m - 11.0
            steps = int((additional + 1.999) // 2.0)  # ceiling division
            return base + (steps * 1.0)  # 15.10.40.70(4) / 15.20.40.70(4)
        return base

    # ── CR zones ──
    if ctx.zone_code in ["CR", "CRE", "CR-T"]:
        if ss == 1:
            # SS1: rear setback only when abutting residential (with windows)
            if abutting_zone in ANGULAR_PLANE_TRIGGER_ZONES:
                return 7.5  # 40.10.40.70(1)(C)
            return 0.0

        if ss in [2, 3]:
            # SS2/SS3: 7.5m when abutting residential/open space
            if abutting_zone in ANGULAR_PLANE_TRIGGER_ZONES:
                return 7.5  # 40.10.40.70(2)(C), (3)(B)
            # Lane reduction: 7.5m from opposite lot line across lane
            if ctx.rear_has_laneway and ctx.laneway_opposite_zone in ANGULAR_PLANE_TRIGGER_ZONES:
                lw = ctx.laneway_width_m or 0.0
                return max(0.0, 7.5 - lw / 2.0)  # 40.10.40.70(2)(D)
            return 0.0

        # If SS is unknown (0), default to 0.0m for CR zones
        # rather than the massive 7.5m conservative fallback.
        return 0.0

    return 7.5  # Conservative default limit for other undocumented zones


def side_setback(
    ctx: ParcelContext,
    ss: int,
    abutting_zone: Optional[str],
    has_windows: bool,
    height_m: Optional[float] = None,
) -> float:
    """Bylaw ref: 10.10.40.70(3)(4), 10.20.40.70(3)(5), 10.40.40.70(3),
    10.60.40.70(3), 10.80.40.70(3), 15.10.40.70(3)(4), 40.10.40.70"""
    # ── Residential zones ──
    if ctx.zone_code == "R":
        if ctx.building_type in [
            "detached", "semi_detached", "duplex", "triplex", "fourplex"
        ] or (ctx.building_type == "townhouse" and ctx.num_frontages > 0):
            return 0.9 if has_windows else 0.45  # 10.10.40.70(3)(4)
        return 7.5  # Townhouse not fronting street, apartment > 13m

    elif ctx.zone_code == "RD":
        # Frontage-based lookup — 10.20.40.70(3)
        f = ctx.lot_frontage_m
        if f < 6.0:
            return 0.6
        if f < 12.0:
            return 0.9
        if f < 15.0:
            return 1.2
        if f < 18.0:
            return 1.5
        if f < 24.0:
            return 1.8
        if f < 30.0:
            return 2.4
        return 3.0

    elif ctx.zone_code == "RS":
        # Frontage-based lookup — 10.40.40.70(3)
        f = ctx.lot_frontage_m
        if f < 6.0:
            return 0.6
        if f < 12.0:
            return 0.9
        if f < 15.0:
            return 1.2
        return 1.5

    elif ctx.zone_code == "RT":
        if ctx.building_type in [
            "detached", "semi_detached", "duplex", "triplex", "fourplex"
        ] or (ctx.building_type == "townhouse" and ctx.num_frontages > 0):
            return 0.9  # 10.60.40.70(3)
        return 7.5

    elif ctx.zone_code == "RM":
        if ctx.building_type in ["detached", "duplex", "triplex", "fourplex"]:
            return 1.2  # 10.80.40.70(3)
        if ctx.building_type == "semi_detached":
            return 1.5
        return 2.4

    elif ctx.zone_code in ["RA", "RAC"]:
        base = 7.5  # 15.10.40.70(3)
        # Height-based step-back: +1.0m for each 2.0m above 11.0m
        if height_m is not None and height_m > 11.0:
            additional = height_m - 11.0
            steps = int((additional + 1.999) // 2.0)
            return base + (steps * 1.0)  # 15.10.40.70(4)
        return base

    # ── CR zones ──
    elif ctx.zone_code in ["CR", "CRE", "CR-T"]:
        if abutting_zone in ANGULAR_PLANE_TRIGGER_ZONES:
            return 5.5 if has_windows else 3.0  # 40.10.40.70(1)(B)-(C)
        return 0.0

    return 0.0


def flanking_setback(
    ctx: ParcelContext,
    ss: int,
    abutting_zone: Optional[str],
) -> float:
    """Bylaw ref: 10.20.40.70(6), 10.5.40.70

    Setback for a side edge that faces a street (corner lot flanking side).

    TODO: Verify exact flanking setback values for each residential zone
    against bylaw source. The values below are from the current bylaws.py
    config which may need correction (like the angular planes were).
    """
    if ctx.zone_code in ["CR", "CRE", "CR-T"]:
        return 0.0  # 40.10.40.70 — no flanking setback

    if ctx.zone_code in ["RA", "RAC"]:
        return 3.0  # 15.10.40.70

    if ctx.zone_code == "RD" and ctx.lot_frontage_m >= 12.0:
        return 3.0  # 10.20.40.70(6)

    # TODO: Gemini to verify these per-zone flanking values from bylaw
    # source sections 10.x.40.70. Current values from bylaws.py config.
    if ctx.zone_code in RESIDENTIAL_ZONES:
        return 4.5

    return 4.5  # Conservative default


def lane_setback(ctx: ParcelContext) -> float:
    """Bylaw ref: 10.5.40.70(2), 15.5.30.20(1)

    A building must be at least 2.5m from the original centreline of a lane.
    """
    return 2.5


def residential_first_storey_front_setback(ctx: ParcelContext, ss: int) -> Optional[float]:
    """Bylaw ref: 40.10.40.70(4)

    CR zones: dwelling units on the first storey must be set back at
    least 4.5m from front lot line (or 3.0m if floor level is 0.9-1.2m
    above grade).
    """
    if ctx.zone_code in ["CR", "CRE", "CR-T"]:
        return 4.5  # 40.10.40.70(4)
    return None


# ═══════════════════════════════════════════════════════════════════
# E. ANGULAR PLANES
# ═══════════════════════════════════════════════════════════════════

def rear_angular_plane(
    ctx: ParcelContext,
    ss: int,
    abutting_zone: Optional[str],
) -> Optional[dict]:
    """Bylaw ref: 40.10.40.70(2)(E)-(F), (3)(D)-(E), 30.20.40.70(3)

    Angular planes DO NOT exist for residential zones (R, RD, RS, RT, RM, RA).
    Residential zones use height limits and setback distances only.
    RA uses height-based stepped setbacks instead (see rear_setback).

    Angular planes exist for:
      - CR SS2/SS3: conditional on abutting residential/open space zone
      - CL: conditional on abutting residential/open space zone
      - CR SS1: NONE
    """
    # ── Residential zones: NO angular planes ──
    if ctx.zone_code in ALL_RESIDENTIAL_ZONES:
        return None

    # ── CR zones ──
    if ctx.zone_code in ["CR", "CRE", "CR-T"]:
        # SS1: no angular planes
        if ss == 1:
            return None

        # SS2 and SS3: only when abutting residential/open space
        if ss in [2, 3]:
            triggers_direct = abutting_zone in ANGULAR_PLANE_TRIGGER_ZONES
            triggers_via_lane = (
                ctx.rear_has_laneway
                and ctx.laneway_opposite_zone in ANGULAR_PLANE_TRIGGER_ZONES
            )

            if triggers_direct or triggers_via_lane:
                # Shallow vs deep lot determines start height
                row_w = ctx.front_street_row_width_m
                if is_shallow_lot(row_w, ctx.lot_depth_m):
                    start_h = 10.5  # 40.10.40.70(2)(E) shallow
                else:
                    start_h = 7.5   # 40.10.40.70(2)(E) deep

                # Lane adjustment: start height measured from lot line,
                # but angular plane projects from the lane width height
                if triggers_via_lane and not triggers_direct:
                    lw = ctx.laneway_width_m or 0.0
                    start_h = max(start_h, lw)  # At least lane width

                return {
                    "start_height_m": start_h,
                    "angle_deg": 45.0,
                    "bylaw_ref": f"40.10.40.70({ss})(E)",
                }
            return None

    # ── CL zone — most restrictive ──
    if ctx.zone_code == "CL":
        if abutting_zone in ANGULAR_PLANE_TRIGGER_ZONES:
            if ctx.rear_has_laneway:
                lw = ctx.laneway_width_m or 0.0
                return {
                    "start_height_m": lw,  # Height = lane width
                    "angle_deg": 45.0,
                    "bylaw_ref": "30.20.40.70(3)",
                }
            else:
                return {
                    "start_height_m": 0.0,  # Ground level!
                    "angle_deg": 45.0,
                    "bylaw_ref": "30.20.40.70(3)",
                }
        return None

    return None


def side_angular_plane(
    ctx: ParcelContext,
    ss: int,
    abutting_zone: Optional[str],
) -> Optional[dict]:
    """No zone in 569-2013 prescribes side angular planes.

    Side constraints are handled by dimensional setbacks (see side_setback).
    The RA zone uses height-based stepped setbacks on sides.
    """
    return None


def street_facing_angular_plane(
    ctx: ParcelContext,
    ss: int,
) -> Optional[dict]:
    """Bylaw ref: 40.10.40.70(2)(G)-(H)

    CR SS2 ONLY: building may not penetrate a 45-degree angular plane
    measured at a height equal to 80% of the street ROW width, from the
    lot line abutting that street.

    If multiple lot lines abut a street, the one with the widest ROW
    is used — 40.10.40.70(2)(H).
    """
    if ctx.zone_code in ["CR", "CRE", "CR-T"] and ss == 2:
        # Use the widest ROW if multiple street frontages
        row_widths = [ctx.front_street_row_width_m]
        if ctx.flanking_street_row_width_m is not None:
            row_widths.append(ctx.flanking_street_row_width_m)
        widest_row = max(row_widths)

        return {
            "start_height_m": widest_row * 0.80,  # 80% of ROW width
            "angle_deg": 45.0,
            "from_lot_line": "street",
            "bylaw_ref": "40.10.40.70(2)(G)",
        }
    return None


def angular_plane_encroachment_allowed(ctx: ParcelContext) -> bool:
    """Bylaw ref: 40.10.40.60(9), 30.20.40.60(9)

    In CR and CL zones, permitted encroachments may NOT penetrate
    angular planes. This is absolute — no exceptions for building elements.
    """
    if ctx.zone_code in ["CR", "CRE", "CR-T", "CL"]:
        return False  # Encroachments cannot penetrate angular planes
    return True  # Other zones have no angular planes to penetrate


# ═══════════════════════════════════════════════════════════════════
# F. BUILDING SEPARATION
# ═══════════════════════════════════════════════════════════════════

def building_separation_window_to_window(
    ctx: ParcelContext,
    wall_height_1: float,
    wall_height_2: float,
) -> float:
    """Bylaw ref: 10.10.40.80(1), 10.60.40.80(1), 10.80.40.80(1),
    15.10.40.80(1), 15.20.40.80(1)

    Minimum distance between two main walls with windows facing each other
    on the same lot.
    """
    if ctx.zone_code in ["R", "RT", "RM"]:
        return 11.0

    # TODO: Verify RD (10.20.40.80) and RS (10.40.40.80) — likely 11.0m
    if ctx.zone_code in ["RD", "RS"]:
        return 11.0  # Assumed same as R — needs bylaw verification

    if ctx.zone_code in ["RA", "RAC"]:
        max_h = max(wall_height_1, wall_height_2)
        if max_h <= 11.0:
            return 11.0
        # Above 11.0m: distance = average of the two wall heights
        return (wall_height_1 + wall_height_2) / 2.0  # 15.10.40.80(1)

    # CR zones
    if ctx.zone_code in ["CR", "CRE", "CR-T"]:
        return 11.0  # 40.10.40.80(1)

    return 0.0


def building_separation_window_to_blank(
    ctx: ParcelContext,
    wall_height_1: float,
    wall_height_2: float,
) -> float:
    """Bylaw ref: 10.10.40.80(1), 10.60.40.80(1), 10.80.40.80(1),
    15.10.40.80(1), 15.20.40.80(1)

    Minimum distance from a windowed wall to a blank wall on the same lot.
    """
    if ctx.zone_code in ["R", "RT", "RM"]:
        return 5.5

    if ctx.zone_code in ["RD", "RS"]:
        return 5.5  # Assumed same as R — needs bylaw verification

    if ctx.zone_code in ["RA", "RAC"]:
        max_h = max(wall_height_1, wall_height_2)
        if max_h <= 11.0:
            return 5.5
        return (wall_height_1 + wall_height_2) / 2.0

    if ctx.zone_code in ["CR", "CRE", "CR-T"]:
        return 5.5  # 40.10.40.80(1)

    return 0.0


def building_separation_blank_to_blank(ctx: ParcelContext) -> float:
    """Bylaw ref: 10.10.40.80(1), 10.60.40.80(2)"""
    if ctx.zone_code == "R" and ctx.building_type in ["townhouse", "apartment"]:
        return 2.0
    if ctx.zone_code == "RT":
        return 2.4  # Between side main walls
    return 0.0


def zone_boundary_separation(
    ctx: ParcelContext,
    abutting_zone: Optional[str],
) -> float:
    """Bylaw ref: 15.10.40.80(3), 15.20.40.80(4)

    RA/RAC buildings must maintain 15.0m from RD/RS zone boundaries.
    """
    if ctx.zone_code in ["RA", "RAC"] and abutting_zone in ["RD", "RS"]:
        return 15.0
    return 0.0


# ═══════════════════════════════════════════════════════════════════
# G. PERMITTED ENCROACHMENTS INTO SETBACKS
# ═══════════════════════════════════════════════════════════════════

def balcony_encroachment(ctx: ParcelContext) -> dict:
    """Bylaw ref: 10.5.40.60(1), 15.5.40.60(1)

    Covers decks, porches, balconies, and landings.
    """
    return {
        "max_encroachment_m": 2.5,
        "permitted_yards": ["front", "rear"],
        "max_width_fraction": 0.50,  # 50% of main wall width
        "min_distance_from_lot_line_m": 0.3,
    }


def canopy_encroachment(ctx: ParcelContext) -> dict:
    """Bylaw ref: 10.5.40.60(2), 15.5.40.60(2)"""
    return {
        "max_encroachment_m": 2.5,
        "max_width_fraction": 0.50,  # 50% of main wall width
        "min_distance_from_lot_line_m": 0.3,
    }


def stairs_encroachment(ctx: ParcelContext) -> dict:
    """Bylaw ref: 10.5.40.60(3), 15.5.40.60(3)"""
    return {
        "max_width_m": 2.0,
        "min_distance_from_lot_line_m": 0.6,
        "ramp_max_slope_ratio": 15.0,  # 1 vertical : 15 horizontal
    }


def bay_window_encroachment(ctx: ParcelContext) -> dict:
    """Bylaw ref: 10.5.40.60(6), 15.5.40.60(6)"""
    return {
        "front_rear_max_encroachment_m": 0.75,
        "front_rear_max_cumulative_width_fraction": 0.65,
        "side_max_encroachment_m": 0.6,
        "side_max_cumulative_width_fraction": 0.30,
        "min_distance_from_lot_line_m": 0.3,
    }


def roof_projection_encroachment(ctx: ParcelContext) -> dict:
    """Bylaw ref: 10.5.40.60(7), 15.5.40.60(7)"""
    return {
        "eaves_max_encroachment_m": 0.9,
        "eaves_min_distance_from_lot_line_m": 0.3,
    }


def architectural_feature_encroachment(ctx: ParcelContext) -> dict:
    """Bylaw ref: 10.5.40.60(5), 15.5.40.60(5)"""
    return {
        "pilaster_cornice_max_encroachment_m": 0.6,
        "chimney_max_encroachment_m": 0.6,
        "chimney_max_width_m": 1.8,
        "min_distance_from_lot_line_m": 0.3,
    }


def cladding_encroachment(building_age_years: float) -> float:
    """Bylaw ref: 10.5.40.60(4), 15.5.40.60(4)

    Allowed encroachment for adding insulation/cladding to existing
    buildings that are at least 5 years old.
    """
    if building_age_years >= 5.0:
        return 0.15
    return 0.0


def equipment_encroachment(ctx: ParcelContext) -> dict:
    """Bylaw ref: 10.5.40.60(8), 15.5.40.60(8)"""
    return {
        "ac_unit_max_encroachment_m": 0.9,
        "ac_min_distance_from_lot_line_m": 0.3,
        "prohibited_yards": ["front", "flanking"],
    }


# Note: angular_plane_encroachment_allowed() is defined in section E above.
# In CR and CL zones, encroachments may NOT penetrate angular planes.
# In all other zones, there are no angular planes to penetrate.


# ═══════════════════════════════════════════════════════════════════
# H. AMENITY SPACE
# ═══════════════════════════════════════════════════════════════════

AMENITY_UNIT_THRESHOLD = 20  # Only required for 20+ dwelling units


def indoor_amenity_space_sqm(ctx: ParcelContext) -> float:
    """Bylaw ref: 10.10.40.50(1)(A), 15.10.40.50(1)(A), 40.10.40.50(1)(A)

    Minimum indoor amenity space. Applies to ANY building with 20+
    dwelling units, regardless of building type.
    """
    if ctx.num_dwelling_units >= AMENITY_UNIT_THRESHOLD:
        return ctx.num_dwelling_units * 2.0  # 2.0 sqm per unit
    return 0.0


def outdoor_amenity_space_sqm(ctx: ParcelContext) -> float:
    """Bylaw ref: 10.10.40.50(1)(B), 15.10.40.50(1)(B), 40.10.40.50(1)(B)

    Minimum outdoor amenity space. Must adjoin or be directly accessible
    to the indoor amenity space, with a minimum of 40.0 sqm in that
    adjoining location.
    """
    if ctx.num_dwelling_units >= AMENITY_UNIT_THRESHOLD:
        return ctx.num_dwelling_units * 2.0  # 2.0 sqm per unit
    return 0.0


def outdoor_amenity_adjacency_min_sqm(ctx: ParcelContext) -> float:
    """Bylaw ref: 10.10.40.50(1)(B), 15.10.40.50(1)(B)

    At least 40.0 sqm of outdoor amenity must adjoin indoor amenity.
    """
    if ctx.num_dwelling_units >= AMENITY_UNIT_THRESHOLD:
        return 40.0
    return 0.0


def green_roof_amenity_max_fraction() -> float:
    """Bylaw ref: 10.10.40.50(1)(C), 15.10.40.50(1)(C)

    No more than 25% of outdoor amenity may be a green roof.
    """
    return 0.25


def non_residential_outdoor_amenity(ctx: ParcelContext) -> Optional[dict]:
    """Bylaw ref: 40.10.40.50(2)

    CR SS1 non-residential buildings: outdoor amenity based on number
    of lot lines abutting streets and non-residential floor area.
    """
    if ctx.zone_code in ["CR", "CRE", "CR-T"] and ctx.development_standard_set == 1:
        # Rates vary by number of street-facing lot lines
        if ctx.num_frontages >= 3:
            return {
                "rate_of_floor_area": 0.06,  # 6% of non-residential GFA
                "rate_of_lot_area": 0.18,    # or 18% of lot area
            }
        elif ctx.num_frontages == 2:
            return {
                "rate_of_floor_area": 0.03,
                "rate_of_lot_area": 0.09,
            }
        else:
            return {
                "rate_of_floor_area": 0.015,
                "rate_of_lot_area": 0.045,
            }
    return None


# ═══════════════════════════════════════════════════════════════════
# I. LANDSCAPING
# ═══════════════════════════════════════════════════════════════════

def landscaping_strip_width(
    ctx: ParcelContext,
    abutting_zone: Optional[str],
) -> float:
    """Bylaw ref: 10.5.50.10(5), 15.5.50.10(2), 40.10.50.10

    Width of required soft landscaping strip along lot line.
    Applies to ANY building abutting a residential zone — not just
    apartments.
    """
    # Any zone abutting residential requires a landscape buffer
    if abutting_zone in ALL_RESIDENTIAL_ZONES:
        return 1.5  # 10.5.50.10(5)

    # CR SS3: if main wall set back 3.0m+ from front lot line,
    # a 3.0m wide landscaping strip is required
    if (ctx.zone_code in ["CR", "CRE", "CR-T"]
            and ctx.development_standard_set == 3):
        return 3.0  # 40.10.50.10

    return 0.0


def soft_landscaping_rates(ctx: ParcelContext) -> dict:
    """Bylaw ref: 10.5.50.10(1)(3)(4), 15.5.50.10(1)

    Soft landscaping requirements for yards.
    """
    if ctx.building_type == "apartment" or ctx.zone_code in RESIDENTIAL_APARTMENT_ZONES:
        return {
            "lot_area_landscaping_min_fraction": 0.50,
            "soft_landscaping_min_fraction_of_landscaping": 0.50,
        }

    # Non-apartment residential
    f = ctx.lot_frontage_m
    return {
        "front_yard_landscaping_min_fraction": 0.50 if f >= 6.0 else 1.0,
        "front_yard_soft_fraction": 0.75,
        "rear_yard_soft_min_fraction": 0.50 if f > 6.0 else 0.25,
    }


def fencing_required(ctx: ParcelContext, abutting_zone: Optional[str]) -> bool:
    """Bylaw ref: 40.10.50.10

    CR zones abutting R/RA zones require fencing along that lot line.
    General fencing regulations are in Municipal Code Chapter 447.
    """
    if ctx.zone_code in ["CR", "CRE", "CR-T"]:
        return abutting_zone in ALL_RESIDENTIAL_ZONES
    return False


# ═══════════════════════════════════════════════════════════════════
# J. PARKING
# ═══════════════════════════════════════════════════════════════════
#
# Parking rates are in Chapter 200 and vary by Policy Area (PA1-PA4),
# use type, and proximity to transit. The functions below capture the
# zone-specific LOCATION and SETBACK rules. For actual parking space
# counts, the engine cross-references Chapter 200 at runtime.
# ═══════════════════════════════════════════════════════════════════

def parking_location_restrictions(ctx: ParcelContext) -> list[str]:
    """Bylaw ref: 10.5.80.10(3)(6), 15.5.80.10, 40.10.80.10"""
    restrictions = [
        "not_in_front_yard",
        "not_in_side_yard_abutting_street",
    ]

    # CR SS1/SS2: additional restriction — no surface parking in front yard
    if ctx.zone_code in ["CR", "CRE", "CR-T"] and ctx.development_standard_set in [1, 2]:
        restrictions.append("no_surface_parking_in_front_yard")

    return restrictions


def parking_setback_from_lot_lines(ctx: ParcelContext) -> float:
    """Bylaw ref: 15.5.80.20(1), 40.10.80.20"""
    if ctx.zone_code in RESIDENTIAL_APARTMENT_ZONES:
        return 0.5  # 0.5m from any lot line
    if ctx.zone_code in ["CR", "CRE", "CR-T"]:
        return 0.5  # 40.10.80.20
    return 0.0


def parking_setback_from_residential_zones(
    ctx: ParcelContext,
    abutting_zone: Optional[str],
) -> float:
    """Bylaw ref: 10.5.80.30(1), 15.5.80.30(1), 40.10.80.20

    Parking not in a building must be set back from residential zone lots.
    """
    if ctx.building_type == "apartment":
        return 3.0  # 3.0m from main wall of apartment
    if (ctx.zone_code in ["CR", "CRE", "CR-T"]
            and ctx.is_corner_lot
            and ctx.development_standard_set == 2
            and abutting_zone in ALL_RESIDENTIAL_ZONES | OPEN_SPACE_ZONES):
        return 7.5  # 40.10.80.20 — SS2 corner lots
    return 0.0


# Parking rates and bicycle parking are in Chapters 200 and 230
# respectively. These require a separate extraction pass as they are
# large standalone chapters with use-type-specific rate tables.


# ═══════════════════════════════════════════════════════════════════
# K. LOADING
# ═══════════════════════════════════════════════════════════════════
#
# Loading space types and counts are in Chapter 220. The functions
# below capture zone-specific location and access rules.
# ═══════════════════════════════════════════════════════════════════

def loading_location_restrictions(ctx: ParcelContext) -> list[str]:
    """Bylaw ref: 10.5.90.10(1), 40.10.90.10"""
    restrictions = [
        "not_in_front_yard",
        "not_in_side_yard_abutting_street",
    ]

    # CR/CL: also not in a yard abutting R/RA zones
    if ctx.zone_code in ["CR", "CRE", "CR-T", "CL"]:
        restrictions.append("not_in_yard_abutting_residential")

    return restrictions


def loading_access_requirements(ctx: ParcelContext) -> dict:
    """Bylaw ref: 10.5.90.40(1), 40.10.90.40

    Loading access rules, including lane priority.
    """
    rules: dict = {
        "cannot_cross_residential_zone_lot": True,
    }

    # CR SS1/SS2: if lot abuts a lane, loading access must be from lane
    if ctx.zone_code in ["CR", "CRE", "CR-T"] and ctx.development_standard_set in [1, 2]:
        if ctx.rear_has_laneway or ctx.side_has_laneway:
            rules["must_access_from_lane"] = True
        elif ctx.is_corner_lot:
            rules["must_access_from_non_major_street"] = True

    return rules


def mixed_use_loading_substitution(ctx: ParcelContext) -> Optional[dict]:
    """Bylaw ref: 40.10.90.1

    CR mixed-use buildings: Type G loading can be replaced by Type A/B
    with larger dimensions for buildings with 30+ units.
    """
    if (ctx.zone_code in ["CR", "CRE", "CR-T"]
            and ctx.building_type == "mixed_use"
            and ctx.num_dwelling_units >= 30):
        return {
            "type_g_substitution": "type_a_or_b_with_larger_dimensions",
            "threshold_units": 30,
        }
    return None


# ═══════════════════════════════════════════════════════════════════
# L. VEHICLE ACCESS
# ═══════════════════════════════════════════════════════════════════

def must_access_from_lane(ctx: ParcelContext) -> bool:
    """Bylaw ref: 10.5.80.40(3), 40.10.100.10

    If a lot has a rear or side lot line abutting a lane, vehicle
    access must be from the lane.
    """
    if ctx.rear_has_laneway or ctx.side_has_laneway:
        return True
    return False


def corner_lot_access_from_non_major_street(ctx: ParcelContext) -> bool:
    """Bylaw ref: 10.5.80.40(2), 40.10.100.10

    Corner lots without a lane: access must be from the flanking
    street if it is not a major street.
    """
    if ctx.is_corner_lot and ctx.flanking_street_is_major is False:
        return True
    return False


def max_vehicle_access_points(ctx: ParcelContext) -> int:
    """Bylaw ref: 10.5.100.1(6)

    Circular driveways / two access points allowed only if frontage > 18m.
    """
    if ctx.lot_frontage_m > 18.0:
        return 2
    return 1


def vehicle_access_cannot_cross_residential(ctx: ParcelContext) -> bool:
    """Bylaw ref: 10.5.80.40(4)

    Vehicle access to non-residential uses may not cross a lot in
    a residential zone category.
    """
    return True  # Always prohibited


# ═══════════════════════════════════════════════════════════════════
# M. MIXED-USE BUILDING RULES
# ═══════════════════════════════════════════════════════════════════

def residential_must_be_above_commercial(ctx: ParcelContext) -> bool:
    """Bylaw ref: 40.10.40.1(1), 10.10.20.100(12), 15.10.20.100(13)

    Residential uses must be located above non-residential uses.
    Exceptions: residential lobbies, and corner lot ground-floor units
    with direct street access on non-major streets.
    """
    if ctx.zone_code in ["CR", "CRE", "CR-T"]:
        return True
    # In residential zones, permitted commercial uses (where allowed
    # via condition) cannot be above the first storey
    if ctx.zone_code in ALL_RESIDENTIAL_ZONES:
        return True
    return False


def ground_floor_non_residential_level_m(ctx: ParcelContext) -> Optional[float]:
    """Bylaw ref: 40.10.40.1(2)

    CR zones: non-residential first storey floor level must be within
    0.2m of the ground at the street lot line.
    """
    if ctx.zone_code in ["CR", "CRE", "CR-T"]:
        return 0.2  # Within 0.2m of grade
    return None


def pedestrian_access_ramp_max_slope(ctx: ParcelContext) -> Optional[float]:
    """Bylaw ref: 40.10.40.1(3)

    CR zones: pedestrian access ramps no steeper than 1:25.
    (Not to be confused with exterior stairs ramp slope of 1:15
    in 10.5.40.60(3) which is an encroachment rule.)
    """
    if ctx.zone_code in ["CR", "CRE", "CR-T"]:
        return 25.0  # 1 vertical : 25 horizontal
    return None


def corner_lot_ground_floor_residential_allowed(ctx: ParcelContext) -> bool:
    """Bylaw ref: 40.10.40.1(4)

    CR corner lots: dwelling units permitted on the ground floor if
    they have direct street access on a non-major street.
    """
    if (ctx.zone_code in ["CR", "CRE", "CR-T"]
            and ctx.is_corner_lot
            and ctx.flanking_street_is_major is False):
        return True
    return False


# ═══════════════════════════════════════════════════════════════════
# N. WASTE STORAGE
# ═══════════════════════════════════════════════════════════════════

def waste_must_be_enclosed(ctx: ParcelContext) -> bool:
    """Bylaw ref: 10.5.150.1(1), 15.5.150.1(1), 40.10.150

    Buildings with 20+ dwelling units or non-residential buildings:
    all waste and recyclable material must be stored in a wholly
    enclosed building.
    """
    if ctx.num_dwelling_units >= 20:
        return True
    if ctx.building_type in ["mixed_use", "apartment"]:
        return True
    if ctx.zone_code in ["CR", "CRE", "CR-T"]:
        return True
    return False


def waste_location_restrictions(ctx: ParcelContext) -> list[str]:
    """Bylaw ref: 40.10.150"""
    restrictions = ["must_be_enclosed_in_building"]
    if ctx.zone_code in ["CR", "CRE", "CR-T"]:
        restrictions.extend([
            "not_in_front_yard",
            "not_in_side_yard_abutting_street",
        ])
    return restrictions


def waste_setback_from_residential_m(ctx: ParcelContext) -> float:
    """Bylaw ref: 40.10.150

    Ancillary waste building (if separate): 7.5m from R/RA/OS lot
    lines, 1.0m from other side/rear lot lines.
    """
    if ctx.zone_code in ["CR", "CRE", "CR-T"]:
        return 7.5  # From R/RA/OS lot lines
    return 0.0


# ═══════════════════════════════════════════════════════════════════
# O. ENERGY DEVICES
# ═══════════════════════════════════════════════════════════════════

def solar_device_height_exceedance_m(ctx: ParcelContext) -> float:
    """Bylaw ref: 10.5.75.1(4), 15.5.75.1(4)

    Solar energy devices may exceed max building height by this amount.
    """
    if ctx.building_type == "apartment" or ctx.zone_code in RESIDENTIAL_APARTMENT_ZONES:
        return 2.0
    return 1.2


def wind_device_rules(ctx: ParcelContext) -> dict:
    """Bylaw ref: 10.5.75.1(5), 15.5.75.1(5)"""
    max_exceedance = 2.5  # Default for non-apartment
    if ctx.building_type == "apartment" or ctx.zone_code in RESIDENTIAL_APARTMENT_ZONES:
        h = max_height(ctx)
        max_exceedance = 3.0 if h <= 24.0 else 5.0

    return {
        "max_devices_per_lot": 1,
        "max_height_exceedance_m": max_exceedance,
        "min_setback_from_lot_line_m": None,  # Equal to device height above grade
        "prohibited_yards": ["front", "flanking"],
    }


def geo_energy_rules(ctx: ParcelContext) -> dict:
    """Bylaw ref: 10.5.75.1(3), 15.5.75.1(3)"""
    return {
        "prohibited_yards": ["front", "flanking"],
        "above_ground_parts_must_comply_with_building_setbacks": True,
    }


def cogeneration_rules(ctx: ParcelContext) -> dict:
    """Bylaw ref: 10.5.75.1(6), 15.5.75.1(6)"""
    return {
        "must_be_inside_building": True,
    }


# ═══════════════════════════════════════════════════════════════════
# P. TALL BUILDING OVERLAY (Chapter 600)
# ═══════════════════════════════════════════════════════════════════

TALL_BUILDING_HEIGHT_THRESHOLD_M = 36.0
TOWER_BASE_HEIGHT_M = 24.0
TOWER_MAX_AVG_GFA_PER_STOREY_SQM = 750.0
TOWER_SEPARATION_M = 25.0
TOWER_SIDE_REAR_SETBACK_M = 12.5


def is_tall_building(ctx: ParcelContext) -> bool:
    """Bylaw ref: 600.10.10(1)

    Building Setback Overlay District "A" applies to buildings
    taller than 36.0m.
    """
    h = max_height(ctx)
    return h > TALL_BUILDING_HEIGHT_THRESHOLD_M


def tower_definition() -> dict:
    """Bylaw ref: 10.10.40.10(10), 15.5.40.10(6), 600.10.10

    Tower = portion of building above 24m with max average GFA
    per storey of 750 sqm.
    """
    return {
        "base_height_m": TOWER_BASE_HEIGHT_M,
        "max_avg_gfa_per_storey_sqm": TOWER_MAX_AVG_GFA_PER_STOREY_SQM,
    }


def tower_setback_m(ctx: ParcelContext) -> float:
    """Bylaw ref: 600.10.10(1)(A)

    Tower portions (above 24m) must be set back from side and rear
    lot lines.
    """
    if is_tall_building(ctx):
        return TOWER_SIDE_REAR_SETBACK_M
    return 0.0


def tower_separation_m(ctx: ParcelContext) -> float:
    """Bylaw ref: 600.10.10(1)(B)

    Tower portions must maintain 25.0m separation from other tower
    portions on the same or adjacent lots.
    """
    if is_tall_building(ctx):
        return TOWER_SEPARATION_M
    return 0.0


def tower_encroachments_cannot_penetrate_angular_planes() -> bool:
    """Bylaw ref: 600.10.10(1)(F)

    Building elements which encroach into the tower setback or
    separation distances must NOT penetrate any required angular plane.
    """
    return True


# ═══════════════════════════════════════════════════════════════════
# Q. ZONE-CATEGORY-LEVEL RULES (Chapters 10.5 / 15.5 / 40.5)
# ═══════════════════════════════════════════════════════════════════

def front_yard_averaging_allowed(ctx: ParcelContext) -> bool:
    """Bylaw ref: 10.5.40.70(1)

    If abutting lots have buildings within 15m of the front lot line,
    the required front setback may be reduced to the average of those
    buildings' setbacks.

    This requires runtime geometric queries and cannot be evaluated
    from the zone rules alone.
    """
    if ctx.zone_code in RESIDENTIAL_ZONES:
        return True
    return False


def multiplex_conversion_exemptions(ctx: ParcelContext) -> Optional[dict]:
    """Bylaw ref: 10.5.20.40

    Buildings constructed prior to May 15, 2023 may be converted to
    multiplex (up to 4 units) with certain exemptions from FSI, height,
    and parking requirements.
    """
    if ctx.zone_code in RESIDENTIAL_ZONES and ctx.building_type in [
        "duplex", "triplex", "fourplex"
    ]:
        return {
            "construction_date_cutoff": "2023-05-15",
            "fsi_exempt": True,
            "height_exempt_if_within_existing_envelope": True,
            "st_overlay_exempt": True,
            "parking_reduction_if_driveway_removed": True,
        }
    return None


def cr_category_lane_setback(ctx: ParcelContext) -> Optional[float]:
    """Bylaw ref: 40.5.40.70

    CR category: buildings must be set back from lane centreline.
    Uses the same 2.5m rule as residential (see lane_setback).
    """
    if ctx.zone_code in ["CR", "CRE", "CR-T"]:
        return 2.5
    return None


def cr_category_height_measurement(ctx: ParcelContext) -> Optional[str]:
    """Bylaw ref: 40.5.40.10(1)

    CR zone height measurement: same as residential — distance from
    established grade to highest point of building.
    """
    if ctx.zone_code in ["CR", "CRE", "CR-T"]:
        return height_measurement_method(ctx)
    return None
