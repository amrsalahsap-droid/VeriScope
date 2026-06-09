/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    unoptimized: true
  },
  async rewrites() {
    return {
      fallback: [
        // Rewrite backend API routes (exclude NextAuth routes)
        {
          source: '/api/github/:path*',
          destination: 'http://localhost:8000/github/:path*',
        },
        {
          source: '/api/repositories/:path*',
          destination: 'http://localhost:8000/github/repositories/:path*',
        },
        {
          source: '/api/recommendations/:path*',
          destination: 'http://localhost:8000/recommendations/:path*',
        },
        {
          source: '/api/readiness/:path*',
          destination: 'http://localhost:8000/readiness/:path*',
        },
        {
          source: '/api/intelligence/:path*',
          destination: 'http://localhost:8000/intelligence/:path*',
        },
      ]
    }
  },
};

module.exports = nextConfig;
