/**
 * The size limit for frontend source files and its baseline, shared by
 * eslint.config.ts and scripts/check-max-lines-baseline.ts so both count
 * lines the same way. Every file over the limit fails lint, except the ones
 * in max-lines-baseline.json, which were over it when the limit became an
 * error. Each of those is capped at the size it had then, so it may shrink
 * but never grow, and leaves the list once it fits the limit.
 */
import { readFileSync, writeFileSync } from 'node:fs'

/** Lines of code, without blank lines and comments, a source file may have. */
export const MAX_LINES_OPTIONS = { max: 600, skipBlankLines: true, skipComments: true }

/** The files the limit applies to. Locale files and specs are long by nature. */
export const MAX_LINES_FILES = ['src/**/*.{vue,ts}']
export const MAX_LINES_IGNORES = ['src/core/i18n/locales/**', 'src/**/__tests__/**', 'src/**/*.spec.ts']

const BASELINE_URL = new URL('./max-lines-baseline.json', import.meta.url)

/** The baselined files, relative to frontend/, with the lines each may have at most. */
export function readMaxLinesBaseline(): Record<string, number> {
  return JSON.parse(readFileSync(BASELINE_URL, 'utf8')) as Record<string, number>
}

export function writeMaxLinesBaseline(baseline: Record<string, number>): void {
  const sorted = Object.fromEntries(Object.entries(baseline).sort(([a], [b]) => a.localeCompare(b)))
  writeFileSync(BASELINE_URL, `${JSON.stringify(sorted, null, 2)}\n`)
}
