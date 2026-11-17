import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

// The backend serves its collection routes with a trailing slash and
// redirects a request without it, which costs every such call a second
// round trip. The generated client takes its paths from the OpenAPI
// snapshot; this keeps the hand-written calls on the same paths.

const spec = JSON.parse(readFileSync(resolve(process.cwd(), '../backend/openapi/web-v0.1.json'), 'utf8')) as {
  paths: Record<string, Record<string, unknown>>
}

const slashed = new Map<string, Set<string>>()
for (const [path, operations] of Object.entries(spec.paths)) {
  if (!path.startsWith('/api/v1/web/') || !path.endsWith('/')) continue
  slashed.set(path.slice('/api/v1/web'.length, -1), new Set(Object.keys(operations).map((m) => m.toUpperCase())))
}

const sources = import.meta.glob(['/src/**/*.ts', '!/src/**/__tests__/**', '!/src/core/api/generated/**'], {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

const CALL = /api\.(get|post|put|patch|delete)(?:<[^()]*?>)?\(\s*(['`])(\/[^'`?]*)\2/g

describe('hand-written API calls', () => {
  it('use the canonical path of a collection route, with its trailing slash', () => {
    const redirected: string[] = []
    for (const [file, source] of Object.entries(sources)) {
      for (const match of source.matchAll(CALL)) {
        const method = match[1]!.toUpperCase()
        const path = match[3]!
        if (slashed.get(path)?.has(method)) redirected.push(`${file}: ${method} ${path}`)
      }
    }
    expect(redirected).toEqual([])
  })
})
