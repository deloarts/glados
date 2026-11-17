import { localeTag } from '@/core/utils/dates'
import { finiteNumberOrNull, plainRecordOrNull } from '@/core/utils/guards'
import type { Translate } from '@/core/i18n'

export type { Translate }

/**
 * Turns a saved results snapshot into one line for calculation lists. A
 * snapshot with an unexpected shape (written by an older tool version, say)
 * yields an empty string instead of throwing.
 */
export type Summarizer = (results: Record<string, unknown>, t: Translate) => string

function formatted(value: number, digits = 3): string {
  return new Intl.NumberFormat(localeTag(), { maximumFractionDigits: digits }).format(value)
}

export const summarizeFit: Summarizer = (results, t) => {
  const hole = plainRecordOrNull(results.hole)
  const shaft = plainRecordOrNull(results.shaft)
  const size = finiteNumberOrNull(results.size)
  if (!hole || !shaft || typeof hole.code !== 'string' || typeof shaft.code !== 'string') return ''
  const head = `${size === null ? '' : `Ø${formatted(size)} `}${hole.code}/${shaft.code}`
  const fit = plainRecordOrNull(results.fit)
  const type = fit?.type
  return typeof type === 'string' ? `${head}, ${t(`tools.fitCalculator.types.${type}`)}` : head
}

export const summarizeGeneralTolerances: Summarizer = (results) => {
  const designation = results.designation
  const size = finiteNumberOrNull(results.size)
  const linear = finiteNumberOrNull(results.linear)
  if (typeof designation !== 'string') return ''
  const parts = [designation]
  if (size !== null) parts.push(`${formatted(size)} mm`)
  if (linear !== null) parts.push(`±${formatted(linear)} mm`)
  return parts.join(', ')
}

export const summarizeThreads: Summarizer = (results) => {
  const thread = results.thread
  const cls = results.propertyClass
  const torque = finiteNumberOrNull(results.torque)
  if (typeof thread !== 'string') return ''
  const parts = [typeof cls === 'string' ? `${thread} ${cls}` : thread]
  if (torque !== null) parts.push(`${formatted(torque, 2)} Nm`)
  return parts.join(', ')
}
