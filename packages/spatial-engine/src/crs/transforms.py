"""Coordinate Reference System transforms between WGS84 and any UTM zone."""

from functools import lru_cache

from pyproj import Transformer
from shapely.geometry import Polygon
from shapely.ops import transform

WGS84 = "EPSG:4326"

# Default for backward compatibility (Toronto)
DEFAULT_UTM_EPSG = 32617  # UTM Zone 17N


@lru_cache(maxsize=16)
def _get_transformer(from_crs: str, to_crs: str) -> Transformer:
    """Cache transformers to avoid repeated creation."""
    return Transformer.from_crs(from_crs, to_crs, always_xy=True)


def polygon_to_utm(coords: list[list[float]], epsg: int = DEFAULT_UTM_EPSG) -> Polygon:
    """Transform WGS84 coordinate list to a UTM Shapely Polygon."""
    transformer = _get_transformer(WGS84, f"EPSG:{epsg}")
    polygon = Polygon(coords)
    return transform(transformer.transform, polygon)


def polygon_to_wgs84(polygon: Polygon, epsg: int = DEFAULT_UTM_EPSG) -> Polygon:
    """Transform a UTM polygon back to WGS84."""
    transformer = _get_transformer(f"EPSG:{epsg}", WGS84)
    return transform(transformer.transform, polygon)


def coords_utm_to_wgs84(x: float, y: float, epsg: int = DEFAULT_UTM_EPSG) -> tuple[float, float]:
    """Transform a single UTM point to WGS84 (lng, lat)."""
    transformer = _get_transformer(f"EPSG:{epsg}", WGS84)
    return transformer.transform(x, y)
