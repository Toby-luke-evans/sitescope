from pydantic import BaseModel


class ZoningResult(BaseModel):
    """Result of zoning analysis from a plugin."""

    zone_code: str
    city: str
    max_fsi: float
    max_gfa_sqm: float
    modified_gfa_sqm: float
    max_height_m: float
    setbacks: dict[str, float]
    angular_planes: dict[str, dict]
    envelope_volume_m3: float
    bylaw_references: dict[str, str | None] = {}
    zn_string: str | None = None  # Full zoning designation, e.g. "CR 3.0 (c2.0; r2.5) SS2"
    abutting_zones: dict[str, str | None] = {}
    guideline_source: str | None = None  # "midrise" when Mid-Rise Guidelines are active
    row_width_m: float | None = None  # Detected or user-overridden ROW width
    streetwall_height_m: float | None = None  # Streetwall height (Mid-Rise Guidelines)  # edge_type → neighbour zone code
    
    # Parking requirements (Vancouver-specific)
    parking_requirements: dict[str, float] | None = None  # Parking calculation results

