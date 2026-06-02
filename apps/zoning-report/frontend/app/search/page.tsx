"use client";

import { useState } from "react";
import { Search, MapPin, Download, FileText, ArrowRight, Loader2 } from "lucide-react";
import Link from "next/link";
import { searchAddress, lookupZoning, generatePdf, downloadPdf } from "@/lib/api";
import type { DevelopmentStandards, DevelopmentStandardValue, ParcelPropertyContext, ZoningResponse } from "@/lib/api";

function labelize(key: string) {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatPrimitive(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/\.00$/, "");
  if (typeof value === "string") return value;
  return "";
}

function RenderUnknown({ value }: { value: unknown }) {
  if (value === null || value === undefined || typeof value !== "object") {
    return <span>{formatPrimitive(value)}</span>;
  }
  if (Array.isArray(value)) {
    return (
      <ul className="list-disc list-inside space-y-1">
        {value.map((item, i) => <li key={i}><RenderUnknown value={item} /></li>)}
      </ul>
    );
  }
  return (
    <div className="space-y-1">
      {Object.entries(value as Record<string, unknown>).map(([key, val]) => (
        <div key={key} className="grid grid-cols-[minmax(120px,1fr)_2fr] gap-3">
          <span className="text-muted">{labelize(key)}</span>
          <span className="text-fg"><RenderUnknown value={val} /></span>
        </div>
      ))}
    </div>
  );
}

function PropertyFacts({ context }: { context: ParcelPropertyContext | null | undefined }) {
  if (!context) return null;
  const facts = [
    ["Lot area", context.lot_area_sqm ? `${context.lot_area_sqm.toLocaleString()} m²` : "—"],
    ["Lot frontage", context.lot_frontage_m ? `${context.lot_frontage_m} m` : "—"],
    ["Lot depth", context.lot_depth_m ? `${context.lot_depth_m} m` : "—"],
    ["Corner lot", context.is_corner_lot === null || context.is_corner_lot === undefined ? "Unknown" : context.is_corner_lot ? "Yes" : "No"],
    ["Frontages", context.num_frontages ?? "—"],
    ["Frontage bearing", context.frontage_bearing_deg ? `${context.frontage_bearing_deg}°` : "—"],
    ["Street ROW", context.front_street_row_width_m ? `${context.front_street_row_width_m} m` : "Unavailable"],
  ];

  return (
    <div className="bg-surface-2 rounded-xl p-4 mb-6 border border-faint">
      <h3 className="font-semibold text-lg mb-3 flex items-center gap-2">
        <MapPin size={18} className="text-accent" />
        Property Facts
      </h3>
      <p className="text-muted text-xs mb-4">
        Existing parcel context calculated from City parcel geometry. No proposed or current building assumptions are used here.
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
        {facts.map(([label, value]) => (
          <div key={String(label)} className="bg-surface rounded-lg p-3">
            <p className="text-muted text-xs uppercase tracking-wider mb-1">{label}</p>
            <p className="text-fg font-semibold">{String(value)}</p>
          </div>
        ))}
      </div>
      <details className="text-xs text-muted">
        <summary className="cursor-pointer text-accent-2 mb-2">Sources / confidence</summary>
        <div className="space-y-1">
          {context.frontage_source && <p>Frontage: {context.frontage_source}</p>}
          {context.depth_source && <p>Depth: {context.depth_source}</p>}
          {context.corner_source && <p>Corner status: {context.corner_source}</p>}
          {context.row_width_source && <p>ROW: {context.row_width_source}</p>}
          {context.confidence && Object.keys(context.confidence).length > 0 && (
            <p>Confidence: {Object.entries(context.confidence).map(([k, v]) => `${labelize(k)} ${(v * 100).toFixed(0)}%`).join(" · ")}</p>
          )}
          {context.warnings?.map((warning, i) => <p key={i} className="text-amber-300">{warning}</p>)}
        </div>
      </details>
    </div>
  );
}

