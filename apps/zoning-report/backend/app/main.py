"""Zoning Report — FastAPI backend.

Endpoints:
  GET  /health          Service health
  GET  /search          Address → parcels
  GET  /search/reverse  lat/lng → nearest parcel
  GET  /zoning          lat/lng → full zoning + overlays + standards
  POST /reports/pdf     Generate PDF report
  POST /reports/preview JSON preview
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import search, zoning, reports

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load spatial indices in background."""
    asyncio.create_task(_load_zoning())
    yield


async def _load_zoning():
    try:
        from zoning_core.spatial import load_zoning_index
        await load_zoning_index()
        logger.info("Zoning spatial index loaded successfully.")
    except Exception as e:
        logger.error("Failed to load zoning index: %s", e)


app = FastAPI(
    title="Zoning Report API",
    description="Parcel lookup, zoning summary, and PDF report generation.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router, prefix="/search", tags=["search"])
app.include_router(zoning.router, prefix="/zoning", tags=["zoning"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])


@app.get("/health")
async def health():
    from zoning_core.spatial import is_loaded
    return {
        "status": "ok",
        "service": "zoning-report",
        "zoning_index_loaded": is_loaded(),
    }
