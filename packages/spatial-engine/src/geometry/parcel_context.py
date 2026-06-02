"""Parcel-derived spatial context for zoning lookup tools.

This module calculates existing-property facts from parcel geometry and nearby
parcel topology. It intentionally avoids proposed/current-building assumptions:
frontage, depth, corner status, and ROW estimates are parcel/street-context
facts, not programme inputs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Any

from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon, shape
from shapely.ops import transform

WGS84 = "EPSG:4326"
TORONTO_METRES = "EPSG:26917"  # NAD83 / UTM zone 17N, metres

_TO_METRES = Transformer.from_crs(WGS84, TORONTO_METRES, always_xy=True)


@dataclass
class EdgeContext:
    kind: str
    length_m: float
    bearing_deg: float
    confidence: float
    source: str


@dataclass
class ParcelSpatialContext:
    lot_area_sqm: float | None = None
    lot_frontage_m: float | None = None
    lot_depth_m: float | None = None
    is_corner_lot: bool | None = None
    num_frontages: int = 0
    frontage_bearing_deg: float | None = None
    front_street_row_width_m: float | None = None
    flanking_street_row_width_m: float | None = None
    frontage_source: str = "unavailable"
    depth_source: str = "unavailable"
    corner_source: str = "unavailable"
    row_width_source: str = "unavailable"
    confidence: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    edges: list[EdgeContext] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["edges"] = [asdict(e) for e in self.edges]
        return data


def _project_geom(geom: Any):
    return transform(_TO_METRES.transform, geom)


def _as_polygon(geojson: dict[str, Any] | None) -> Polygon | None:
    if not geojson:
        return None
    geom = shape(geojson)
    if geom.is_empty:
        return None
    if not geom.is_valid:
        geom = geom.buffer(0)
    if geom.geom_type == "MultiPolygon":
        geoms = list(getattr(geom, "geoms", []))
        polys = [p for p in geoms if isinstance(p, Polygon)]
        return max(polys, key=lambda p: p.area) if polys else None
    if isinstance(geom, Polygon):
        return geom
    return None


def _edge_bearing(line: LineString) -> float:
    (x1, y1), (x2, y2) = list(line.coords)[:2]
    dx = x2 - x1
    dy = y2 - y1
    # bearing from north, clockwise
    return (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0


def _angle_delta(a: float, b: float) -> float:
    d = abs((a - b + 180.0) % 360.0 - 180.0)
    return min(d, 180.0 - d)  # line orientation, not direction


def _outward_normal(edge: LineString, centroid: Point) -> tuple[float, float]:
    (x1, y1), (x2, y2) = list(edge.coords)[:2]
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / length, dy / length
    n1 = (-uy, ux)
    n2 = (uy, -ux)
    mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    to_centroid = (centroid.x - mx, centroid.y - my)
    # outward normal points away from centroid
    return n1 if (to_centroid[0] * n1[0] + to_centroid[1] * n1[1]) < 0 else n2


def _offset_line(edge: LineString, normal: tuple[float, float], distance_m: float) -> LineString:
    coords = [(x + normal[0] * distance_m, y + normal[1] * distance_m) for x, y in edge.coords]
    return LineString(coords)


def _edge_has_neighbour(edge: LineString, normal: tuple[float, float], neighbours: list[Polygon]) -> bool:
    if not neighbours:
        return False
    probe = _offset_line(edge, normal, 1.25).buffer(1.5, cap_style="flat")
    return any(probe.intersects(n) for n in neighbours)


def _row_width_from_opposite_parcel(edge: LineString, normal: tuple[float, float], neighbours: list[Polygon]) -> float | None:
    if not neighbours:
        return None
    mid = edge.interpolate(0.5, normalized=True)
    ray = LineString([(mid.x, mid.y), (mid.x + normal[0] * 80.0, mid.y + normal[1] * 80.0)])
    distances: list[float] = []
    for n in neighbours:
        inter = ray.intersection(n.boundary)
        if inter.is_empty:
            continue
        points: list[Point] = []
        if inter.geom_type == "Point":
            points = [inter]
        elif hasattr(inter, "geoms"):
            points = [g for g in getattr(inter, "geoms", []) if isinstance(g, Point)]
        for p in points:
            d = mid.distance(p)
            if 4.0 <= d <= 60.0:
                distances.append(d)
    return min(distances) if distances else None


def _cluster_street_edges(street_edges: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    clusters: list[list[dict[str, Any]]] = []
    for item in sorted(street_edges, key=lambda e: e["length"], reverse=True):
        bearing = item["bearing"]
        for cluster in clusters:
            cluster_bearing = cluster[0]["bearing"]
            if _angle_delta(bearing, cluster_bearing) <= 25.0:
                cluster.append(item)
                break
        else:
            clusters.append([item])
    return clusters


def _oriented_bbox_fallback(poly_m: Polygon) -> tuple[float, float, float]:
    rect = poly_m.minimum_rotated_rectangle
    coords = list(rect.exterior.coords)
    lengths = []
    bearings = []
    for i in range(4):
        line = LineString([coords[i], coords[i + 1]])
        lengths.append(line.length)
        bearings.append(_edge_bearing(line))
    short = min(lengths)
    long = max(lengths)
    bearing = bearings[lengths.index(short)]
    return short, long, bearing


def build_parcel_spatial_context(
    parcel_geometry: dict[str, Any] | None,
    *,
    nearby_parcel_geometries: list[dict[str, Any]] | None = None,
) -> ParcelSpatialContext:
    """Calculate parcel facts from geometry and nearby parcel topology."""
    ctx = ParcelSpatialContext()
    poly_wgs = _as_polygon(parcel_geometry)
    if poly_wgs is None:
        ctx.warnings.append("Parcel geometry unavailable; lot area/frontage/depth/corner status could not be calculated.")
        ctx.confidence = {"area": 0.0, "frontage": 0.0, "depth": 0.0, "corner_status": 0.0, "row_width": 0.0}
        return ctx

    poly_m = _project_geom(poly_wgs)
    if not poly_m.is_valid:
        poly_m = poly_m.buffer(0)

    ctx.lot_area_sqm = round(float(poly_m.area), 1)
    ctx.confidence["area"] = 0.98

    neighbours: list[Polygon] = []
    for geo in nearby_parcel_geometries or []:
        n = _as_polygon(geo)
        if n is None:
            continue
        n_m = _project_geom(n)
        if n_m.is_empty or n_m.equals(poly_m):
            continue
        # Avoid accidentally treating the subject parcel as a neighbour.
        if n_m.area and n_m.intersection(poly_m).area / min(n_m.area, poly_m.area) > 0.90:
            continue
        neighbours.append(n_m)

    centroid = poly_m.centroid
    street_edges: list[dict[str, Any]] = []
    parcel_edges: list[dict[str, Any]] = []
    coords = list(poly_m.exterior.coords)
    for i in range(len(coords) - 1):
        edge = LineString([coords[i], coords[i + 1]])
        if edge.length < 0.75:
            continue
        normal = _outward_normal(edge, centroid)
        bearing = _edge_bearing(edge)
        has_neighbour = _edge_has_neighbour(edge, normal, neighbours)
        item = {
            "edge": edge,
            "normal": normal,
            "bearing": bearing,
            "length": float(edge.length),
            "has_neighbour": has_neighbour,
            "row_width": None if has_neighbour else _row_width_from_opposite_parcel(edge, normal, neighbours),
        }
        parcel_edges.append(item)
        if not has_neighbour:
            street_edges.append(item)

    if street_edges:
        clusters = _cluster_street_edges(street_edges)
        clusters.sort(key=lambda c: sum(e["length"] for e in c), reverse=True)
        primary = clusters[0]
        primary_len = sum(e["length"] for e in primary)
        primary_bearing = primary[0]["bearing"]
        primary_normal = primary[0]["normal"]
        primary_anchor = primary[0]["edge"].interpolate(0.5, normalized=True)

        ctx.lot_frontage_m = round(primary_len, 1)
        ctx.frontage_bearing_deg = round(primary_bearing, 1)
        ctx.frontage_source = "calculated_from_parcel_edges_open_to_public_realm"
        ctx.confidence["frontage"] = 0.82 if neighbours else 0.55

        inward = (-primary_normal[0], -primary_normal[1])
        depths = [
            (x - primary_anchor.x) * inward[0] + (y - primary_anchor.y) * inward[1]
            for x, y in poly_m.exterior.coords
        ]
        positive_depths = [d for d in depths if d > 0]
        if positive_depths:
            ctx.lot_depth_m = round(max(positive_depths), 1)
            ctx.depth_source = "calculated_perpendicular_to_front_lot_line"
            ctx.confidence["depth"] = 0.78 if neighbours else 0.55

        frontage_clusters = [c for c in clusters if sum(e["length"] for e in c) >= 2.0]
        ctx.num_frontages = len(frontage_clusters)
        ctx.is_corner_lot = len(frontage_clusters) >= 2 and _angle_delta(frontage_clusters[0][0]["bearing"], frontage_clusters[1][0]["bearing"]) >= 35.0
        ctx.corner_source = "calculated_from_multiple_public-realm-facing_parcel_edges"
        ctx.confidence["corner_status"] = 0.78 if neighbours else 0.50

        row_values = [e["row_width"] for e in primary if e.get("row_width")]
        if row_values:
            ctx.front_street_row_width_m = round(sum(row_values) / len(row_values), 1)
            ctx.row_width_source = "estimated_from_distance_to_opposite_parcel_boundary"
            ctx.confidence["row_width"] = 0.55
        else:
            ctx.confidence["row_width"] = 0.0
            ctx.warnings.append("Street ROW width unavailable from parcel topology; not defaulted.")

        if ctx.is_corner_lot and len(frontage_clusters) > 1:
            flank_values = [e["row_width"] for e in frontage_clusters[1] if e.get("row_width")]
            if flank_values:
                ctx.flanking_street_row_width_m = round(sum(flank_values) / len(flank_values), 1)

        for e in parcel_edges:
            if not e["has_neighbour"]:
                kind = "front_or_flanking"
                source = "open_public_realm_edge"
            else:
                kind = "side_or_rear"
                source = "abutting_parcel_edge"
            ctx.edges.append(EdgeContext(kind=kind, length_m=round(e["length"], 1), bearing_deg=round(e["bearing"], 1), confidence=0.75, source=source))
    else:
        frontage, depth, bearing = _oriented_bbox_fallback(poly_m)
        ctx.lot_frontage_m = round(frontage, 1)
        ctx.lot_depth_m = round(depth, 1)
        ctx.frontage_bearing_deg = round(bearing, 1)
        ctx.is_corner_lot = None
        ctx.num_frontages = 0
        ctx.frontage_source = "estimated_from_minimum_rotated_rectangle_no_neighbour_topology"
        ctx.depth_source = "estimated_from_minimum_rotated_rectangle_no_neighbour_topology"
        ctx.corner_source = "unavailable_no_neighbour_topology"
        ctx.confidence.update({"frontage": 0.35, "depth": 0.35, "corner_status": 0.0, "row_width": 0.0})
        ctx.warnings.append("Nearby parcel topology unavailable; frontage/depth estimated from oriented parcel envelope.")
        ctx.warnings.append("Corner lot status unavailable; not defaulted.")
        ctx.warnings.append("Street ROW width unavailable; not defaulted.")

    return ctx
