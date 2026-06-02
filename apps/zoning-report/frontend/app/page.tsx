"use client";

import { Search } from "lucide-react";
import Link from "next/link";

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center bg-bg text-fg">
      <div className="max-w-2xl w-full px-6 text-center">
        <h1 className="font-display text-5xl font-bold mb-4">
          Zoning Report
        </h1>
        <p className="text-muted text-lg mb-8">
          Instant zoning classification, overlay data, and PDF reports for any parcel in Toronto.
        </p>

        <div className="flex gap-2 max-w-md mx-auto">
          <Link
            href="/search"
            className="flex-1 flex items-center justify-center gap-2 bg-accent hover:bg-accent-2 text-bg font-semibold py-3 px-6 rounded-xl transition"
          >
            <Search size={18} />
            Search a Property
          </Link>
        </div>

        <div className="mt-12 flex gap-4 justify-center text-sm text-muted">
          <span>Toronto</span>
          <span>·</span>
          <span>Vancouver (soon)</span>
          <span>·</span>
          <span>PDF Reports</span>
        </div>

        <div className="mt-16 text-xs text-faint">
          <p>Part of the{" "}
            <a
              href="https://hb-you-2026.vercel.app"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent hover:text-accent-2 transition"
            >
              SiteScope
            </a>{" "}
            suite.
          </p>
        </div>
      </div>
    </main>
  );
}
