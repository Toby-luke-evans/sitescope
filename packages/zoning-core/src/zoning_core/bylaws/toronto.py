"""
Toronto Zoning Bylaw 569-2013 parameters.

Complete zone parameter table covering all 20 zone types. Values serve as
defaults — the CKAN spatial overlays (FSI, height, lot coverage) override
these per-parcel when available.

IMPORTANT — Angular Planes:
  Residential zones (R, RD, RS, RT, RM, RA) do NOT have angular planes
  in Bylaw 569-2013. They rely on height limits and setback distances only.
  The RA zone uses height-based stepped setbacks (+1.0m per 2.0m above 11.0m).

  Angular planes only exist for:
    - CR SS2: rear (conditional on abutting zone, shallow/deep lot) + street-facing (80% ROW)
    - CR SS3: rear only (conditional on abutting zone, shallow/deep lot)
    - CL: rear from ground level (conditional on abutting zone)
    - CR SS1: NONE
  See rules_engine.py for the full conditional logic.

Special fields:
  - rear_m_ratio: When present, rear setback = max(rear_m, depth * ratio).
    Used by RM zones where bylaw specifies 25% of lot depth.
  - flanking_m: Setback for a side edge that faces a street (corner lots).
    Applied instead of side_m when the lot is detected as a corner lot.
  - transit_bonus_fsi: Additional FSI for transit corridor zones.
  - bylaw_references: Section references for the Toronto Zoning Bylaw.
    Used to generate hyperlinks into the official bylaw document.
"""

