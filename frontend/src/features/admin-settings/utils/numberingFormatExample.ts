import { todayStart } from '@/core/utils/dates'

// Mirrors src/modules/platform/domain/services/numbering_format.py::render_example on the
// backend so the preview updates live as the user types, without a round
// trip. Keep in sync with that module if the placeholder syntax changes.

const SEQ_TOKEN_RE = /\{seq(?::0(\d+)d)?\}$/
const DATE_PLACEHOLDER_RE = /\{(year|yy|month)\}/g

export function renderNumberFormatExample(
  template: string,
  today: Date = todayStart(),
): string | null {
  const seqMatch = SEQ_TOKEN_RE.exec(template)
  if (!seqMatch) return null

  const width = seqMatch[1] ? Number(seqMatch[1]) : 1
  const year = today.getFullYear()
  const values: Record<'year' | 'yy' | 'month', string> = {
    year: String(year).padStart(4, '0'),
    yy: String(year % 100).padStart(2, '0'),
    month: String(today.getMonth() + 1).padStart(2, '0'),
  }

  const prefix = template
    .slice(0, seqMatch.index)
    .replace(DATE_PLACEHOLDER_RE, (_match, key: string) => values[key as 'year' | 'yy' | 'month'])

  return `${prefix}${'1'.padStart(width, '0')}`
}
