"""Pydantic models for full zoning development standards."""

from typing import Any
from pydantic import BaseModel, Field


class DevelopmentStandardValue(BaseModel):
    """A single evaluated development standard from the rules engine."""

    value: Any
    unit: str | None = None
    bylaw_ref: str | None = None
    is_default: bool = False
    note: str | None = None


class DevelopmentStandardCategory(BaseModel):
    """A category of related development standards."""

    category_id: str
    category_name: str
    standards: dict[str, DevelopmentStandardValue]


class DevelopmentStandards(BaseModel):
    """All evaluated development standards for a parcel."""

    categories: list[DevelopmentStandardCategory]
    defaults_used: list[str] = Field(default_factory=list)
    context_summary: dict[str, Any] = Field(default_factory=dict)
