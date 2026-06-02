# Zoning Report Suite — Monorepo Plan

> **Version:** 0.1  
> **Date:** 2026-06-02  
> **Author:** C.A.L. for Toby Evans  
> **Scope:** Extract a focused Zoning Lookup + PDF Report tool from the existing SiteScope-2026 codebase, while restructuring into a maintainable monorepo.

---

## 1. Why a Monorepo?

| Concern | Monorepo | Separate Repos |
|--------|----------|---------------|
| Shared bylaw data (zone params, JSON elements, PDF chapters) | Single source of truth | 47MB PDFs copied N times → guaranteed drift |
| Zoning lookup service (spatial → STRtree → point-in-polygon) | Extract once, import everywhere | Re-implement in each repo |
| CI/CD overhead | One push triggers relevant apps | 4× Vercel + 4× Render configs |
| Solo builder cognitive load | One codebase, clear boundaries | Context-switching between repos |
| Future extraction | `git subtree split` when needed | Easy now, expensive later |

**Decision:** Start unified. Extract later if investors or teams demand it.

---

## 2. Directory Layout

```
sitescope/                          # rename to brand later
├── README.md
├── docker-compose.yml                  # dev stack: postgres + redis
├── .gitignore
│
├── packages/                           # SHARED libraries (no Docker, no deploy)
│   ├── zoning-core/                  # THE shared zoning brain
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   ├── bylaws/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── toronto.py        # from plugins/toronto/bylaws.py
│   │   │   │   └── vancouver.py      # from plugins/vancouver/bylaws.py
│   │   │   ├── models/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── zoning.py         # ZoningResult, ZoneInfo, HeightInfo, etc.
│   │   │   │   └── reports.py        # ReportRequest, ZoningReportData
│   │   │   ├── spatial/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── index.py          # ZoningIndex (from zoning_lookup_service.py)
│   │   │   │   └── lookup.py         # Convenience wrappers
│   │   │   └── reports/
│   │   │       ├── __init__.py
│   │   │       ├── zoning_pdf.py     # Stripped PDF generator (from pdf_service.py)
│   │   │       └── templates/
│   │   │           └── zoning_report.html  # Optional: HTML report template
│   │   └── assets/
│   │       ├── toronto/
│   │       │   ├── zoning_elements_chapter_*.json
│   │       │   └── 97ec-City-Planning-Zoning-Zoning-By-law-Part-1_chapter_*.pdf
│   │       └── vancouver/
│   │           └── vancouver_zoning_bylaw_3575.pdf
│   │
│   ├── spatial-engine/               # Shared geometry/CRS utilities
│   │   ├── pyproject.toml
│   │   └── src/
│   │       ├── __init__.py
│   │       ├── geometry/
│   │       │   ├── __init__.py
│   │       │   └── shapes.py         # Reusable geometry helpers
│   │       ├── crs/
│   │       │   ├── __init__.py
│   │       │   └── transforms.py     # UTM ↔ WGS84, polygon_to_utm, etc.
│   │       └── mesh/
│   │           ├── __init__.py
│   │           └── export.py         # OBJ/STEP export (optional for zoning-report)
│   │
│   └── shared-ui/                    # Shared frontend components + theme
│       ├── package.json
│       └── src/
│           ├── components/
│           │   ├── ReportButton.tsx    # Shared "Generate PDF" button
│           │   ├── MapView.tsx         # Base map (adapted from SiteScope)
│           │   └── SearchBar.tsx       # Address/parcel search
│           └── theme/
│               ├── colors.ts
│               └── fonts.ts
│
├── apps/                               # INDEPENDENTLY DEPLOYABLE applications
│   ├── hb-you-flagship/              # Current SiteScope (full HBU analysis)
│   │   ├── README.md                 # "This is the flagship tool"
│   │   ├── backend/                  # Current FastAPI (refs packages via PYTHONPATH)
│   │   │   ├── app/
│   │   │   └── Dockerfile
│   │   ├── frontend/                 # Current Next.js (refs packages via workspace/turborepo)
│   │   │   └── ...
│   │   └── docker-compose.yml
│   │
│   └── zoning-report/               # NEW: stripped-back lookup + PDF tool
│       ├── README.md                 # "Parcel lookup → zoning summary → PDF"
│       ├── backend/
│       │   ├── pyproject.toml
│       │   ├── Dockerfile
│       │   ├── app/
│       │   │   ├── __init__.py
│       │   │   ├── main.py           # FastAPI app (lightweight)
│       │   │   ├── routers/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── search.py     # Address → lat/lng + parcel
│       │   │   │   ├── zoning.py     # lat/lng → ZoneInfo + overlays
│       │   │   │   └── reports.py    # Generate + download PDF
│       │   │   └── services/
│       │   │       ├── __init__.py
│       │   │       └── search.py     # City search adapters (CKAN, OpenDataSoft, etc.)
│       │   └── zoning_core/           # Symlink or PYTHONPATH to packages/zoning-core
│       └── frontend/
│           ├── package.json
│           ├── next.config.ts
│           ├── Dockerfile
│           └── src/
│               ├── app/
│               │   ├── layout.tsx     # Minimal: dark theme, no sidebar cruft
│               │   ├── page.tsx       # Landing: search bar CTA
│               │   ├── search/
│               │   │   └── page.tsx   # Search results + map
│               │   └── report/
│               │       └── page.tsx   # Full zoning summary + PDF button
│               ├── components/
│               │   ├── ZoningPanel.tsx       # Zone code + params + overlays
│               │   ├── OverlayBadges.tsx     # Height, coverage, parking
│               │   ├── StandSummary.tsx      # Setbacks, density, standards
│               │   └── ReportPreview.tsx     # HTML preview before PDF
│               └── lib/
│                   ├── api.ts               # Backend client (SWR / React Query)
│                   ├── types.ts             # Frontend types
│                   └── constants.ts         # City configs, API URLs
│
├── docs/
│   ├── ZONING-REPORT-PLAN.md           # This file
│   ├── API-SPEC.md                     # REST API contract
│   ├── EXTRACTION-MAP.md               # SiteScope file → monorepo destination
│   └── DEPLOYMENT.md                   # Render + Vercel setup
│
└── tools/
    ├── copy-assets.sh                  # Copy SiteScope assets to packages/zoning-core/assets/
    └── verify-extraction.py            # Compare extracted files with originals
```

