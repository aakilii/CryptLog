/**
 * Links `vendor/operation-room` → real Operation Room `src` so Turbopack (root = frontend)
 * can resolve `@operation-room/*` without traversing outside the project boundary.
 */
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(__dirname, "..")
const target = path.resolve(frontendRoot, "../backend/app/phase_5_CISC/operation-room/frontend/src")
const link = path.join(frontendRoot, "vendor", "operation-room")

if (!fs.existsSync(target)) {
  console.error("missing target", target)
  process.exit(1)
}
fs.mkdirSync(path.dirname(link), { recursive: true })
if (fs.existsSync(link)) {
  console.log("already linked", link)
  process.exit(0)
}
fs.symlinkSync(target, link, process.platform === "win32" ? "junction" : "dir")
console.log("linked", link, "->", target)
