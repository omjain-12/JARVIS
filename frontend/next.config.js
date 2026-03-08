/** @type {import('next').NextConfig} */
const backendApiUrl = process.env.BACKEND_API_URL || "http://localhost:8001";

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendApiUrl}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
