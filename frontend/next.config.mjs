import { createRequire } from 'module'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const operationRoomSrc = path.resolve(
  __dirname,
  '../backend/app/phase_5_CISC/operation-room/frontend/src',
)
const require = createRequire(import.meta.url)
const { loadEnvConfig } = require('@next/env')
// Load .env / .env.local from this app folder (frontend), not from process.cwd() when that differs.
loadEnvConfig(__dirname)

/** Monolith API (Phases 1–4). Set NEXT_PUBLIC_API_URL in Vercel to your Python backend URL. */
const monolithOrigin = (process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000').replace(
  /\/+$/,
  '',
)

/** Must include `/api/phase5` when using the Forensic Engine monolith (Phase 5 mount). */
const backendOrigin = (
  process.env.OPROOM_BACKEND_ORIGIN ||
  process.env.NEXT_PUBLIC_OPROOM_BACKEND_ORIGIN ||
  `${monolithOrigin}/api/phase5`
).replace(/\/+$/, '')

const repoRoot = path.join(__dirname, '..')

/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  /** Monorepo: trace files outside csic_frontend (Operation Room under app/phase_5_CISC). */
  outputFileTracingRoot: repoRoot,
  async rewrites() {
    return [
      {
        source: '/api/deep-research/:path*',
        destination: `${backendOrigin}/api/deep-research/:path*`,
      },
      {
        source: '/api/:path*',
        destination: `${monolithOrigin}/api/:path*`,
      },
    ]
  },
  experimental: {
    externalDir: true,
    proxyTimeout: 300000,
  },
  webpack(config) {
    const nm = path.join(__dirname, 'node_modules')
    config.resolve.modules = [nm, ...(config.resolve.modules || ['node_modules'])]
    config.resolve.alias = {
      ...config.resolve.alias,
      '@operation-room': operationRoomSrc,
      canvas: path.join(__dirname, 'lib/empty-module.js'),
    }
    // Operation Room sources use `@/` for their own src tree (not csic_frontend root).
    config.module.rules.push({
      test: /\.(tsx|ts|jsx|js)$/,
      include: [operationRoomSrc],
      resolve: {
        alias: {
          '@': operationRoomSrc,
        },
      },
    })
    return config
  },
  turbopack: {
    root: repoRoot,
    resolveAlias: {
      canvas: path.join(__dirname, 'lib/empty-module.js'),
    },
  },
  // Ensure client bundle receives these even if cwd-based loading missed .env.local
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000',
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL || '',
    NEXT_PUBLIC_GOOGLE_CLIENT_ID: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || '',
    NEXT_PUBLIC_GOOGLE_API_KEY: process.env.NEXT_PUBLIC_GOOGLE_API_KEY || '',
    NEXT_PUBLIC_CSIC_DEMO_MODE: process.env.NEXT_PUBLIC_CSIC_DEMO_MODE || '',
    /** Operation Room “home” when embedded in this app (see middleware + app/operation-room). */
    NEXT_PUBLIC_OR_OPERATION_HOME: process.env.NEXT_PUBLIC_OR_OPERATION_HOME || '/operation-room',
  },
}

export default nextConfig
