#!/usr/bin/env python3
"""Pre-download all Toronto CKAN spatial data for offline use.

Run this during Docker build:
    python3 scripts/download-ckan-data.py

Creates:
    packages/zoning-core/assets/ckan-cache/
        zoning.json    - Zoning Area polygons
        height.json    - Height Overlay
        coverage.json  - Lot Coverage Overlay
        parking.json   - Parking Zone Overlay

These are loaded by the backend at startup instead of making live CKAN calls.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

CKAN_BASE = "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/datastore_search"
RESOURCES = {
    "zoning": "76a2620f-a6b4-495d-8e41-c0ede1f8a928",
    "height": "f0a88d06-2430-4025-b15d-362cabd00f31",
    "coverage": "58ad8814-ca4e-43d6-848d-d5fd8d873574",
    "parking": "8f969df7-9008-49fd-a50b-df53f1f680e6",
}
BATCH_SIZE = 500

OUT_DIR = Path(__file__).parent.parent / "packages" / "zoning-core" / "assets" / "ckan-cache"


async def fetch_dataset(name: str, resource_id: str):
    """Fetch all records for a resource."""
    all_records = []
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
            if offset % 5000 == 0:
                print(f"  {name}: {len(all_records)} records...")
    return all_records


async def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for name, rid in RESOURCES.items():
        print(f"Downloading {name}...")
        records = await fetch_dataset(name, rid)
        out_file = OUT_DIR / f"{name}.json"
        with open(out_file, "w") as f:
            json.dump(records, f)
        size_mb = out_file.stat().st_size / 1024 / 1024
        print(f"  Saved {len(records):,} records → {out_file.name} ({size_mb:.1f} MB)")

    total_size = sum(f.stat().st_size for f in OUT_DIR.iterdir()) / 1024 / 1024
    print(f"\n✅ Done. Total cache size: {total_size:.1f} MB")


if __name__ == "__main__":
    asyncio.run(main())
