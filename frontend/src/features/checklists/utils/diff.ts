import { HEADER_OWNER_FIELDS, HEADER_TEXT_FIELDS } from './state'
import type { ChecklistDefinition, ChecklistItem } from './types'

/**
 * Compares two revisions of a checklist: which header fields changed, and
 * which items got a different answer or remark. Both sides are read as they
 * were stored, keyed by item id, so an answer to an item the checklist type
 * no longer has still shows up, without its text.
 */

export interface ChecklistSnapshot {
  header: Readonly<Record<string, string>>
  answers: Readonly<Record<string, string>>
  remarks: Readonly<Record<string, string>>
}

export interface ItemSide {
  answer: string | null
  remark: string
}

export interface ItemChange {
  id: string
  /** The item in the current definition, null for one the type no longer has. */
  item: ChecklistItem | null
  before: ItemSide
  after: ItemSide
  answerChanged: boolean
  remarkChanged: boolean
}

export interface HeaderChange {
  field: string
  before: string
  after: string
}

export interface ChecklistDiff {
  header: HeaderChange[]
  /** In checklist order; items the type no longer has come last. */
  items: ItemChange[]
  changedIds: ReadonlySet<string>
}

const HEADER_ORDER: readonly string[] = [...HEADER_OWNER_FIELDS, 'legalBasis', ...HEADER_TEXT_FIELDS]

function headerOrder(field: string): number {
  const index = HEADER_ORDER.indexOf(field)
  return index === -1 ? HEADER_ORDER.length : index
}

function side(snapshot: ChecklistSnapshot, id: string): ItemSide {
  return { answer: snapshot.answers[id] ?? null, remark: (snapshot.remarks[id] ?? '').trim() }
}

export function diffChecklists(
  definition: ChecklistDefinition,
  before: ChecklistSnapshot,
  after: ChecklistSnapshot,
): ChecklistDiff {
  const fields = new Set([...Object.keys(before.header), ...Object.keys(after.header)])
  const header = [...fields]
    .map((field) => ({
      field,
      before: (before.header[field] ?? '').trim(),
      after: (after.header[field] ?? '').trim(),
    }))
    .filter((change) => change.before !== change.after)
    .sort((a, b) => headerOrder(a.field) - headerOrder(b.field) || a.field.localeCompare(b.field))

  const ids = new Set([
    ...Object.keys(before.answers),
    ...Object.keys(after.answers),
    ...Object.keys(before.remarks),
    ...Object.keys(after.remarks),
  ])
  const position = new Map(definition.items.map((item, index) => [item.id, index]))
  const items: ItemChange[] = []
  for (const id of ids) {
    const was = side(before, id)
    const now = side(after, id)
    const answerChanged = was.answer !== now.answer
    const remarkChanged = was.remark !== now.remark
    if (!answerChanged && !remarkChanged) continue
    items.push({ id, item: definition.itemById.get(id) ?? null, before: was, after: now, answerChanged, remarkChanged })
  }
  items.sort((a, b) => {
    const pa = position.get(a.id) ?? Number.MAX_SAFE_INTEGER
    const pb = position.get(b.id) ?? Number.MAX_SAFE_INTEGER
    return pa - pb || a.id.localeCompare(b.id)
  })

  return { header, items, changedIds: new Set(items.map((change) => change.id)) }
}