---

## 3. API Surface (Zoning Report Backend)

### Core Principle: 4 endpoints, no bloat.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/search` | `GET` | Address query → list of parcels with lat/lng |
| `/search/reverse` | `GET` | lat/lng → nearest parcel |
| `/zoning` | `GET` | lat/lng → full zoning + overlay + standards |
| `/reports/pdf` | `POST` | Generate PDF report from zoning data |

### 3.1 `GET /search?city={city}&q={address}`

**Request:**
```
GET /search?city=toronto&q=100+Queen+St+W
```

**Response:**
```json
{
  "city": "toronto",
  "query": "100 Queen St W",
  "results": [
    {
      "id": "prop_abc123",
      "address": "100 Queen Street West",
      "lat": 43.6532,
      "lng": -79.3832,
      "zone_code": "CR",
      "confidence": 0.98
    }
  ]
}
```

**Adapters per city:**
- Toronto: CKAN (`datastore_search` on parcel polygons) + ArcGIS
- Vancouver: OpenDataSoft (`property-parcel-polygons`) with suffix expansion + exact civic filtering (see `municipal-zoning-plugin` skill)
- Future: Add `/{city}/search` sub-routers as needed

### 3.2 `GET /search/reverse?city={city}&lat={lat}&lng={lng}`

**Response:** Same parcel shape as `/search`, but single result (nearest).

### 3.3 `GET /zoning?city={city}&lat={lat}&lng={lng}`

