import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Zoning Report — Parcel Lookup & Zoning Summary",
  description: "Instant zoning classification, overlay data, and PDF reports for any parcel.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600;700&family=Playfair+Display:wght@600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
