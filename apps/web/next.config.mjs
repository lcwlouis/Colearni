const rawBackendBaseUrl = process.env.BACKEND_BASE_URL ?? "http://127.0.0.1:8000";
const backendBaseUrl = rawBackendBaseUrl.replace(/\/$/, "");

/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backendBaseUrl}/:path*` }];
  },
};

export default nextConfig;