**Response:**
```json
{
  "parcel": {
    "id": "prop_abc123",
    "address": "100 Queen St W",
    "lat": 43.6532,
    "lng": -79.3832
  },
  "zoning": {
    "zone_code": "CR T3.0 C2.0 R2.0 ST1",
    "zn_string": "CR T3.0 C2.0 R2.0 ST1",
    "max_fsi": 3.0,
    "max_height_m": 30.0,
    "storeys": 10,
    "density": null,
    "lot_coverage": 45.0,
    "stand_set": 1
  },
  "overlays": {
    "height": { "height_m": 30.0, "storeys": 10 },
    "lot_coverage": { "coverage_pct": 45.0 },
    "parking_zone": { "zone": "A" }
  },
  "standards": {
    "setbacks": {
      "front_m": 0.0,
      "rear_m": 7.5,
      "side_interior_m": 0.0,
      "side_exterior_m": 3.0,
      "side_total_m": 3.0
    },
    "angular_planes": {
      " applies": true,
      "plane_angle_deg": 45
    },
    "bylaw_reference": "Chapter 230, Section 4.2.1"
  },
  "city": "toronto"
}
```

**Backend flow:**
1. `ZoningIndex.lookup_zone(lng, lat)` → `ZoneInfo`
2. `ZoningIndex.lookup_height(lng, lat)` → `HeightInfo`
3. `ZoningIndex.lookup_lot_coverage(lng, lat)` → `float`
4. `ZoningIndex.lookup_parking_zone(lng, lat)` → `str`
5. `ZoneParams` from `packages/zoning-core/src/bylaws/{city}.py`
6. `RulesEngine.evaluate_setbacks(zn_string)` + `evaluate_angular_planes()`
7. Assemble response

### 3.4 `POST /reports/pdf`

**Request:**
```json
{
  "parcel_id": "prop_abc123",
  "address": "100 Queen St W",
  "city": "toronto",
  "zoning": { /* full /zoning response */ },
  "template": "standard",   // future: "detailed", "comparison"
  "include_map": true
}
```

**Response:** `application/pdf` binary stream (inline download).

**PDF Generation (stripped from SiteScope):**
- Page 1: Parcel info + Zoning Classification + Key Parameters (FSI, Height, Setbacks)
- Page 2: Overlay Summary (Height, Lot Coverage, Parking Zone)
- Page 3: Development Standards (angular planes, setbacks table, bylaw refs)
- Page 4: Map inset (static image or rendered polygon)
- Page 5: Notes + Disclaimer

**Out of scope for this tool:** Proforma, 3D envelope, mesh data, precedent search, policy alerts, collaboration features.

---

## 4. Extraction Map: SiteScope → Monorepo

### 4.1 `packages/zoning-core/`

| SiteScope Source | Monorepo Destination | Notes |
|--------------|----------------------|-------|
| `backend/app/services/zoning_lookup_service.py` | `packages/zoning-core/src/spatial/index.py` | Full copy, remove backend-specific imports |
| `backend/app/services/zoning_lookup_service.py` (wrap) | `packages/zoning-core/src/spatial/lookup.py` | Re-export convenience functions |
| `backend/app/plugins/toronto/bylaws.py` | `packages/zoning-core/src/bylaws/toronto.py` | `ZONE_PARAMS` dict, remove plugin-specific refs |
| `backend/app/plugins/vancouver/bylaws.py` | `packages/zoning-core/src/bylaws/vancouver.py` | Same as above |
| `backend/app/models/zoning.py` | `packages/zoning-core/src/models/zoning.py` | Pydantic models: `ZoningResult`, `ZoneInfo`, etc. |
| `backend/app/schemas/report.py` | `packages/zoning-core/src/models/reports.py` | `ReportRequest`, report data schemas |
| `backend/app/services/pdf_service.py` | `packages/zoning-core/src/reports/zoning_pdf.py` | Strip to zoning-only pages |
| `backend/app/services/pdf_service_new.py` | → review, may be better than pdf_service.py | |
| `assets/zoning_elements*.json` | `packages/zoning-core/assets/toronto/` | All JSON + PDF chapters |
| `assets/vancouver_zoning_bylaw_3575.pdf` | `packages/zoning-core/assets/vancouver/` | |

### 4.2 `packages/spatial-engine/`

