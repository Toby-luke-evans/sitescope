// API client for Zoning Report backend
const API_BASE = "https://sitescope-zoning-report.onrender.com";

export interface ParcelInfo {
  lat: number;
  lng: number;
  zone_code: string;
  zn_string: string;
}

export interface ZoningData {
  zone_code: string;
  zn_string: string;
  max_fsi: number | null;
  max_height_m: number | null;
  storeys: number | null;
  density: number | null;
  lot_coverage: number | null;
  stand_set: number | null;
}

export interface OverlaysData {
  height: { height_m: number | null; storeys: number | null } | null;
  lot_coverage: { coverage_pct: number | null } | null;
  parking_zone: { zone: string | null } | null;
}

export interface SetbacksData {
  front_m: number | null;
  rear_m: number | null;
  side_interior_m: number | null;
  side_exterior_m: number | null;
  side_total_m: number | null;
}

export interface DevelopmentStandardValue {
  value: unknown;
  unit?: string | null;
  bylaw_ref?: string | null;
  is_default?: boolean;
  note?: string | null;
}

export interface DevelopmentStandardCategory {
  category_id: string;
  category_name: string;
  standards: Record<string, DevelopmentStandardValue>;
}

export interface DevelopmentStandards {
  categories: DevelopmentStandardCategory[];
  defaults_used: string[];
  context_summary: Record<string, unknown>;
}

export interface StandardsData {
  setbacks: SetbacksData;
  angular_planes: {
    applies: boolean;
    plane_angle_deg: number | null;
    start_height_m: number | null;
  };
  bylaw_reference: string[] | string | Record<string, string>;
  development_standards?: DevelopmentStandards | null;
}

export interface ZoningResponse {
  parcel: ParcelInfo;
  zoning: ZoningData | null;
  overlays: OverlaysData;
  standards: StandardsData;
  development_standards?: DevelopmentStandards | null;
  city: string;
  error?: string;
  note?: string;
}

export interface ParcelSearchResult {
  id: string;
  address?: string;
  lat: number;
  lng: number;
  zone_code?: string;
  zn_string?: string;
  zoning: ZoningData | null;
  overlays: OverlaysData;
  error?: string;
}

export interface AddressSearchResponse {
  city: string;
  query: string;
  results: ParcelSearchResult[];
  total: number;
  error?: string;
  note?: string;
}

export async function searchAddress(
  query: string,
  city: string = "toronto",
  limit: number = 5
): Promise<AddressSearchResponse> {
  const res = await fetch(
    `${API_BASE}/search/?city=${encodeURIComponent(city)}&q=${encodeURIComponent(query)}&limit=${limit}`
  );
  if (!res.ok) {
    throw new Error(`Address search failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function lookupZoning(
  lat: number,
  lng: number,
  city: string = "toronto"
): Promise<ZoningResponse> {
  const res = await fetch(
    `${API_BASE}/zoning/?city=${encodeURIComponent(city)}&lat=${lat}&lng=${lng}`
  );
  if (!res.ok) {
    throw new Error(`Zoning lookup failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function generatePdf(
  data: ZoningResponse
): Promise<Blob> {
  const res = await fetch(`${API_BASE}/reports/pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    throw new Error(`PDF generation failed: ${res.status} ${res.statusText}`);
  }
  return res.blob();
}

export async function previewReport(
  data: ZoningResponse
): Promise<unknown> {
  const res = await fetch(`${API_BASE}/reports/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    throw new Error(`Preview failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export function downloadPdf(blob: Blob, filename?: string) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || `zoning-report-${new Date().toISOString().slice(0, 10)}.pdf`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}
// Rebuild: Tue Jun  2 11:23:45 EDT 2026
