/**
 * Keeps the max-lines baseline honest.
 *
 * ESLint fails every source file over the size limit, except the files in
 * max-lines-baseline.json, which each have their own cap. This check measures
 * the baselined files with the limit itself and fails when an entry is no
 * longer needed: the file is gone or fits the limit, so it would otherwise
 * keep room to grow back. A file that shrank but is still over the limit is
 * reported with its new size, so its cap can follow it down.
 *
 * `--write` applies both: it lowers each cap to the file's current size and
 * drops the entries that are no longer needed. It never adds a file or raises
 * a cap; a file over the limit is split instead.
 *
 * Run: npm run lint:check:max-lines (add `-- --write` to update the baseline)
 */
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { ESLint } from 'eslint'

import {
  MAX_LINES_OPTIONS,
  readMaxLinesBaseline,
  writeMaxLinesBaseline,
} from '../eslint.max-lines'

const ROOT = fileURLToPath(new URL('..', import.meta.url))
const write = process.argv.includes('--write')

/** The size of each file in lines as max-lines counts them, or null when within the limit. */
async function measure(files: string[]): Promise<Map<string, number | null>> {
  const eslint = new ESLint({
    cwd: ROOT,
    ruleFilter: ({ ruleId }) => ruleId === 'max-lines',
    // Every baselined file is measured against the limit itself, so the
    // message carries its size; nothing here needs type information.
    overrideConfig: {
      languageOptions: { parserOptions: { projectService: false, project: null } },
      rules: { 'max-lines': ['error', MAX_LINES_OPTIONS] },
    },
  })
  const sizes = new Map<string, number | null>()
  for (const result of await eslint.lintFiles(files)) {
    const file = result.filePath.slice(ROOT.length)
    const message = result.messages.find((m) => m.ruleId === 'max-lines')
    const size = message ? /\((\d+)\)/.exec(message.message)?.[1] : undefined
    sizes.set(file, size === undefined ? null : Number(size))
  }
  return sizes
}

const baseline = readMaxLinesBaseline()
const listed = Object.keys(baseline)
const present = listed.filter((file) => existsSync(new URL(`../${file}`, import.meta.url)))
const sizes = await measure(present)

const stale: string[] = []
const shrunk: string[] = []
const next: Record<string, number> = {}

for (const file of listed) {
  const cap = baseline[file]!
  if (!present.includes(file)) {
    stale.push(`${file}: listed, but the file no longer exists`)
    continue
  }
  const size = sizes.get(file) ?? null
  if (size === null) {
    stale.push(`${file}: listed, but it fits the limit of ${MAX_LINES_OPTIONS.max} lines now`)
    continue
  }
  if (size < cap) shrunk.push(`${file}: ${size} lines, its cap is ${cap}`)
  next[file] = Math.min(size, cap)
}

if (write) {
  writeMaxLinesBaseline(next)
  console.log(
    `max-lines baseline written: ${Object.keys(next).length} files, ` +
      `${stale.length} entries dropped, ${shrunk.length} caps lowered.`,
  )
  process.exit(0)
}

if (shrunk.length > 0) {
  console.log('Baselined files that shrank; `npm run lint:check:max-lines -- --write` lowers their caps:')
  for (const line of shrunk) console.log(`  ${line}`)
}

if (stale.length > 0) {
  console.error('max-lines baseline entries that are no longer needed; remove them or run with --write:')
  for (const line of stale) console.error(`  ${line}`)
  process.exit(1)
}

console.log(`max-lines baseline OK: ${listed.length} files over the limit, each still needs its entry.`)
