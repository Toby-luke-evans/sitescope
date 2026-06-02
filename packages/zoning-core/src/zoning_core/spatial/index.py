"""Spatial zoning & overlay index for Toronto.

Fetches Zoning Area, Height, Lot Coverage, and Parking Zone overlay datasets
from Toronto CKAN on startup. Builds Shapely STRtree indices for fast
point-in-polygon lookups.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
from shapely.geometry import Point, shape
from shapely import STRtree

logger = logging.getLogger(__name__)

CKAN_BASE = "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/datastore_search"
ZONING_RESOURCE = "76a2620f-a6b4-495d-8e41-c0ede1f8a928"
HEIGHT_RESOURCE = "f0a88d06-2430-4025-b15d-362cabd00f31"
LOT_COVERAGE_RESOURCE = "58ad8814-ca4e-43d6-848d-d5fd8d873574"
PARKING_ZONE_RESOURCE = "8f969df7-9008-49fd-a50b-df53f1f680e6"

BATCH_SIZE = 500  # Records per API call


def _safe_float(val: Any) -> float | None:
    """Parse a value to float, returning None on failure or sentinel -1."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if f < 0 else f  # CKAN uses -1 as "not specified"
    except (ValueError, TypeError):
        return None


@dataclass
class ZoneInfo:
    zone_code: str
    fsi_total: float | None
    fsi_commercial: float | None
    fsi_residential: float | None
    zn_string: str
    density: float | None
    lot_coverage: float | None  # from Zoning Area (often null)
    stand_set: int | None       # standard setback set number


@dataclass
class HeightInfo:
    height_m: float
    storeys: int | None


@dataclass
class LotCoverageInfo:
    coverage_pct: float  # e.g. 33.0 means 33%


@dataclass
class ParkingZoneInfo:
    zone: str  # e.g. "A", "B"


# ---------------------------------------------------------------------------
# Generic paginated CKAN fetcher
# ---------------------------------------------------------------------------

async def _fetch_all_records(resource_id: str, label: str) -> list[dict]:
    """Fetch all records from a CKAN datastore resource, paginated."""
    all_records: list[dict] = []

    async with httpx.AsyncClient(timeout=60.0) as client:
        offset = 0
        while True:
            params = {
                "id": resource_id,
                "limit": BATCH_SIZE,
                "offset": offset,
            }
            resp = await client.get(CKAN_BASE, params=params)
            resp.raise_for_status()
            result = resp.json().get("result", {})
            records = result.get("records", [])

            if not records:
                break

            all_records.extend(records)
            offset += BATCH_SIZE
            logger.debug("%s: fetched %d records so far", label, len(all_records))

    return all_records


def _parse_geometry(rec: dict):
    """Extract and validate a Shapely geometry from a CKAN record."""
    geom_raw = rec.get("geometry")
    if not geom_raw:
        return None

    if isinstance(geom_raw, str):
        try:
            geom_raw = json.loads(geom_raw)
        except (json.JSONDecodeError, ValueError):
            return None

    try:
        poly = shape(geom_raw)
        if poly.is_valid and not poly.is_empty:
            return poly
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Spatial index
# ---------------------------------------------------------------------------

