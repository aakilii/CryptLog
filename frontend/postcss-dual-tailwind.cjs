'use strict'

const path = require('path')
const postcss = require('postcss')
const tailwind3 = require('tailwindcss-v3')
const autoprefixer = require('autoprefixer')
const tailwind4 = require('@tailwindcss/postcss')

// Bundled with frontend so Vercel always has it (repo tailwind.config.js may be .vercelignore'd).
const orTailwindConfig = path.join(__dirname, 'operation-room.tailwind.config.cjs')

const operationRoomPlugins = [
  tailwind3({ config: orTailwindConfig }),
  autoprefixer(),
]

function replaceAstInPlace(targetRoot, newRoot) {
  targetRoot.removeAll()
  newRoot.each((node) => {
    targetRoot.append(node.clone())
  })
}

function isOperationRoomCss(from, input) {
  const normalized = String(from || '').replace(/\\/g, '/')
  if (normalized.includes('phase_5_CISC/operation-room/frontend')) return true
  if (
    input &&
    input.includes('@tailwind base') &&
    input.includes('@tailwind components') &&
    input.includes('@tailwind utilities')
  ) {
    return true
  }
  return false
}

/**
 * Routes Operation Room CSS through Tailwind v3; everything else through @tailwindcss/postcss (v4).
 * Next.js does not allow a function `postcss.config`, so this is a single PostCSS plugin.
 */
module.exports = {
  postcssPlugin: 'dual-tailwind-or-router',
  async Once(root, result) {
    const from =
      result.opts?.from ??
      result.root?.source?.input?.from ??
      root.source?.input?.from ??
      root.source?.input?.file ??
      ''
    const input = root.source?.input?.css ?? root.toString()

    if (isOperationRoomCss(from, input)) {
      const fromOpt =
        from ||
        path.join(
          __dirname,
          '..',
          'backend',
          'app',
          'phase_5_CISC',
          'operation-room',
          'frontend',
          'src',
          'app',
          'globals.css',
        )
      const out = await postcss(operationRoomPlugins).process(input, {
        from: fromOpt,
      })
      replaceAstInPlace(root, out.root)
      return
    }

    const pack = tailwind4()
    const chain = pack.plugins && Array.isArray(pack.plugins) ? pack.plugins : [pack]
    const fromOpt =
      from ||
      path.join(__dirname, 'app', 'globals.css')
    const out = await postcss(chain).process(input, { from: fromOpt })
    replaceAstInPlace(root, out.root)
  },
}
