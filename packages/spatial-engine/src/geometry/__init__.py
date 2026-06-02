"""Geometry helpers for SiteScope spatial engine."""

from .parcel_context import ParcelSpatialContext, build_parcel_spatial_context
from .shapes import classify_lot_edges

__all__ = ["ParcelSpatialContext", "build_parcel_spatial_context", "classify_lot_edges"]
