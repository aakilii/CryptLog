#!/usr/bin/env node

import { execFileSync, spawn } from 'node:child_process'
import { existsSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'

const projectRoot = process.cwd()
const flags = new Set(process.argv.slice(2))
const cleanOnly = flags.has('--clean-only')
const skipKill = flags.has('--no-kill')

const RESERVED_FLAGS = new Set(['--clean-only', '--no-kill'])

const log = (message) => {
  console.log(`[dev-safe] ${message}`)
}

const cleanBuildArtifacts = () => {
  for (const folder of ['.next', '.turbo']) {
    const target = resolve(projectRoot, folder)
    if (!existsSync(target)) {
      continue
    }

    rmSync(target, {
      recursive: true,
      force: true,
      maxRetries: 3,
      retryDelay: 100,
    })

    log(`Removed ${folder}`)
  }
}

const escapePowerShell = (value) => value.replace(/'/g, "''")

const killStaleWindowsNextProcesses = () => {
  const targetScript = resolve(
    projectRoot,
    'node_modules',
    'next',
    'dist',
    'server',
    'lib',
    'start-server.js'
  ).toLowerCase()

  const command = [
    `$target = '${escapePowerShell(targetScript)}'`,
    `$current = ${process.pid}`,
    "$matches = Get-CimInstance Win32_Process |",
    "  Where-Object {",
    "    $_.Name -eq 'node.exe' -and",
    "    $_.CommandLine -and",
    "    $_.ProcessId -ne $current -and",
    "    $_.CommandLine.ToLower().Contains($target)",
    "  } |",
    "  Select-Object -ExpandProperty ProcessId",
    'if ($matches) {',
    '  foreach ($procId in $matches) {',
    '    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue',
    '    Write-Output $procId',
    '  }',
    '}',
  ].join('\n')

  const output = execFileSync('powershell.exe', ['-NoProfile', '-Command', command], {
    cwd: projectRoot,
    encoding: 'utf8',
  })

  return output
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => /^\d+$/.test(line))
}

const killStaleUnixNextProcesses = () => {
  const targetScript = resolve(
    projectRoot,
    'node_modules',
    'next',
    'dist',
    'server',
    'lib',
    'start-server.js'
  )

  const rows = execFileSync('ps', ['-eo', 'pid=,args='], {
    cwd: projectRoot,
    encoding: 'utf8',
  })
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)

  const killed = []

  for (const row of rows) {
    const match = row.match(/^(\d+)\s+(.*)$/)
    if (!match) {
      continue
    }

    const pid = Number(match[1])
    const args = match[2]

    if (pid === process.pid) {
      continue
    }

    if (!args.includes(targetScript)) {
      continue
    }

    try {
      process.kill(pid, 'SIGTERM')
      killed.push(String(pid))
    } catch {
      // Ignore transient process errors; startup can proceed.
    }
  }

  return killed
}

const killStaleNextProcesses = () => {
  try {
    const killed = process.platform === 'win32'
      ? killStaleWindowsNextProcesses()
      : killStaleUnixNextProcesses()

    if (killed.length > 0) {
      log(`Stopped stale Next dev process IDs: ${killed.join(', ')}`)
    } else {
      log('No stale Next dev processes found')
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    log(`Could not auto-stop stale Next dev processes: ${message}`)
  }
}

const warnNodeVersion = () => {
  const major = Number.parseInt(process.versions.node.split('.')[0], 10)
  if (Number.isNaN(major) || major >= 18) {
    return
  }

  log(`Node ${process.versions.node} detected. Next.js 14 works best with Node 18+.`)
}

const startNextDev = () => {
  const nextBin = resolve(projectRoot, 'node_modules', 'next', 'dist', 'bin', 'next')

  if (!existsSync(nextBin)) {
    console.error('[dev-safe] Missing Next.js binary. Run npm install in frontend first.')
    process.exit(1)
  }

  const forwardedArgs = process.argv
    .slice(2)
    .filter((arg) => !RESERVED_FLAGS.has(arg))

  const child = spawn(process.execPath, [nextBin, 'dev', ...forwardedArgs], {
    cwd: projectRoot,
    stdio: 'inherit',
    env: process.env,
  })

  child.on('exit', (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal)
      return
    }

    process.exit(code ?? 0)
  })
}

warnNodeVersion()

if (!skipKill) {
  killStaleNextProcesses()
}

cleanBuildArtifacts()

if (!cleanOnly) {
  startNextDev()
}
