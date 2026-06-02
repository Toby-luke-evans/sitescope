# Deploying Zoning Report

## Backend (Render)

The backend is configured with `render.yaml` at the repo root.

1. Push this repo to GitHub (`Toby-luke-evans/sitescope`)
2. In Render Dashboard: **New Web Service → Build and deploy from Git repository**
3. Select `Toby-luke-evans/sitescope`
4. Render auto-detects `render.yaml`
5. Service name: `zoning-report-backend`
6. Region: Ohio (or closest to your users)
7. Plan: Free

**Environment variables (auto-set by render.yaml):**
- `PYTHONPATH`: `/app/apps/zoning-report/backend/app:/app/packages/zoning-core/src:/app/packages/spatial-engine/src`

**Health check:** `GET /health` returns `{"status":"ok","service":"zoning-report","zoning_index_loaded":true/false}`

**API endpoints:**
- `GET /health`
- `GET /zoning/?city={city}&lat={lat}&lng={lng}`
- `POST /reports/pdf` — Returns `application/pdf`
- `POST /reports/preview` — Returns JSON preview

## Frontend (Vercel)


cd apps/zoning-report/frontend
npm install
npm run build
vercel --prod

Or connect GitHub repo to Vercel with:
- Framework: Next.js
- Root directory: `apps/zoning-report/frontend`
- Build command: `npm run build`
- Output directory: `dist`

**Environment variables in Vercel Dashboard:**
- `NEXT_PUBLIC_API_URL`: `https://zoning-report-backend.onrender.com` (your Render URL)

## Linking from SiteScope Landing Page

Add a "Zoning Report" CTA button to the SiteScope landing page (`frontend/src/app/page.tsx`):

```tsx
<Link
  href="https://zoning-report.vercel.app"  // or /zoning-report if same domain
  className="..."
>
  Zoning Report
</Link>
```

## Testing After Deploy

```bash
# Test health
curl https://zoning-report-backend.onrender.com/health

# Test zoning lookup
curl "https://zoning-report-backend.onrender.com/zoning/?city=toronto&lat=43.6532&lng=-79.3832"

# Test PDF generation (requires JSON payload)
curl -X POST https://zoning-report-backend.onrender.com/reports/pdf \
  -H "Content-Type: application/json" \
  -d '{
    "parcel": {"lat":43.6532,"lng":-79.3832,"zone_code":"CR","zn_string":"CR T3.0"},
    "zoning": {"zone_code":"CR","zn_string":"CR T3.0","max_fsi":3.0,"max_height_m":30,"storeys":10},
    "overlays": {"height":{"height_m":30,"storeys":10},"lot_coverage":{"coverage_pct":45},"parking_zone":{"zone":"A"}},
    "standards": {"setbacks":{"front_m":0,"rear_m":7.5},"angular_planes":{"applies":false},"bylaw_reference":["Section 4.1"]},
    "city":"toronto"
  }'
```
