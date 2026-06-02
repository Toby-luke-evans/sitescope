"use client";

import { useState } from "react";
import { Search, MapPin, Download, FileText, ArrowRight, Loader2 } from "lucide-react";
import Link from "next/link";
import { lookupZoning, generatePdf, downloadPdf } from "@/lib/api";
import type { ZoningResponse } from "@/lib/api";

export default function SearchPage() {
  const [lat, setLat] = useState("43.6532");
  const [lng, setLng] = useState("-79.3832");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ZoningResponse | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await lookupZoning(parseFloat(lat), parseFloat(lng));
      setResult(data);
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
          Enter coordinates to look up zoning classification, overlays, and development standards.
        </p>

        <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-3 mb-8">
          <div className="flex-1 flex gap-3">
            <input
              type="number"
              step="any"
              value={lat}
              onChange={(e) => setLat(e.target.value)}
              placeholder="Latitude (e.g. 43.6532)"
              className="flex-1 bg-surface border border-faint rounded-xl px-4 py-3 text-fg placeholder-muted focus:outline-none focus:border-accent transition"
              required
            />
            <input
              type="number"
              step="any"
              value={lng}
              onChange={(e) => setLng(e.target.value)}
              placeholder="Longitude (e.g. -79.3832)"
              className="flex-1 bg-surface border border-faint rounded-xl px-4 py-3 text-fg placeholder-muted focus:outline-none focus:border-accent transition"
              required
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="bg-accent hover:bg-accent-2 text-bg font-semibold py-3 px-6 rounded-xl transition disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading ? <Loader2 size={18} className="animate-spin" /> : <Search size={18} />}
            {loading ? "Loading..." : "Look Up"}
          </button>
        </form>

        {error && (
          <div className="bg-red-900/20 border border-red-500/30 rounded-xl p-4 mb-6 text-red-300">
            {error}
          </div>
        )}

        {result && (
          <>
            <div className="bg-surface border border-faint rounded-2xl p-6 mb-6">
              <div className="flex items-start justify-between mb-6">
                <div>
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
                  className="flex items-center gap-2 bg-accent hover:bg-accent-2 text-bg font-semibold py-2 px-4 rounded-xl transition disabled:opacity-50"
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

                  {/* Overlays */}
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

                  {/* Development Standards */}
                  <h3 className="font-semibold text-lg mb-3 flex items-center gap-2">
                    <FileText size={18} className="text-accent" />
                    Development Standards
                  </h3>
                  <div className="bg-surface-2 rounded-xl p-4 mb-4">
                    <h4 className="text-sm font-semibold text-muted mb-2">Setbacks</h4>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-sm">
                      {Object.entries(result.standards.setbacks).map(([key, val]) => (
                        <div key={key} className="flex justify-between">
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

                    {result.standards.bylaw_reference && (
                      <>
                        <h4 className="text-sm font-semibold text-muted mt-4 mb-2">Bylaw References</h4>
                        <ul className="text-sm text-muted list-disc list-inside">
                          {(Array.isArray(result.standards.bylaw_reference)
                            ? result.standards.bylaw_reference
                            : [result.standards.bylaw_reference]
                          ).map((ref: string, i: number) => (
                            <li key={i}>{ref}</li>
                          ))}
                        </ul>
                      </>
                    )}
                  </div>

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
