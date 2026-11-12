/** @type {import('next').NextConfig} */
const backendOrigin = (process.env.OPROOM_BACKEND_ORIGIN || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')
  .replace(/\/api\/?$/, '')
  .replace(/\/+$/, '');

const nextConfig = {
  async redirects() {
    return [
      {
        source: '/cases/:id/report',
        destination: '/cases/:id/studio-v4',
        permanent: false,
      },
      {
        source: '/cases/:id/studio',
        destination: '/cases/:id/studio-v4',
        permanent: false,
      },
      {
        source: '/cases/:id/report-studio',
        destination: '/cases/:id/studio-v4',
        permanent: false,
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: '/api/deep-research/:path*',
        destination: `${backendOrigin}/deep-research/:path*`,
      },
      {
        source: '/api/:path*',
        destination: `${backendOrigin}/api/:path*`,
      },
    ];
  },
  experimental: {
    proxyTimeout: 300000,
  },
  webpack: (config, { isServer }) => {
    // vega-canvas optionally imports the native 'canvas' npm package
    // for server-side SVG rendering. In the browser it uses DOM Canvas.
    // Alias it to false so webpack doesn't try to bundle the native addon.
    config.resolve.alias = {
      ...config.resolve.alias,
      canvas: false,
    };

    return config;
  },
};

export default nextConfig;
