import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  agentRules: false,
  // API принимает файлы до 20 МБ (MAX_BODY API = 21 MiB); по умолчанию Next режет проксируемое тело на 10 МБ.
  // Лимит 22mb на 1 МБ выше потолка API: Next молча обрезает больший body, и API не успел бы вернуть свой 413.
  experimental: { proxyClientMaxBodySize: "22mb" },
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
