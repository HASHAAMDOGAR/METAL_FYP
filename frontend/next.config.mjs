/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Standalone build keeps the Modal container image small.
  output: "standalone",
};

export default nextConfig;