function FullDevelopmentStandards({ standards }: { standards: DevelopmentStandards }) {
  return (
    <div className="space-y-4">
      {standards.defaults_used?.length > 0 && (
        <div className="bg-amber-900/20 border border-amber-500/30 rounded-xl p-4 text-amber-200 text-sm">
          <p className="font-semibold mb-2">Sources / data gaps</p>
          <ul className="list-disc list-inside space-y-1">
            {standards.defaults_used.map((item, i) => <li key={i}>{item}</li>)}
          </ul>
        </div>
      )}

      {standards.categories.map((category) => (
        <details key={category.category_id} open={category.category_id < "D"} className="bg-surface-2 rounded-xl border border-faint overflow-hidden">
          <summary className="cursor-pointer px-4 py-3 font-semibold text-fg flex items-center justify-between">
            <span>{category.category_id}. {category.category_name}</span>
            <span className="text-xs text-muted">{Object.keys(category.standards).length} standards</span>
          </summary>
          <div className="border-t border-faint divide-y divide-faint">
            {Object.entries(category.standards).map(([key, standard]: [string, DevelopmentStandardValue]) => (
              <div key={key} className="p-4 text-sm">
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 mb-2">
                  <div>
                    <p className="font-medium text-fg">{labelize(key)}</p>
                    {standard.note && <p className="text-muted text-xs mt-1">{standard.note}</p>}
                  </div>
                  <div className="text-right text-muted text-xs shrink-0">
                    {standard.bylaw_ref && <p>Bylaw §{standard.bylaw_ref}</p>}
                    {standard.is_default && <p className="text-amber-300">Default/assumption</p>}
                  </div>
                </div>
                <div className="text-fg">
                  <RenderUnknown value={standard.value} />
                  {standard.unit && <span className="text-muted ml-1">{standard.unit}</span>}
                </div>
              </div>
            ))}
          </div>
        </details>
      ))}
    </div>
  );
}

