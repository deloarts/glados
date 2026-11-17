import type {
  ChecklistDefinition,
  ChecklistItem,
  ChecklistPart,
  ChecklistSection,
  ChecklistType,
  DocumentKey,
  Reference,
  VerificationMethod,
} from './types'
import { VERIFICATION_METHODS } from './types'

/**
 * Authoring helpers for the checklist definitions. A definition is written as
 * parts, sections and items with stable keys only; numbers are derived from
 * the order, so inserting or removing an item renumbers the list cleanly
 * while ids, texts and saved answers stay attached to the right item.
 */

export interface ItemOptions {
  hint?: boolean
  see?: string[]
}

export interface ItemSpec extends ItemOptions {
  key: string
  level: 0 | 1
  refs: Reference[]
  methods: string
}

export interface SectionSpec {
  key: string
  items: ItemSpec[]
}

export interface PartSpec {
  key: string
  sections: SectionSpec[]
}

export function item(key: string, refs: Reference[] = [], options: ItemOptions = {}): ItemSpec {
  return { key, level: 0, refs, methods: '', ...options }
}

/** A sub-item, numbered below the main item before it (`3.1` after `3`). */
export function sub(key: string, refs: Reference[] = [], options: ItemOptions = {}): ItemSpec {
  return { key, level: 1, refs, methods: '', ...options }
}

/** A robotics item: its verification methods as letters, for example `'ABE'`. */
export function verified(
  key: string,
  methods: string,
  refs: Reference[] = [],
  options: ItemOptions = {},
): ItemSpec {
  return { key, level: 0, refs, methods, ...options }
}

export function section(key: string, items: ItemSpec[]): SectionSpec {
  return { key, items }
}

export function part(key: string, sections: SectionSpec[]): PartSpec {
  return { key, sections }
}

export function clauses(doc: DocumentKey, ...list: string[]): Reference[] {
  return list.length === 0 ? [{ kind: 'clause', doc }] : list.map((clause) => ({ kind: 'clause', doc, clause }))
}

export function intro(doc: DocumentKey): Reference {
  return { kind: 'intro', doc }
}

export function table(doc: DocumentKey, name: string): Reference {
  return { kind: 'table', doc, table: name }
}

export function article(doc: DocumentKey, name: string): Reference {
  return { kind: 'article', doc, article: name }
}

export function annex(doc: DocumentKey, name: string, point?: string): Reference {
  return point === undefined ? { kind: 'annex', doc, annex: name } : { kind: 'annex', doc, annex: name, point }
}

export function machinery(...points: string[]): Reference[] {
  return points.map((point) => ({ kind: 'machinery', point }))
}

function parseMethods(letters: string): VerificationMethod[] {
  return [...letters].filter((letter): letter is VerificationMethod =>
    (VERIFICATION_METHODS as readonly string[]).includes(letter),
  )
}

function numberItems(sectionKey: string, specs: ItemSpec[]): ChecklistItem[] {
  let main = 0
  let subNumber = 0
  return specs.map((spec) => {
    if (spec.level === 0 || main === 0) {
      main += 1
      subNumber = 0
    } else {
      subNumber += 1
    }
    return {
      id: `${sectionKey}.${spec.key}`,
      key: spec.key,
      sectionKey,
      number: subNumber === 0 ? String(main) : `${main}.${subNumber}`,
      level: subNumber === 0 ? 0 : 1,
      refs: spec.refs,
      methods: parseMethods(spec.methods),
      hint: spec.hint === true,
      see: spec.see ?? [],
    }
  })
}

export function buildChecklist(type: ChecklistType, specs: PartSpec[]): ChecklistDefinition {
  const parts: ChecklistPart[] = specs.map((partSpec, partIndex) => {
    const partNumber = String(partIndex + 1)
    return {
      key: partSpec.key,
      number: partNumber,
      sections: partSpec.sections.map(
        (sectionSpec, sectionIndex): ChecklistSection => ({
          key: sectionSpec.key,
          partKey: partSpec.key,
          number: `${partNumber}.${sectionIndex + 1}`,
          items: numberItems(sectionSpec.key, sectionSpec.items),
        }),
      ),
    }
  })
  const sections = parts.flatMap((p) => p.sections)
  const items = sections.flatMap((s) => s.items)
  return {
    type,
    parts,
    sections,
    items,
    itemById: new Map(items.map((i) => [i.id, i])),
    sectionByKey: new Map(sections.map((s) => [s.key, s])),
  }
}
