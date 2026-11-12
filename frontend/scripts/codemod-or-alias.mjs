/**
 * One-time style: rewrite Operation Room imports from `@/` to `@operation-room/`
 * so the same sources compile inside frontend (single Next app).
 */
import fs from "node:fs"
import path from "node:path"

const root = path.resolve("backend/app/phase_5_CISC/operation-room/frontend/src")

function walk(dir) {
  for (const name of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, name.name)
    if (name.isDirectory()) walk(p)
    else if (/\.(tsx?|jsx?)$/.test(name.name)) {
      let s = fs.readFileSync(p, "utf8")
      const orig = s
      s = s.replace(/from\s+['"]@\//g, "from '@operation-room/")
      s = s.replace(/from\s+["']@\//g, 'from "@operation-room/')
      s = s.replace(/import\s*\(\s*['"]@\//g, "import('@operation-room/")
      if (s !== orig) {
        fs.writeFileSync(p, s)
        console.log("updated", p)
      }
    }
  }
}

if (!fs.existsSync(root)) {
  console.error("missing", root)
  process.exit(1)
}
walk(root)