export default function SearchPage() {
  const [address, setAddress] = useState("");
  const [selectedAddress, setSelectedAddress] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ZoningResponse | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const fullStandards = result?.development_standards || result?.standards?.development_standards || null;

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    const query = address.trim();
    if (!query) return;

    setLoading(true);
    setError("");
    setResult(null);
    setSelectedAddress("");

    try {
      const search = await searchAddress(query, "toronto", 5);
      const firstParcel = search.results?.[0];

      if (!firstParcel) {
        setError("No Toronto parcel found for that address. Try including the street number and street type, e.g. '77 Ossington Ave'.");
        return;
      }

      if (firstParcel.error) {
        setError(firstParcel.error);
        return;
      }

      const zoning = await lookupZoning(firstParcel.lat, firstParcel.lng, "toronto");
      setResult(zoning);
      setSelectedAddress(firstParcel.address || query);

      if (!zoning.zoning) {
        setError(zoning.note || "Parcel found, but no zoning data was available at its centroid.");
      }
    } catch (err: any) {
      setError(err.message || "Failed to fetch zoning data");
    } finally {
      setLoading(false);
    }
  };

  const handlePdf = async () => {
    if (!result) return;
    setPdfLoading(true);
    try {
      const blob = await generatePdf(result);
      downloadPdf(blob);
    } catch (err: any) {
      setError(err.message || "PDF generation failed");
    } finally {
      setPdfLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-bg text-fg">
      <div className="max-w-3xl mx-auto px-6 py-12">
        <div className="mb-8">
          <Link href="/" className="text-muted text-sm hover:text-fg transition">
            ← Home
          </Link>
        </div>

        <h1 className="font-display text-3xl font-bold mb-2">
          Parcel Search
        </h1>
        <p className="text-muted mb-8">
          Enter a Toronto address to look up zoning classification, overlays, and development standards.
        </p>

        <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-3 mb-8">
          <input
            type="text"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="e.g. 77 Ossington Ave"
            className="flex-1 bg-surface border border-faint rounded-xl px-4 py-3 text-fg placeholder-muted focus:outline-none focus:border-accent transition"
            autoComplete="street-address"
            required
          />
          <button
            type="submit"
            disabled={loading}
            className="bg-accent hover:bg-accent-2 text-bg font-semibold py-3 px-6 rounded-xl transition disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading ? <Loader2 size={18} className="animate-spin" /> : <Search size={18} />}
            {loading ? "Searching..." : "Look Up"}
          </button>
        </form>

        {loading && (
          <div className="bg-accent/10 border border-accent/20 rounded-xl p-4 mb-6 text-accent-2 text-sm flex items-center gap-2">
            <Loader2 size={16} className="animate-spin" />
            Zoning index loading / parcel lookup running...
          </div>
        )}

        {error && (
          <div className="bg-red-900/20 border border-red-500/30 rounded-xl p-4 mb-6 text-red-300">
            {error}
          </div>
        )}

        {result && (
          <>
            <div className="bg-surface border border-faint rounded-2xl p-6 mb-6">
              <div className="flex items-start justify-between mb-6 gap-4">
                <div>
                  <p className="text-muted text-sm mb-1">
                    {selectedAddress || "Selected parcel"}
                  </p>
                  <h2 className="font-display text-2xl font-bold text-fg">
                    {result.zoning?.zone_code || "N/A"}
                  </h2>
                  <p className="text-muted text-sm mt-1">
                    {result.zoning?.zn_string || "No zoning data"}
                  </p>
                </div>
                <button
                  onClick={handlePdf}
                  disabled={pdfLoading || !result.zoning}
                  className="flex items-center gap-2 bg-accent hover:bg-accent-2 text-bg font-semibold py-2 px-4 rounded-xl transition disabled:opacity-50 shrink-0"
                >
                  {pdfLoading ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
                  Export PDF
                </button>
              </div>

              {result.note && (
                <div className="bg-accent/10 border border-accent/20 rounded-xl p-4 mb-4 text-accent-2 text-sm">
                  {result.note}
                </div>
              )}

              {result.zoning && (
                <>
                  <PropertyFacts context={result.property_context || result.parcel?.property_context || result.zoning?.property_context} />

                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-6">
                    <div className="bg-surface-2 rounded-xl p-4">
                      <p className="text-muted text-xs uppercase tracking-wider mb-1">Max FSI</p>
                      <p className="text-fg font-bold text-lg">{result.zoning.max_fsi ?? "—"}</p>
                    </div>
                    <div className="bg-surface-2 rounded-xl p-4">
                      <p className="text-muted text-xs uppercase tracking-wider mb-1">Max Height</p>
                      <p className="text-fg font-bold text-lg">{result.zoning.max_height_m ? `${result.zoning.max_height_m}m` : "—"}</p>
                    </div>
                    <div className="bg-surface-2 rounded-xl p-4">
                      <p className="text-muted text-xs uppercase tracking-wider mb-1">Storeys</p>
                      <p className="text-fg font-bold text-lg">{result.zoning.storeys ?? "—"}</p>
                    </div>
                    <div className="bg-surface-2 rounded-xl p-4">
                      <p className="text-muted text-xs uppercase tracking-wider mb-1">Lot Coverage</p>
                      <p className="text-fg font-bold text-lg">{result.zoning.lot_coverage ? `${result.zoning.lot_coverage}%` : "—"}</p>
                    </div>
                    <div className="bg-surface-2 rounded-xl p-4">
                      <p className="text-muted text-xs uppercase tracking-wider mb-1">Density</p>
                      <p className="text-fg font-bold text-lg">{result.zoning.density ? `${result.zoning.density} units/ha` : "—"}</p>
                    </div>
                    <div className="bg-surface-2 rounded-xl p-4">
                      <p className="text-muted text-xs uppercase tracking-wider mb-1">Standard Set</p>
                      <p className="text-fg font-bold text-lg">{result.zoning.stand_set ?? "—"}</p>
                    </div>
                  </div>

                  <h3 className="font-semibold text-lg mb-3 flex items-center gap-2">
                    <MapPin size={18} className="text-accent" />
                    Overlays
                  </h3>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6">
                    <div className="bg-surface-2 rounded-xl p-3">
                      <p className="text-muted text-xs">Height Overlay</p>
                      <p className="text-fg font-semibold">{result.overlays.height?.height_m ? `${result.overlays.height.height_m}m` : "—"}</p>
                    </div>
                    <div className="bg-surface-2 rounded-xl p-3">
                      <p className="text-muted text-xs">Lot Coverage</p>
                      <p className="text-fg font-semibold">{result.overlays.lot_coverage?.coverage_pct ? `${result.overlays.lot_coverage.coverage_pct}%` : "—"}</p>
                    </div>
                    <div className="bg-surface-2 rounded-xl p-3">
                      <p className="text-muted text-xs">Parking Zone</p>
                      <p className="text-fg font-semibold">{result.overlays.parking_zone?.zone || "—"}</p>
                    </div>
                  </div>

                  <h3 className="font-semibold text-lg mb-3 flex items-center gap-2">
                    <FileText size={18} className="text-accent" />
                    Development Standards
                  </h3>
                  <div className="bg-surface-2 rounded-xl p-4 mb-4">
                    <h4 className="text-sm font-semibold text-muted mb-2">Quick Summary</h4>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-sm">
                      {Object.entries(result.standards.setbacks).map(([key, val]) => (
                        <div key={key} className="flex justify-between gap-3">
                          <span className="text-muted">{key.replace(/_/g, " ")}</span>
                          <span className="text-fg">{val !== null ? `${val}m` : "—"}</span>
                        </div>
                      ))}
                    </div>

                    <h4 className="text-sm font-semibold text-muted mt-4 mb-2">Angular Planes</h4>
                    <p className="text-sm text-fg">
                      {result.standards.angular_planes.applies
                        ? `Applies — ${result.standards.angular_planes.plane_angle_deg}° from ${result.standards.angular_planes.start_height_m}m`
                        : "Not applicable for this zone"}
                    </p>
                  </div>

                  {fullStandards ? (
                    <div className="mb-6">
                      <h3 className="font-semibold text-lg mb-3 flex items-center gap-2">
                        <FileText size={18} className="text-accent" />
                        Full Zoning Analysis
                      </h3>
                      <FullDevelopmentStandards standards={fullStandards} />
                    </div>
                  ) : (
                    <div className="bg-amber-900/20 border border-amber-500/30 rounded-xl p-4 mb-6 text-amber-200 text-sm">
                      Full HB-YOU standards engine did not return categorized standards for this parcel.
                    </div>
                  )}

                  {result.standards.bylaw_reference && (
                    <div className="bg-surface-2 rounded-xl p-4 mb-6">
                      <h4 className="text-sm font-semibold text-muted mb-2">Bylaw References</h4>
                      <ul className="text-sm text-muted list-disc list-inside">
                        {Array.isArray(result.standards.bylaw_reference)
                          ? result.standards.bylaw_reference.map((ref, i) => (
                              <li key={i}>{String(ref)}</li>
                            ))
                          : typeof result.standards.bylaw_reference === "object"
                            ? Object.entries(result.standards.bylaw_reference).map(([label, ref]) => (
                                <li key={label}>
                                  <span className="capitalize">{label.replace(/_/g, " ")}</span>: {ref}
                                </li>
                              ))
                            : <li>{result.standards.bylaw_reference}</li>}
                      </ul>
                    </div>
                  )}

                  <div className="flex gap-3">
                    <Link
                      href={`/report?lat=${result.parcel.lat}&lng=${result.parcel.lng}`}
                      className="flex items-center gap-2 bg-surface-2 hover:bg-surface border border-faint text-fg font-medium py-2 px-4 rounded-xl transition"
                    >
                      View Full Report
                      <ArrowRight size={16} />
                    </Link>
                  </div>
                </>
              )}
            </div>
          </>
        )}
      </div>
    </main>
  );
}
