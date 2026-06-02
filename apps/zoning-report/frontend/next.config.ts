import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  distDir: "dist",
  images: {
    unoptimized: true,
  },
  // In dev: proxy API to local backend
  // In prod: frontend calls NEXT_PUBLIC_API_URL directly
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination:
          (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/:path*",
      },
    ];
  },
};

export default nextConfig;
