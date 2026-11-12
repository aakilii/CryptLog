/**
 * Generates frontend/app/operation-room/** re-exporting the real Operation Room app
 * from @operation-room/app/... (single-port integration).
 */
import fs from "node:fs"
import path from "node:path"

const orApp = path.resolve("backend/app/phase_5_CISC/operation-room/frontend/src/app")
const outRoot = path.resolve("frontend/app/operation-room")

function walk(dir) {
  const out = []
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, ent.name)
    if (ent.isDirectory()) out.push(...walk(p))
    else if (/^(page|layout|error|global-error)\.(js|tsx)$/.test(ent.name)) {
      out.push(p)
    }
  }
  return out
}

if (!fs.existsSync(orApp)) {
  console.error("missing", orApp)
  process.exit(1)
}

const files = walk(orApp)
for (const abs of files) {
  const rel = path.relative(orApp, abs).replace(/\\/g, "/")
  const ext = path.extname(rel)
  const base = rel.slice(0, -ext.length)
  const importPath = `@operation-room/app/${base}${ext}`

  const outRel = ext === ".js" ? `${base}.tsx` : rel
  const outAbs = path.join(outRoot, outRel)
  fs.mkdirSync(path.dirname(outAbs), { recursive: true })

  const isLayout = rel.endsWith("layout.js") || rel.endsWith("layout.tsx")
  const isRootLayout = rel === "layout.js"
  const content = isRootLayout
    ? `export { default, metadata, viewport } from "${importPath}"\n`
    : isLayout || rel.endsWith("page.js") || rel.endsWith("page.tsx") || rel.endsWith("error.tsx")
      ? `export { default } from "${importPath}"\n`
      : `export { default } from "${importPath}"\n`

  fs.writeFileSync(outAbs, content, "utf8")
  console.log("wrote", path.relative(process.cwd(), outAbs))
}
