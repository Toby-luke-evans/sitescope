"""Reports router — PDF report generation from zoning data."""

import io
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from zoning_core.reports.zoning_pdf import build_zoning_pdf

router = APIRouter()


class ParcelData(BaseModel):
    lat: float
    lng: float
    zone_code: str
    zn_string: str


class ZoningData(BaseModel):
    zone_code: str
    zn_string: str
    max_fsi: float | None = None
    max_height_m: float | None = None
    storeys: int | None = None
    density: float | None = None
    lot_coverage: float | None = None
    stand_set: int | None = None


class OverlayData(BaseModel):
    height: dict | None = None
    lot_coverage: dict | None = None
    parking_zone: dict | None = None


class ReportRequest(BaseModel):
    parcel: ParcelData
    zoning: ZoningData
    overlays: OverlayData
    standards: dict
    city: str
    template: str = "standard"
    include_map: bool = True


@router.post("/pdf")
async def generate_pdf(request: ReportRequest):
    """Generate a PDF zoning report from parcel + zoning data."""
    try:
        pdf_bytes = build_zoning_pdf(request.model_dump())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="zoning-report-{datetime.now().strftime("%Y%m%d")}.pdf"'
        },
    )


@router.post("/preview")
async def preview_report(request: ReportRequest):
    """Return a JSON preview of what the PDF report would contain."""
    return {
        "title": f"Zoning Report — {request.parcel.zone_code}",
        "city": request.city,
        "parcel": request.parcel.model_dump(),
        "zoning": request.zoning.model_dump(),
        "overlays": request.overlays.model_dump(),
        "standards": request.standards,
        "template": request.template,
        "generated_at": datetime.now().isoformat(),
    }
