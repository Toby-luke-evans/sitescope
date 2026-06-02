#!/usr/bin/env python3
"""Pre-download Toronto CKAN zoning data and build a local spatial cache.

This script is run during Docker build to avoid downloading 16k+ polygons
on every cold start. It creates a binary Pickle cache of all parsed
geometries + zone data that can be loaded ~50x faster than re-parsing GeoJSON.
"""

import asyncio
import json
import pickle
import sys
from pathlib import Path

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))

from zoning_core.spatial.index import _fetch_all_records, _parse_geometry, _safe_float, ZoneInfo, HeightInfo, LotCoverageInfo, ParkingZoneInfo
from zoning_core.spatial.index import ZONING_RESOURCE, HEIGHT_RESOURCE, LOT_COVERAGE_RESOURCE, PARKING_ZONE_RESOURCE

CACHE_DIR = Path(__file__).parent.parent / "packages" / "zoning-core" / "assets"
CACHE_FILE = CACHE_DIR / "spatial-index.pkl"


def build_cache():
    print("Building spatial index cache...")

    cache = {
        "zoning_polys": [],
        "zoning_data": [],
        "height_polys": [],
        "height_data": [],
        "coverage_polys": [],
        "coverage_data": [],
        "parking_polys": [],
        "parking_data": [],
    }

    async def _download():
        # Zoning
        print("Downloading Zoning Area polygons...")
        recs = await _fetch_all_records(ZONING_RESOURCE, "Zoning")
        print(f"  Got {len(recs)} records")
        for rec in recs:
            poly = _parse_geometry(rec)
            if poly is None:
                continue
            cache["zoning_polys"].append(poly.wkb)  # Store as WKB (binary, efficient)
            cache["zoning_data"].append({
                "zone_code": str(rec.get("ZN_ZONE", "")),
                "fsi_total": _safe_float(rec.get("FSI_TOTAL")),
                "fsi_commercial": _safe_float(rec.get("PRCNT_COMM")),
                "fsi_residential": _safe_float(rec.get("PRCNT_RES")),
                "zn_string": str(rec.get("ZN_STRING", "")),
                "density": _safe_float(rec.get("DENSITY")),
                "lot_coverage": _safe_float(rec.get("COVERAGE")),
                "stand_set": int(rec.get("STAND_SET")) if rec.get("STAND_SET") is not None else None,
            })

        # Height
        print("Downloading Height Overlay polygons...")
        recs = await _fetch_all_records(HEIGHT_RESOURCE, "Height")
        print(f"  Got {len(recs)} records")
        for rec in recs:
            poly = _parse_geometry(rec)
            if poly is None:
                continue
            ht_raw = rec.get("HT_LABEL", "")
            ht = None
            if ht_raw:
                try:
                    ht = float(str(ht_raw).strip().replace("m", ""))
                except (ValueError, TypeError):
                    pass
            cache["height_polys"].append(poly.wkb)
            cache["height_data"].append({
                "height_m": ht if ht else 10.0,
                "storeys": int(rec.get("HT_STORIES")) if rec.get("HT_STORIES") and int(rec.get("HT_STORIES")) > 0 else None,
            })

        # Lot Coverage
        print("Downloading Lot Coverage polygons...")
        recs = await _fetch_all_records(LOT_COVERAGE_RESOURCE, "LotCoverage")
        print(f"  Got {len(recs)} records")
        for rec in recs:
            poly = _parse_geometry(rec)
            if poly is None:
                continue
            cov = _safe_float(rec.get("PRCNT_CVER"))
            if cov is None:
                continue
            cache["coverage_polys"].append(poly.wkb)
            cache["coverage_data"].append({"coverage_pct": cov})

        # Parking
        print("Downloading Parking Zone polygons...")
        recs = await _fetch_all_records(PARKING_ZONE_RESOURCE, "ParkingZone")
        print(f"  Got {len(recs)} records")
        for rec in recs:
            poly = _parse_geometry(rec)
            if poly is None:
                continue
            zone_label = str(rec.get("ZN_PARKZONE", "")).strip()
            if not zone_label:
                continue
            cache["parking_polys"].append(poly.wkb)
            cache["parking_data"].append({"zone": zone_label})

    asyncio.run(_download())

    total = len(cache["zoning_polys"]) + len(cache["height_polys"]) + len(cache["coverage_polys"]) + len(cache["parking_polys"])
    print(f"\nSaving {total} total polygons to {CACHE_FILE}")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(cache, f)
    size_mb = CACHE_FILE.stat().st_size / 1024 / 1024
    print(f"Cache saved ({size_mb:.1f} MB)")


if __name__ == "__main__":
    build_cache()
