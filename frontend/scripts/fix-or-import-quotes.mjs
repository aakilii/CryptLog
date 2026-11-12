import fs from "node:fs"
import path from "node:path"

const root = path.resolve("backend/app/phase_5_CISC/operation-room/frontend/src")

function walk(dir) {
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, ent.name)
    if (ent.isDirectory()) walk(p)
    else if (/\.(tsx?|jsx?)$/.test(ent.name)) {
      let s = fs.readFileSync(p, "utf8")
      const orig = s
      s = s.replaceAll(`from '@operation-room/lib/utils"`, `from '@operation-room/lib/utils'`)
      s = s.replaceAll(
        `from '@operation-room/components/ui/tooltip";`,
        `from '@operation-room/components/ui/tooltip';`
      )
      if (s !== orig) {
        fs.writeFileSync(p, s)
        console.log("fixed", p)
      }
    }
  }
}

walk(root)
