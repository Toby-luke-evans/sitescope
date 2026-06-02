"""Classify lot polygon edges into front, rear, side, and flanking based on bearing."""

import numpy as np
from shapely.geometry import LineString, Polygon


def classify_lot_edges(
    polygon: Polygon,
    frontage_bearing: float,
    flanking_bearing: float | None = None,
) -> dict[str, list[LineString]]:
    """
    Classify polygon edges into front, rear, side, and optionally flanking
    based on the frontage bearing (degrees from north).

    Uses the angle between each edge's outward normal and the
    front direction to classify edges.

    When ``flanking_bearing`` is provided (corner lot), side edges
    whose outward normal aligns with the flanking direction are
    reclassified as "flanking" instead of "side".

    Returns dict with keys: "front", "rear", "side", and optionally "flanking"
    """
    coords = list(polygon.exterior.coords[:-1])  # Remove closing duplicate
    edges: dict[str, list[LineString]] = {"front": [], "rear": [], "side": []}

    if flanking_bearing is not None:
        edges["flanking"] = []

    # Front direction vector (bearing: 0=N, 90=E, 180=S)
    bearing_rad = np.radians(frontage_bearing)
    front_dir = np.array([
        np.sin(bearing_rad),  # East component
        np.cos(bearing_rad),  # North component
    ])

    # Flanking direction vector (if corner lot)
    flanking_dir = None
    if flanking_bearing is not None:
        flanking_rad = np.radians(flanking_bearing)
        flanking_dir = np.array([
            np.sin(flanking_rad),
            np.cos(flanking_rad),
        ])

    centroid = np.array([polygon.centroid.x, polygon.centroid.y])

    for i in range(len(coords)):
        p1 = np.array(coords[i])
        p2 = np.array(coords[(i + 1) % len(coords)])

        edge_vec = p2 - p1
        edge_len = np.linalg.norm(edge_vec)
        if edge_len < 0.01:
            continue

        edge_unit = edge_vec / edge_len

        # Compute outward normal: perpendicular to edge, pointing away from centroid
        normal_a = np.array([-edge_unit[1], edge_unit[0]])
        normal_b = np.array([edge_unit[1], -edge_unit[0]])

        mid = (p1 + p2) / 2
        to_centroid = centroid - mid
        # Outward normal is the one pointing AWAY from centroid
        if np.dot(to_centroid, normal_a) < 0:
            outward = normal_a
        else:
            outward = normal_b

        # Classify based on dot product with front direction
        dot_front = np.dot(outward, front_dir)
        line = LineString([p1.tolist(), p2.tolist()])

        if dot_front > 0.5:
            edges["front"].append(line)
        elif dot_front < -0.5:
            edges["rear"].append(line)
        elif flanking_dir is not None:
            # Corner lot: check if this side edge faces the flanking direction
            dot_flank = np.dot(outward, flanking_dir)
            if dot_flank > 0.5:
                edges["flanking"].append(line)
            else:
                edges["side"].append(line)
        else:
            edges["side"].append(line)

    return edges
