"use client";

import { FileText, Download } from "lucide-react";

export default function ReportPage() {
  return (
    <main className="min-h-screen bg-[#090907] text-[#efe7dc]">
      <div className="max-w-4xl mx-auto px-6 py-12">
        <div className="flex items-center justify-between mb-8">
          <h1 className="font-['Playfair_Display'] text-3xl font-bold">
            Zoning Report
          </h1>
          <button className="flex items-center gap-2 bg-[#b18255] hover:bg-[#d6aa72] text-[#090907] font-semibold py-2 px-4 rounded-xl transition">
            <Download size={16} />
            Export PDF
          </button>
        </div>

        <div className="bg-[#11100e] border border-[rgba(239,231,220,0.12)] rounded-2xl p-6 mb-6">
          <h2 className="font-semibold text-lg mb-4 flex items-center gap-2">
            <FileText size={18} />
            Zoning Classification
          </h2>
          <div className="text-[#91887c]">
            Select a property to view its zoning summary.
          </div>
        </div>
      </div>
    </main>
  );
}
