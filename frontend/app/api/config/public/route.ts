import { loadEnvConfig } from "@next/env"
import { NextResponse } from "next/server"
import { existsSync, readFileSync } from "fs"
import { join } from "path"

export const dynamic = "force-dynamic"

const NEXT_CONFIG_NAMES = ["next.config.mjs", "next.config.ts", "next.config.js"] as const

/** Directory that contains next.config.* (works when cwd is repo root or frontend). */
function resolveNextAppRoot(): string {
  const cwd = process.cwd()
  for (const name of NEXT_CONFIG_NAMES) {
    if (existsSync(join(cwd, name))) return cwd
  }
  const nested = join(cwd, "frontend")
  for (const name of NEXT_CONFIG_NAMES) {
    if (existsSync(join(nested, name))) return nested
  }
  return cwd
}

loadEnvConfig(resolveNextAppRoot())

function trimVal(v: string | undefined): string {
  if (v == null) return ""
  let t = v.trim()
  if (
    (t.startsWith('"') && t.endsWith('"')) ||
    (t.startsWith("'") && t.endsWith("'"))
  ) {
    t = t.slice(1, -1).trim()
  }
  return t
}

/** Minimal .env parser (KEY=value, # comments). */
function parseDotEnv(content: string): Record<string, string> {
  const out: Record<string, string> = {}
  for (const rawLine of content.split(/\r?\n/)) {
    let line = rawLine.trim()
    if (!line || line.startsWith("#")) continue
    const eq = line.indexOf("=")
    if (eq === -1) continue
    let key = line.slice(0, eq).trim()
    if (key.startsWith("export ")) key = key.slice(7).trim()
    let val = line.slice(eq + 1).trim()
    if (
      (val.startsWith('"') && val.endsWith('"')) ||
      (val.startsWith("'") && val.endsWith("'"))
    ) {
      val = val.slice(1, -1)
    }
    out[key] = val
  }
  return out
}

function readEnvDir(dir: string, into: Record<string, string>) {
  for (const name of [".env", ".env.local"] as const) {
    const p = join(dir, name)
    if (!existsSync(p)) continue
    try {
      Object.assign(into, parseDotEnv(readFileSync(p, "utf8")))
    } catch {
      /* ignore */
    }
  }
}

/**
 * Load .env files from disk. Supports:
 * - `npm run dev` with cwd = frontend
 * - cwd = repo root with frontend/.env.local
 */
function loadPublicEnvFromDisk(): Record<string, string> {
  const merged: Record<string, string> = {}
  const appRoot = resolveNextAppRoot()
  readEnvDir(appRoot, merged)
  readEnvDir(process.cwd(), merged)
  readEnvDir(join(process.cwd(), "frontend"), merged)

  let up = process.cwd()
  for (let i = 0; i < 5; i++) {
    const parent = dirname(up)
    if (parent === up) break
    readEnvDir(join(parent, "frontend"), merged)
    up = parent
  }
  return merged
}

export async function GET() {
  const disk = loadPublicEnvFromDisk()

  const googleClientId = trimVal(
    disk.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID,
  )
  const googleApiKey = trimVal(
    disk.NEXT_PUBLIC_GOOGLE_API_KEY ?? process.env.NEXT_PUBLIC_GOOGLE_API_KEY,
  )
  const apiUrl =
    trimVal(
      disk.NEXT_PUBLIC_API_URL ?? process.env.NEXT_PUBLIC_API_URL,
    ) || "http://127.0.0.1:8000"

  return NextResponse.json({
    googleClientId,
    googleApiKey,
    apiUrl,
  })
}
