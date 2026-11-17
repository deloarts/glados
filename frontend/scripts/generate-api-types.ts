/**
 * Regenerates src/core/api/generated/webSchema.ts from the backend's `web`
 * OpenAPI surface, the one this app's axios client actually talks to
 * (auth/login routes are tagged onto it too, see
 * backend/src/modules/platform/adapters/inbound/api/docs.py).
 *
 * By default reads the committed snapshot at backend/openapi/web-v*.json
 * (written by backend/scripts/export_openapi.py), so no backend needs to be
 * running. Pass --url <http://host:port> to instead fetch a live schema
 * from a running backend (dev convenience while iterating on backend
 * routes ahead of the next snapshot export).
 *
 * Run: npm run generate:api-types
 * Run: npm run generate:api-types -- --url http://localhost:3000
 * Run: npm run check:api-types  (--check: fails instead of writing, if the
 *   committed file is stale relative to the source schema)
 *
 * Without --check the file is rewritten only when its content differs from
 * the fresh output apart from the Generated timestamp.
 */
import { readdir, readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath, pathToFileURL } from 'node:url'
import openapiTS, { astToString } from 'openapi-typescript'

const REPO_ROOT = fileURLToPath(new URL('../../', import.meta.url))
const OPENAPI_DIR = fileURLToPath(new URL('../../backend/openapi/', import.meta.url))
const OUTPUT_PATH = fileURLToPath(
  new URL('../src/core/api/generated/webSchema.ts', import.meta.url),
)

const args = process.argv.slice(2)
const CHECK_MODE = args.includes('--check')

function readUrlFlag(): string | null {
  const i = args.indexOf('--url')
  if (i === -1) return null
  const value = args[i + 1]
  if (!value || value.startsWith('--')) {
    console.error('--url requires a value, e.g. --url http://localhost:3000')
    process.exit(1)
  }
  return value.replace(/\/$/, '')
}
const LIVE_URL = readUrlFlag()

/** Relative, portable label for an absolute path under the repo (falls back
 * to the absolute path itself if it isn't, e.g. a live URL). */
const relLabel = (absPath: string) =>
  absPath.startsWith(REPO_ROOT) ? absPath.slice(REPO_ROOT.length) : absPath

/** The single backend/openapi/web-v*.json snapshot. Errors clearly if none
 * has been exported yet, or if more than one is somehow present. */
async function findSnapshot(): Promise<string> {
  const entries = await readdir(OPENAPI_DIR).catch(() => [] as string[])
  const matches = entries.filter((name) => /^web-v\d+\.\d+\.json$/.test(name)).sort()

  if (matches.length === 0) {
    throw new Error(
      `No web-v*.json snapshot found in ${relLabel(OPENAPI_DIR)}. Run ` +
        '`cd backend && poetry run python scripts/export_openapi.py` first, ' +
        'or pass --url <http://host:port> to read from a live backend instead.',
    )
  }
  if (matches.length > 1) {
    throw new Error(
      `Multiple web-v*.json snapshots found in ${relLabel(OPENAPI_DIR)} ` +
        `(${matches.join(', ')}); expected exactly one, for the current minor version.`,
    )
  }
  return `${OPENAPI_DIR}${matches[0]}`
}

const HEADER = (sourceLabel: string, generatedAt: string) => `/**
 * GENERATED FILE - do not hand-edit.
 * Regenerate with: npm run generate:api-types
 *
 * Source: ${sourceLabel}
 * Generated: ${generatedAt}
 */
`
const stripGeneratedAt = (content: string) => content.replace(/^ \* Generated: .*$/m, '')

async function main() {
  const source = LIVE_URL
    ? new URL(`${LIVE_URL}/api/v1/web/openapi.json`)
    : pathToFileURL(await findSnapshot())
  const sourceLabel = LIVE_URL ? source.href : relLabel(fileURLToPath(source))

  console.log(`Reading schema from ${sourceLabel} ...`)
  let ast: Parameters<typeof astToString>[0]
  try {
    ast = await openapiTS(source)
  } catch (err) {
    console.error(`\nCould not fetch/parse the OpenAPI schema from ${sourceLabel}.`)
    if (LIVE_URL) {
      console.error('Is the backend running there?')
    } else {
      console.error(
        'Re-export it with `cd backend && poetry run python scripts/export_openapi.py`.',
      )
    }
    throw err
  }

  const body = astToString(ast)
  const fresh = HEADER(sourceLabel, new Date().toISOString()) + body
  const committed = await readFile(OUTPUT_PATH, 'utf-8').catch(() => '')
  const upToDate = stripGeneratedAt(committed) === stripGeneratedAt(fresh)

  if (CHECK_MODE && !upToDate) {
    console.error(
      `\n${relLabel(OUTPUT_PATH)} is stale relative to the source schema.\n` +
        'Run `npm run generate:api-types` and commit the result.',
    )
    process.exit(1)
  }
  // An unchanged schema leaves the file alone, so the timestamp only moves
  // when the types do and the pre-commit hook does not dirty the tree.
  if (upToDate) {
    console.log('Generated API types are up to date.')
    return
  }

  await writeFile(OUTPUT_PATH, fresh)
  console.log(`Wrote ${relLabel(OUTPUT_PATH)}`)
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
