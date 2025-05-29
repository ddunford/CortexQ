/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://core-api:8001/:path*',
      },
    ];
  },
};

module.exports = nextConfig; 