import { describe, it, expect } from 'vitest'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'

/**
 * Repo-wide accessibility guard: every icon-only `<Button>` must
 * carry a non-empty accessible name. A screen reader has nothing else to
 * announce for a Button whose only content is an `icon` prop: it needs
 * `label` (visible text) or `aria-label` (bound via `t(...)`), never
 * hardcoded English strings.
 *
 * This walks the actual source tree rather than a fixed file list, so it
 * catches regressions across the codebase and keeps holding as
 * new icon-only buttons are added later.
 */

const SRC_ROOT = join(__dirname, '..')

function collectVueFiles(dir: string): string[] {
  const entries = readdirSync(dir)
  const files: string[] = []

  for (const entry of entries) {
    if (entry === '__tests__') continue
    const fullPath = join(dir, entry)
    const stats = statSync(fullPath)
    if (stats.isDirectory()) {
      files.push(...collectVueFiles(fullPath))
    } else if (entry.endsWith('.vue')) {
      files.push(fullPath)
    }
  }

  return files
}

interface Violation {
  file: string
  line: number
  snippet: string
}

function findUnlabelledIconButtons(): Violation[] {
  const violations: Violation[] = []
  // Attribute values are skipped as whole quoted strings, so a `>` inside
  // a binding such as an arrow function does not end the tag early.
  const buttonTagRe = /<Button\b((?:[^>"]|"[^"]*")*?)\/>/gs

  for (const file of collectVueFiles(SRC_ROOT)) {
    const content = readFileSync(file, 'utf-8')

    for (const match of content.matchAll(buttonTagRe)) {
      const attrs = match[1] ?? ''
      const hasIcon = /(?<!:)\bicon\s*=/.test(attrs) || /:icon\s*=/.test(attrs)
      if (!hasIcon) continue

      const hasLabel = /(?<!aria-)(?<!:aria-)\blabel\s*=/.test(attrs)
      const hasAriaLabel = /aria-label\s*=/.test(attrs)
      if (hasLabel || hasAriaLabel) continue

      const line = content.slice(0, match.index).split('\n').length
      violations.push({
        file: relative(SRC_ROOT, file),
        line,
        snippet: attrs.trim().replace(/\s+/g, ' ').slice(0, 120),
      })
    }
  }

  return violations
}

describe('a11y guard: icon-only Button accessible names', () => {
  it('every icon-only <Button> has a label or aria-label', () => {
    const violations = findUnlabelledIconButtons()

    if (violations.length > 0) {
      const report = violations
        .map((v) => `  ${v.file}:${v.line} - ${v.snippet}`)
        .join('\n')
      throw new Error(
        `${violations.length} icon-only <Button> element(s) have no accessible name ` +
          `(add label or :aria-label="t(...)"):\n${report}`,
      )
    }

    expect(violations).toHaveLength(0)
  })
})