class ZoningIndex:
    """In-memory spatial index for Toronto zoning and overlay data."""

    def __init__(self):
        self._zoning_polys: list = []
        self._zoning_data: list[ZoneInfo] = []
        self._zoning_tree: STRtree | None = None

        self._height_polys: list = []
        self._height_data: list[HeightInfo] = []
        self._height_tree: STRtree | None = None

        self._coverage_polys: list = []
        self._coverage_data: list[LotCoverageInfo] = []
        self._coverage_tree: STRtree | None = None

        self._parking_polys: list = []
        self._parking_data: list[ParkingZoneInfo] = []
        self._parking_tree: STRtree | None = None

        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    async def load(self) -> None:
        """Fetch all overlay records from CKAN and build spatial indices."""
        if self._loaded:
            return

        import time
        start_time = time.time()

        logger.info("Loading Toronto zoning spatial index...")

        await self._load_zoning()
        logger.info("Zoning Area:    %d polygons indexed", len(self._zoning_polys))

        await self._load_height()
        logger.info("Height Overlay: %d polygons indexed", len(self._height_polys))

        await self._load_lot_coverage()
        logger.info("Lot Coverage:   %d polygons indexed", len(self._coverage_polys))

        await self._load_parking()
        logger.info("Parking Zone:   %d polygons indexed", len(self._parking_polys))

        self._loaded = True
        
        elapsed = time.time() - start_time
        total_polygons = len(self._zoning_polys) + len(self._height_polys) + len(self._coverage_polys) + len(self._parking_polys)
        
        logger.info("Zoning spatial index ready. Loaded %d total polygons in %.2f seconds.", total_polygons, elapsed)
        logger.info("Expected load time: 15-30 seconds. Expected memory footprint: ~200-400MB.")

    # -- Zoning Area --------------------------------------------------------

    async def _load_zoning(self) -> None:
        records = await _fetch_all_records(ZONING_RESOURCE, "Zoning")
        polys = []
        data = []

        for rec in records:
            poly = _parse_geometry(rec)
            if poly is None:
                continue

            stand_set_raw = rec.get("STAND_SET")
            stand_set = None
            if stand_set_raw is not None:
                try:
                    ss = int(stand_set_raw)
                    stand_set = ss if ss >= 0 else None
                except (ValueError, TypeError):
                    pass

            polys.append(poly)
            data.append(ZoneInfo(
                zone_code=str(rec.get("ZN_ZONE", "")),
                fsi_total=_safe_float(rec.get("FSI_TOTAL")),
                fsi_commercial=_safe_float(rec.get("PRCNT_COMM")),
                fsi_residential=_safe_float(rec.get("PRCNT_RES")),
                zn_string=str(rec.get("ZN_STRING", "")),
                density=_safe_float(rec.get("DENSITY")),
                lot_coverage=_safe_float(rec.get("COVERAGE")),
                stand_set=stand_set,
            ))

        self._zoning_polys = polys
        self._zoning_data = data
        if polys:
            self._zoning_tree = STRtree(polys)

    # -- Height Overlay -----------------------------------------------------

    async def _load_height(self) -> None:
        records = await _fetch_all_records(HEIGHT_RESOURCE, "Height")
        polys = []
        data = []

        for rec in records:
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

            storeys_raw = rec.get("HT_STORIES")
            storeys = None
            if storeys_raw is not None:
                try:
                    s = int(storeys_raw)
                    storeys = s if s > 0 else None
                except (ValueError, TypeError):
                    pass

            polys.append(poly)
            data.append(HeightInfo(
                height_m=ht if ht else 10.0,
                storeys=storeys,
            ))

        self._height_polys = polys
        self._height_data = data
        if polys:
            self._height_tree = STRtree(polys)

    # -- Lot Coverage Overlay -----------------------------------------------

    async def _load_lot_coverage(self) -> None:
        records = await _fetch_all_records(LOT_COVERAGE_RESOURCE, "LotCoverage")
        polys = []
        data = []

        for rec in records:
            poly = _parse_geometry(rec)
            if poly is None:
                continue

            cov = _safe_float(rec.get("PRCNT_CVER"))
            if cov is None:
                continue

            polys.append(poly)
            data.append(LotCoverageInfo(coverage_pct=cov))

        self._coverage_polys = polys
        self._coverage_data = data
        if polys:
            self._coverage_tree = STRtree(polys)

    # -- Parking Zone Overlay -----------------------------------------------

    async def _load_parking(self) -> None:
        records = await _fetch_all_records(PARKING_ZONE_RESOURCE, "ParkingZone")
        polys = []
        data = []

        for rec in records:
            poly = _parse_geometry(rec)
            if poly is None:
                continue

            zone_label = str(rec.get("ZN_PARKZONE", "")).strip()
            if not zone_label:
                continue

            polys.append(poly)
            data.append(ParkingZoneInfo(zone=zone_label))

        self._parking_polys = polys
        self._parking_data = data
        if polys:
            self._parking_tree = STRtree(polys)

    # -- Lookup methods -----------------------------------------------------

    def lookup_zone(self, lng: float, lat: float) -> ZoneInfo | None:
        """Find the zoning info for a WGS84 point."""
        if not self._zoning_tree:
            return None

        point = Point(lng, lat)
        indices = self._zoning_tree.query(point)

        for idx in indices:
            if self._zoning_polys[idx].contains(point):
                return self._zoning_data[idx]

        return None

    def lookup_height(self, lng: float, lat: float) -> HeightInfo | None:
        """Find the height overlay for a WGS84 point."""
        if not self._height_tree:
            return None

        point = Point(lng, lat)
        indices = self._height_tree.query(point)

        for idx in indices:
            if self._height_polys[idx].contains(point):
                return self._height_data[idx]

        return None

    def lookup_lot_coverage(self, lng: float, lat: float) -> float | None:
        """Find the lot coverage percentage for a WGS84 point."""
        if not self._coverage_tree:
            return None

        point = Point(lng, lat)
        indices = self._coverage_tree.query(point)

        for idx in indices:
            if self._coverage_polys[idx].contains(point):
                return self._coverage_data[idx].coverage_pct

        return None

    def lookup_parking_zone(self, lng: float, lat: float) -> str | None:
        """Find the parking zone designation for a WGS84 point."""
        if not self._parking_tree:
            return None

        point = Point(lng, lat)
        indices = self._parking_tree.query(point)

        for idx in indices:
            if self._parking_polys[idx].contains(point):
                return self._parking_data[idx].zone

        return None


# Module-level singleton
_index = ZoningIndex()


async def load_zoning_index() -> None:
    """Load the global zoning index. Called from app startup."""
    await _index.load()


def lookup_zone(lng: float, lat: float) -> ZoneInfo | None:
    """Look up zoning for a coordinate."""
    return _index.lookup_zone(lng, lat)


def lookup_height(lng: float, lat: float) -> HeightInfo | None:
    """Look up height info for a coordinate."""
    return _index.lookup_height(lng, lat)


def lookup_lot_coverage(lng: float, lat: float) -> float | None:
    """Look up lot coverage % for a coordinate."""
    return _index.lookup_lot_coverage(lng, lat)


def lookup_parking_zone(lng: float, lat: float) -> str | None:
    """Look up parking zone for a coordinate."""
    return _index.lookup_parking_zone(lng, lat)


def is_loaded() -> bool:
    """Check if the zoning index has been loaded."""
    return _index.is_loaded
