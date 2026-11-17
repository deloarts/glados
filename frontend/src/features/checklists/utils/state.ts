import { todayStart } from '@/core/utils/dates'
import { legalBasisFor } from '@/features/products'
import { ANSWERS } from './types'
import type { Answer, ChecklistDefinition, ChecklistHeader, ChecklistState } from './types'

export { legalBasisFor }

/** Longest value of a one-line header field, of the reason and notes, and of a remark. */
export const MAX_FIELD_LENGTH = 200
export const MAX_TEXT_LENGTH = 2000

/** The header fields holding a date, every other text field holds free text. */
export const HEADER_DATE_FIELDS = ['placingOnMarket', 'assessedOn'] as const

/** The free-text header fields that take several lines. */
export const HEADER_LONG_FIELDS = ['reason', 'notes'] as const

/**
 * The text header fields copied from the checklist's owner and its product,
 * never typed in. The legal basis is copied with them.
 */
export const HEADER_OWNER_FIELDS = [
  'ownerNumber',
  'ownerCustomer',
  'ownerProduct',
  'ownerManager',
  'designation',
  'machineType',
  'placingOnMarket',
  'installationSite',
  'installationLocation',
] as const
export type HeaderOwnerField = (typeof HEADER_OWNER_FIELDS)[number]

export type HeaderTextField = Exclude<keyof ChecklistHeader, 'legalBasis' | HeaderOwnerField>

export const HEADER_TEXT_FIELDS: readonly HeaderTextField[] = [
  'assessedBy',
  'assessedOn',
  'reason',
  'notes',
]

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/

/** True for a real calendar date written as `YYYY-MM-DD`. */
export function isIsoDate(value: string): boolean {
  const match = ISO_DATE.exec(value)
  if (!match) return false
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])]
  const date = new Date(Date.UTC(year, month - 1, day))
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day
}

export function emptyHeader(today: Date = todayStart()): ChecklistHeader {
  return {
    ownerNumber: '',
    ownerCustomer: '',
    ownerProduct: '',
    ownerManager: '',
    designation: '',
    machineType: '',
    placingOnMarket: '',
    installationSite: '',
    installationLocation: '',
    legalBasis: legalBasisFor('', today),
    assessedBy: '',
    assessedOn: '',
    reason: '',
    notes: '',
  }
}

export function emptyState(today: Date = todayStart()): ChecklistState {
  return { header: emptyHeader(today), answers: {}, remarks: {} }
}

function limit(value: string, field: keyof ChecklistHeader): string {
  const max = (HEADER_LONG_FIELDS as readonly string[]).includes(field) ? MAX_TEXT_LENGTH : MAX_FIELD_LENGTH
  return value.slice(0, max)
}

/**
 * Reads the header a checklist was saved with. Unknown keys are dropped, a
 * date that is not a real date is cleared, and a missing legal basis is
 * derived from the planned placing on the market.
 */
export function headerFromRecord(record: Readonly<Record<string, string>>): ChecklistHeader {
  const header = emptyHeader()
  for (const field of [...HEADER_OWNER_FIELDS, ...HEADER_TEXT_FIELDS]) {
    const value = record[field]
    if (typeof value === 'string') header[field] = limit(value, field)
  }
  for (const field of HEADER_DATE_FIELDS) {
    if (header[field] !== '' && !isIsoDate(header[field])) header[field] = ''
  }
  const basis = record.legalBasis
  header.legalBasis = basis === 'directive' || basis === 'regulation' ? basis : legalBasisFor(header.placingOnMarket)
  return header
}

/** The header as the plain record the backend stores; empty fields are left out. */
export function headerToRecord(header: Readonly<ChecklistHeader>): Record<string, string> {
  const record: Record<string, string> = { legalBasis: header.legalBasis }
  for (const field of [...HEADER_OWNER_FIELDS, ...HEADER_TEXT_FIELDS]) {
    const value = header[field].trim()
    if (value !== '') record[field] = value
  }
  return record
}

const ANSWER_SET: ReadonlySet<string> = new Set(ANSWERS)

/**
 * Reads the answers and remarks a checklist was saved with against the
 * current definition. Entries for items the definition no longer has are
 * left out and counted, so the page can say that some answers were dropped.
 */
export function answersFromRecord(
  definition: ChecklistDefinition,
  answers: Readonly<Record<string, string>>,
  remarks: Readonly<Record<string, string>>,
): { answers: Record<string, Answer>; remarks: Record<string, string>; dropped: number } {
  const keptAnswers: Record<string, Answer> = {}
  const keptRemarks: Record<string, string> = {}
  const dropped = new Set<string>()
  for (const [id, value] of Object.entries(answers)) {
    if (!definition.itemById.has(id) || !ANSWER_SET.has(value)) dropped.add(id)
    else keptAnswers[id] = value as Answer
  }
  for (const [id, value] of Object.entries(remarks)) {
    if (!definition.itemById.has(id)) dropped.add(id)
    else if (value.trim() !== '') keptRemarks[id] = value.slice(0, MAX_TEXT_LENGTH)
  }
  return { answers: keptAnswers, remarks: keptRemarks, dropped: dropped.size }
}
