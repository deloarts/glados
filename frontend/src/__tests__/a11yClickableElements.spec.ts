import { describe, it, expect } from 'vitest'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'

/**
 * Repo-wide accessibility guard: a non-interactive element
 * (`div`/`span`/`li`/`td`/`i`/`p`/`tr`) that carries a `@click` handler must
 * also be keyboard-operable: `role="button"`, `tabindex="0"`, and a
 * keydown/keyup handler (Enter and/or Space), following the pattern
 * established by `ClickableOrderNumber.vue` and `AppSidebar.vue`'s action
 * items. A mouse-only click target strands keyboard and screen-reader users.
 *
 * This walks the actual source tree so it applies to new code as it is
 * added, not just at the time of the change.
 */

const SRC_ROOT = join(__dirname, '..')
const NON_INTERACTIVE_TAGS = ['div', 'span', 'li', 'td', 'i', 'p', 'tr']

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
  tag: string
  snippet: string
}

function findUnkeyableClickTargets(): Violation[] {
  const violations: Violation[] = []
  const tagRe = new RegExp(`<(${NON_INTERACTIVE_TAGS.join('|')})\\b([^>]*?)(/?)>`, 'gs')

  for (const file of collectVueFiles(SRC_ROOT)) {
    const content = readFileSync(file, 'utf-8')

    for (const match of content.matchAll(tagRe)) {
      const tag = match[1] ?? ''
      const attrs = match[2] ?? ''
      const hasClick = /@click\b|v-on:click\b/.test(attrs)
      if (!hasClick) continue

      const hasRole = /\brole\s*=/.test(attrs)
      const hasTabindex = /\btabindex\s*=/.test(attrs)
      const hasKeyHandler = /@keydown\b|@keyup\b|v-on:keydown\b|v-on:keyup\b/.test(attrs)
      if (hasRole && hasTabindex && hasKeyHandler) continue

      const line = content.slice(0, match.index).split('\n').length
      violations.push({
        file: relative(SRC_ROOT, file),
        line,
        tag,
        snippet: attrs.trim().replace(/\s+/g, ' ').slice(0, 120),
      })
    }
  }

  return violations
}

describe('a11y guard: clickable non-interactive elements', () => {
  it('every clickable div/span/li/td/i/p/tr is keyboard-operable', () => {
    const violations = findUnkeyableClickTargets()

    if (violations.length > 0) {
      const report = violations
        .map((v) => `  ${v.file}:${v.line} <${v.tag}> - ${v.snippet}`)
        .join('\n')
      throw new Error(
        `${violations.length} clickable non-interactive element(s) are not keyboard-operable ` +
          `(add role="button" tabindex="0" @keydown.enter @keydown.space.prevent, or use a real ` +
          `<button>/<router-link>):\n${report}`,
      )
    }

    expect(violations).toHaveLength(0)
  })
})