ZONE_PARAMS: dict[str, dict] = {
    # ── Residential ───────────────────────────────────────────────────────
    "R": {
        "description": "Residential Zone",
        "max_fsi": 0.6,
        "max_height_m": 10.0,
        "setbacks": {
            "front_m": 6.0,
            "rear_m": 7.5,
            "side_m": 1.2,
            "flanking_m": 4.5,
        },
        "angular_planes": {},  # No angular planes for residential zones
        "lot_coverage_max": 0.35,
        "bylaw_references": {
            "general": "10.10",
            "height": "10.10.40.10",
            "lot_coverage": "10.10.30.40",
            "fsi": "10.10.40.40",
            "setbacks": "10.10.40.70",
            "angular_planes": "10.10.40.70",
        },
    },
    "RD": {
        "description": "Residential Detached Zone",
        "max_fsi": 0.6,
        "max_height_m": 10.0,
        "setbacks": {
            "front_m": 6.0,
            "rear_m": 7.5,
            "side_m": 1.2,
            "flanking_m": 4.5,
        },
        "angular_planes": {},  # No angular planes for residential zones
        "lot_coverage_max": 0.35,
        "bylaw_references": {
            "general": "10.20",
            "height": "10.20.40.10",
            "lot_coverage": "10.20.30.40",
            "fsi": "10.20.40.40",
            "setbacks": "10.20.40.70",
            "angular_planes": "10.20.40.70",
        },
    },
    "RS": {
        "description": "Residential Semi-Detached Zone",
        "max_fsi": 0.6,
        "max_height_m": 10.0,
        "setbacks": {
            "front_m": 6.0,
            "rear_m": 7.5,
            "side_m": 0.9,
            "flanking_m": 4.5,
        },
        "angular_planes": {},  # No angular planes for residential zones
        "lot_coverage_max": 0.35,
        "bylaw_references": {
            "general": "10.40",
            "height": "10.40.40.10",
            "lot_coverage": "10.40.30.40",
            "fsi": "10.40.40.40",
            "setbacks": "10.40.40.70",
            "angular_planes": "10.40.40.70",
        },
    },
    "RT": {
        "description": "Residential Townhouse Zone",
        "max_fsi": 1.0,
        "max_height_m": 10.0,
        "setbacks": {
            "front_m": 6.0,
            "rear_m": 7.5,
            "side_m": 1.2,
            "flanking_m": 4.5,
        },
        "angular_planes": {},  # No angular planes for residential zones
        "lot_coverage_max": 0.35,
        "bylaw_references": {
            "general": "10.60",
            "height": "10.60.40.10",
            "lot_coverage": "10.60.30.40",
            "fsi": "10.60.40.40",
            "setbacks": "10.60.40.70",
            "angular_planes": "10.60.40.70",
        },
    },
    "RM": {
        "description": "Residential Multiple Zone",
        "max_fsi": 1.0,
        "max_height_m": 10.5,
        "setbacks": {
            "front_m": 6.0,
            "rear_m": 7.5,  # minimum — actual is max(7.5, depth * 0.25)
            "rear_m_ratio": 0.25,  # 25% of lot depth
            "side_m": 1.2,
            "flanking_m": 4.5,
        },
        "angular_planes": {},  # No angular planes for residential zones
        "lot_coverage_max": 0.35,
        "bylaw_references": {
            "general": "10.80",
            "height": "10.80.40.10",
            "lot_coverage": "10.80.30.40",
            "fsi": "10.80.40.40",
            "setbacks": "10.80.40.70",
            "angular_planes": "10.80.40.70",
        },
    },
    "RA": {
        "description": "Residential Apartment Zone",
        "max_fsi": 1.5,
        "max_height_m": 16.0,
        "setbacks": {
            "front_m": 3.0,
            "rear_m": 7.5,
            "side_m": 3.0,
            "flanking_m": 3.0,
        },
        "angular_planes": {},  # RA uses height-based stepped setbacks, not angular planes
        "lot_coverage_max": 0.4,
        "bylaw_references": {
            "general": "15.10",
            "height": "15.10.40.10",
            "lot_coverage": "15.10.30.40",
            "fsi": "15.10.40.40",
            "setbacks": "15.10.40.70",
            "angular_planes": "15.10.40.70",
        },
    },

    # ── Commercial-Residential ────────────────────────────────────────────
    "CR": {
        "description": "Commercial Residential Zone",
        "max_fsi": 3.0,
        "max_height_m": 30.0,
        "setbacks": {
            "front_m": 0.0,
            "rear_m": 7.5,
            "side_m": 0.0,
            "flanking_m": 0.0,
        },
        # Angular planes are CONDITIONAL — see rules_engine.py:
        #   SS1: NONE
        #   SS2: rear (shallow/deep lot) + street-facing (80% ROW) — only when abutting R/RA/O
        #   SS3: rear (shallow/deep lot) only — only when abutting R/RA/O
        "angular_planes": {},
        "lot_coverage_max": 1.0,
        "bylaw_references": {
            "general": "40.10",
            "height": "40.10.40.10",
            "lot_coverage": "40.10.30.40",
            "fsi": "40.10.40.40",
            "setbacks": "40.10.40.70",
            "angular_planes": "40.10.40.70",
        },
    },
    "CRE": {
        "description": "Commercial Residential Employment Zone",
        "max_fsi": 3.0,
        "max_height_m": 30.0,
        "setbacks": {
            "front_m": 0.0,
            "rear_m": 7.5,
            "side_m": 0.0,
            "flanking_m": 0.0,
        },
        # CRE: angular planes only via site-specific exceptions — see rules_engine.py
        "angular_planes": {},
        "lot_coverage_max": 1.0,
        "bylaw_references": {
            "general": "40.20",
            "height": "40.20.40.10",
            "lot_coverage": "40.20.30.40",
            "fsi": "40.20.40.40",
            "setbacks": "40.20.40.70",
            "angular_planes": "40.20.40.70",
        },
    },
    "CR-T": {
        "description": "Commercial Residential Transit Zone",
        "max_fsi": 3.0,
        "max_height_m": 30.0,
        "setbacks": {
            "front_m": 0.0,
            "rear_m": 7.5,
            "side_m": 0.0,
            "flanking_m": 0.0,
        },
        # Same conditional angular planes as CR — see rules_engine.py
        "angular_planes": {},
        "lot_coverage_max": 1.0,
        "transit_bonus_fsi": 1.5,
        "bylaw_references": {
            "general": "40.10",
            "height": "40.10.40.10",
            "lot_coverage": "40.10.30.40",
            "fsi": "40.10.40.40",
            "setbacks": "40.10.40.70",
            "angular_planes": "40.10.40.70",
        },
    },

    # ── Employment ────────────────────────────────────────────────────────
    "E": {
        "description": "Employment Zone",
        "max_fsi": 1.0,
        "max_height_m": 20.0,
        "setbacks": {
            "front_m": 3.0,
            "rear_m": 7.5,
            "side_m": 3.0,
            "flanking_m": 3.0,
        },
        "angular_planes": {},  # No angular planes for employment zones
        "lot_coverage_max": 0.5,
        "bylaw_references": {
            "general": "60.10",
            "height": "60.10.40.10",
            "lot_coverage": "60.10.30.40",
            "fsi": "60.10.40.40",
            "setbacks": "60.10.40.70",
            "angular_planes": "60.10.40.70",
        },
    },
    "EL": {
        "description": "Employment Light Industrial Zone",
        "max_fsi": 1.0,
        "max_height_m": 20.0,
        "setbacks": {
            "front_m": 6.0,
            "rear_m": 7.5,
            "side_m": 3.0,
            "flanking_m": 3.0,
        },
        "angular_planes": {},  # No angular planes for employment zones
        "lot_coverage_max": 0.5,
        "bylaw_references": {
            "general": "60.20",
            "height": "60.20.40.10",
            "lot_coverage": "60.20.30.40",
            "fsi": "60.20.40.40",
            "setbacks": "60.20.40.70",
            "angular_planes": "60.20.40.70",
        },
    },
    "EO": {
        "description": "Employment Office Zone",
        "max_fsi": 1.0,
        "max_height_m": 20.0,
        "setbacks": {
            "front_m": 3.0,
            "rear_m": 7.5,
            "side_m": 3.0,
            "flanking_m": 3.0,
        },
        "angular_planes": {},  # No angular planes for employment zones
        "lot_coverage_max": 0.5,
        "bylaw_references": {
            "general": "60.30",
            "height": "60.30.40.10",
            "lot_coverage": "60.30.30.40",
            "fsi": "60.30.40.40",
            "setbacks": "60.30.40.70",
            "angular_planes": "60.30.40.70",
        },
    },

    # ── Institutional ─────────────────────────────────────────────────────
    "I": {
        "description": "Institutional Zone",
        "max_fsi": 1.5,
        "max_height_m": 16.0,
        "setbacks": {
            "front_m": 6.0,
            "rear_m": 7.5,
            "side_m": 3.0,
            "flanking_m": 4.5,
        },
        "angular_planes": {},  # No angular planes for institutional zones
        "lot_coverage_max": 0.4,
        "bylaw_references": {
            "general": "80.10",
            "height": "80.10.40.10",
            "lot_coverage": "80.10.30.40",
            "fsi": "80.10.40.40",
            "setbacks": "80.10.40.70",
            "angular_planes": "80.10.40.70",
        },
    },
    "IH": {
        "description": "Institutional Hospital Zone",
        "max_fsi": 3.0,
        "max_height_m": 24.0,
        "setbacks": {
            "front_m": 6.0,
            "rear_m": 7.5,
            "side_m": 3.0,
            "flanking_m": 3.0,
        },
        "angular_planes": {},  # No angular planes for institutional zones
        "lot_coverage_max": 0.5,
        "bylaw_references": {
            "general": "80.20",
            "height": "80.20.40.10",
            "lot_coverage": "80.20.30.40",
            "fsi": "80.20.40.40",
            "setbacks": "80.20.40.70",
            "angular_planes": "80.20.40.70",
        },
    },
    "IE": {
        "description": "Institutional Education Zone",
        "max_fsi": 1.5,
        "max_height_m": 16.0,
        "setbacks": {
            "front_m": 6.0,
            "rear_m": 7.5,
            "side_m": 3.0,
            "flanking_m": 4.5,
        },
        "angular_planes": {},  # No angular planes for institutional zones
        "lot_coverage_max": 0.4,
        "bylaw_references": {
            "general": "80.30",
            "height": "80.30.40.10",
            "lot_coverage": "80.30.30.40",
            "fsi": "80.30.40.40",
            "setbacks": "80.30.40.70",
            "angular_planes": "80.30.40.70",
        },
    },

    # ── Open Space ────────────────────────────────────────────────────────
    "OS": {
        "description": "Open Space Zone",
        "max_fsi": 0.0,
        "max_height_m": 10.0,
        "setbacks": {
            "front_m": 6.0,
            "rear_m": 7.5,
            "side_m": 3.0,
            "flanking_m": 6.0,
        },
        "angular_planes": {},
        "lot_coverage_max": 0.1,
        "bylaw_references": {
            "general": "90.10",
            "height": "90.10.40.10",
            "lot_coverage": "90.10.30.40",
            "fsi": "90.10.40.40",
            "setbacks": "90.10.40.70",
        },
    },
    "ON": {
        "description": "Open Space Natural Zone",
        "max_fsi": 0.0,
        "max_height_m": 10.0,
        "setbacks": {
            "front_m": 6.0,
            "rear_m": 7.5,
            "side_m": 3.0,
            "flanking_m": 6.0,
        },
        "angular_planes": {},
        "lot_coverage_max": 0.05,
        "bylaw_references": {
            "general": "90.20",
            "height": "90.20.40.10",
            "lot_coverage": "90.20.30.40",
            "fsi": "90.20.40.40",
            "setbacks": "90.20.40.70",
        },
    },
    "OR": {
        "description": "Open Space Recreation Zone",
        "max_fsi": 0.0,
        "max_height_m": 10.0,
        "setbacks": {
            "front_m": 6.0,
            "rear_m": 7.5,
            "side_m": 3.0,
            "flanking_m": 6.0,
        },
        "angular_planes": {},
        "lot_coverage_max": 0.1,
        "bylaw_references": {
            "general": "90.30",
            "height": "90.30.40.10",
            "lot_coverage": "90.30.30.40",
            "fsi": "90.30.40.40",
            "setbacks": "90.30.40.70",
        },
    },
    "OG": {
        "description": "Open Space Golf Course Zone",
        "max_fsi": 0.0,
        "max_height_m": 10.0,
        "setbacks": {
            "front_m": 6.0,
            "rear_m": 7.5,
            "side_m": 3.0,
            "flanking_m": 6.0,
        },
        "angular_planes": {},
        "lot_coverage_max": 0.1,
        "bylaw_references": {
            "general": "90.40",
            "height": "90.40.40.10",
            "lot_coverage": "90.40.30.40",
            "fsi": "90.40.40.40",
            "setbacks": "90.40.40.70",
        },
    },

    # ── Utility ───────────────────────────────────────────────────────────
    "UT": {
        "description": "Utility and Transportation Zone",
        "max_fsi": 0.0,
        "max_height_m": 10.0,
        "setbacks": {
            "front_m": 6.0,
            "rear_m": 7.5,
            "side_m": 3.0,
            "flanking_m": 6.0,
        },
        "angular_planes": {},
        "lot_coverage_max": 0.1,
        "bylaw_references": {
            "general": "90.50",
            "height": "90.50.40.10",
            "lot_coverage": "90.50.30.40",
            "fsi": "90.50.40.40",
            "setbacks": "90.50.40.70",
        },
    },
}
