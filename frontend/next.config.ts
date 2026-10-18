import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  agentRules: false,
  // API принимает файлы до 20 МБ; по умолчанию Next режет проксируемое тело на 10 МБ.
  experimental: { proxyClientMaxBodySize: "21mb" },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.API_URL ?? "http://127.0.0.1:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