| SiteScope Source | Monorepo Destination | Notes |
|--------------|----------------------|-------|
| `backend/app/geometry/crs.py` | `packages/spatial-engine/src/crs/transforms.py` | UTM ↔ WGS84, polygon_to_utm |
| `backend/app/geometry/envelope.py` | `packages/spatial-engine/src/geometry/envelope.py` | May not be needed for zoning-report |
| `backend/app/geometry/lot_edges.py` | `packages/spatial-engine/src/geometry/shapes.py` | Utilities for polygon operations |

### 4.3 `apps/zoning-report/backend/`

**New code** (not extracted):
- `main.py` — FastAPI app with lifespan, CORS, 4 routers
- `routers/search.py` — City-aware search adapters
- `routers/zoning.py` — Wraps `packages/zoning-core` lookups
- `routers/reports.py` — PDF generation endpoint
- `services/search.py` — CKAN, OpenDataSoft, ArcGIS client logic (adapted from existing plugins)

**Symlinks / PYTHONPATH:**
The backend will import `packages/zoning-core` and `packages/spatial-engine` via:
- `PYTHONPATH=/app/packages/zoning-core/src:/app/packages/spatial-engine/src`
- Or: install as editable packages (`pip install -e packages/zoning-core`)

### 4.4 `apps/zoning-report/frontend/`

**Extracted/adapted from SiteScope:**
- `components/SearchBar.tsx` — Simplify, remove multi-city toggle
- `components/MapView.tsx` — Adapted, single-city context
- `components/ZoningInfo.tsx` → `components/ZoningPanel.tsx` — Strip proforma, envelope, mesh references
- `lib/api.ts` — Point to new backend, add SWR caching

**New components:**
- `ZoningPanel.tsx` — Zone code, FSI, height, density
- `OverlayBadges.tsx` — Height overlay, lot coverage, parking zone
- `StandSummary.tsx` — Setbacks table, angular planes, bylaw refs
- `ReportPreview.tsx` — HTML preview of what the PDF will contain

---

## 5. Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Monorepo manager | **Turborepo** (or npm workspaces) | Industry standard, caching, parallel builds |
| Backend | **FastAPI** + **Python 3.12** | Already used in SiteScope, proven |
| Frontend | **Next.js 16** + **App Router** + **Tailwind** | Already used, static export for zoning-report |
| PDF | **ReportLab** (Python) | Already built in SiteScope, reliable, controllable |
| Spatial | **Shapely** + **GeoJSON** | Already used, STRtree point-in-polygon |
| Maps | **Mapbox GL** or **Leaflet** | SiteScope uses Mapbox, keep consistent |
| Search adapters | **httpx** async | Already used for CKAN / OpenDataSoft |
| Deployment | **Render** (backend) + **Vercel** (frontend) | Same as SiteScope |
| DB (future) | **Supabase PostgreSQL** + **PostGIS** | For caching search results, not needed v1 |

**v1 can be stateless** — no database required. All data comes from:
- In-memory spatial indices (loaded on startup from CKAN/OpenDataSoft)
- Static JSON assets (bylaw parameters)
- PDF generation on-demand

---

## 6. Build Order (Execution Plan)

### Phase 1: Foundation (This Session)
- [x] Scaffold monorepo structure
- [ ] Write `ZONING-REPORT-PLAN.md` (this document)
- [ ] Write `EXTRACTION-MAP.md` with exact file copy commands
- [ ] Move `zoning_lookup_service.py` → `packages/zoning-core/src/spatial/`
- [ ] Move Toronto + Vancouver bylaws → `packages/zoning-core/src/bylaws/`
- [ ] Copy zoning JSON + PDF assets → `packages/zoning-core/assets/`
- [ ] Create `packages/zoning-core/pyproject.toml` (pip-installable package)

### Phase 2: Backend (Next Session)
- [ ] Scaffold `apps/zoning-report/backend/` with FastAPI
- [ ] Create `/search`, `/search/reverse`, `/zoning` routers
- [ ] Strip `pdf_service.py` to zoning-only pages → `/reports/pdf`
- [ ] Add CORS, health check, OpenAPI docs
- [ ] Test with curl: `/zoning?city=toronto&lat=43.6532&lng=-79.3832`

