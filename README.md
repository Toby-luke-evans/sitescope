# SiteScope Suite

> A suite of planner/developer facing tools for zoning analysis and real estate development.

## What's Here

This monorepo powers the **SiteScope** suite of tools:

| Tool | Description | Status |
|------|-------------|--------|
| **zoning-report** | Parcel lookup + zoning summary + PDF report generation | 🚧 In Progress |
| **hb-you-flagship** | Full HBU analysis, pro forma, 3D envelope, precedent search | 📦 Planned (extract from SiteScope-2026) |

## Repo Structure

```
sitescope/
├── packages/          # Shared libraries (not deployed)
│   ├── zoning-core/   # Zoning lookup, bylaw params, PDF reports
│   ├── spatial-engine/# Geometry, CRS, mesh utilities
│   └── shared-ui/     # Frontend design system (future)
├── apps/              # Independently deployable applications
│   ├── zoning-report/ # NEW: lightweight zoning lookup tool
│   └── hb-you-flagship/# Planned: full SiteScope analysis
└── docs/              # Architecture docs, API specs
```

## Quick Start (Development)

```bash
# 1. Clone and enter the repo
git clone <repo-url> sitescope
cd sitescope

# 2. Start the backend (with hot reload)
docker-compose up backend

# 3. In another terminal, start the frontend
cd apps/zoning-report/frontend
npm install
npm run dev        # runs on http://localhost:3001
```

The backend API will be available at `http://localhost:8000`.

## Architecture Principles

1. **Shared domain in `packages/`** — Zoning bylaws, spatial indices, and report templates live once. Apps import them.
2. **Independently deployable apps** — Each app in `apps/` has its own Dockerfile and can be deployed separately.
3. **No DB for v1** — The zoning-report tool is stateless. All data comes from in-memory spatial indices (CKAN/OpenDataSoft) and static JSON assets.
4. **Dark by default** — All tools share the SiteScope visual identity: dark mode, Playfair Display + JetBrains Mono, `#b18255` accent.

## Tech Stack

- **Backend:** FastAPI + Python 3.12 + Shapely + ReportLab
- **Frontend:** Next.js 16 + React 19 + Tailwind CSS v4
- **Maps:** Mapbox GL (static tiles for PDF, interactive for web)
- **Deploy:** Render (backend) + Vercel (frontend)

## API Surface

See `docs/API-SPEC.md` for full details.

Core endpoints (zoning-report):

| Endpoint | Description |
|----------|-------------|
| `GET /search?q=...` | Address search → parcels |
| `GET /zoning?lat=&lng=` | Full zoning + overlay + standards |
| `POST /reports/pdf` | Generate PDF report |

## Contributing

This is a solo builder project by Toby Evans, with AI assistance from C.A.L.

## License

Proprietary — all rights reserved.