### Phase 3: Frontend (Next Session)
- [ ] Scaffold Next.js in `apps/zoning-report/frontend/`
- [ ] Single page: search bar + map + zoning panel
- [ ] "Generate Report" button → POST to `/reports/pdf`
- [ ] Dark theme matching SiteScope aesthetic

### Phase 4: Integration & Polish
- [ ] Dockerize backend
- [ ] Add `docker-compose.yml` at root for dev
- [ ] Wire to Render `render.yaml`
- [ ] Add Google Analytics / Plausible (optional)
- [ ] Deploy staging

### Phase 5: Extract SiteScope Flagship (After zoning-report ships)
- [ ] Move SiteScope backend into `apps/hb-you-flagship/backend/`
- [ ] Refactor SiteScope to import from `packages/zoning-core`
- [ ] Freeze old SiteScope-2026 repo (archive, don't delete)

---

## 7. Key Decisions & Pitfalls

### ✅ Do This
- **Keep PDF generation server-side.** ReportLab in Python is battle-tested. Client-side PDF libraries (jsPDF, html2canvas) fail on complex tables and custom fonts.
- **Make the frontend stateless.** Search params in URL (`?q=100+Queen+St+W`) so users can bookmark/share links.
- **Cache spatial indices in memory.** CKAN fetch on startup (15-30s), then serve from RAM. No DB needed for v1.
- **Use the same design tokens as SiteScope.** Dark mode, Playfair Display + JetBrains Mono, `#b18255` accent. Consistency builds brand recognition.

### ❌ Don't Do This
- **Don't duplicate bylaw parsing logic.** If you find yourself writing `ZONE_PARAMS` for Toronto in two places, the monorevo has failed.
- **Don't add auth for v1.** One less thing to break. Add Clerk/NextAuth later.
- **Don't build a DB layer for v1.** PostgreSQL is great, but SQLite in memory or flat JSON files handle this fine until you need user accounts.
- **Don't build a "comparison" feature yet.** "Compare two parcels" sounds nice but doubles the UI surface. Ship single-parcel lookup first.

### ⚠️ Known Pitfalls from SiteScope
1. **OpenDataSoft suffix expansion:** Users type "Terminal Avenue", API stores "TERMINAL AV". Expand `(AV OR AVE OR AVENUE)` before querying.
2. **Exact civic-number filtering:** OpenDataSoft's `refine.civic_number` does PREFIX matching (77 matches 7710). Post-filter by exact int match.
3. **Site-specific zones (CD-1, HA-2):** These have no generic standards. Show an informational message, not empty zeros.
4. **Height dict normalization:** Some zones store `max_height_m` as `{"front_building": 10.7, "rear_building": 7.7}`. Always normalize to a single float before PDF rendering.

---

## 8. Open Questions

1. **City scope for v1:** Toronto + Vancouver, or Toronto only to start?  
   → *My recommendation: Toronto v1. Vancouver has 56 zones and OpenDataSoft fragility. Get Toronto solid, then port.*

2. **Parcel geometry in PDF:** Include a static map image of the parcel outline, or just a lat/lng text line?  
   → *Phase 1: text only. Phase 2: static Mapbox static image API.*

3. **Zoning standards depth:** Full rules-engine evaluation (setbacks calculated from lot dimensions) or just table lookup from `ZONE_PARAMS`?  
   → *Phase 1: table lookup. Phase 2: integrate rules engine for dynamic setback calculation.*

4. **Revenue model:** Free tool, or freemium with detailed reports behind auth?  
   → *Out of scope for engineering plan. Ship it, then monetize.*

---

## 9. Success Criteria

The zoning-report tool is "shipped" when:

- [ ] User can search any Toronto address and get correct zone code + params
- [ ] User can click any point on the map and get zoning info
- [ ] PDF report generates with: zoning classification, overlays, development standards, bylaw references
- [ ] Frontend deploys on Vercel, backend on Render, both publicly accessible
- [ ] Old SiteScope-2026 repo still works (we haven't broken the flagship)
- [ ] Monorepo structure is clean enough that adding a third app takes <1 hour

---

*Next action: Execute Phase 1 — move files and create package configs.*
