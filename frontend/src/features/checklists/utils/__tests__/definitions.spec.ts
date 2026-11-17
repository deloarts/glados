import { describe, expect, it } from 'vitest'

import deAT from '@/core/i18n/locales/checklists/checklists.de-AT'
import enGB from '@/core/i18n/locales/checklists/checklists.en-GB'
import { CHECKLISTS, itemHintKey, itemTextKey, partTitleKey, sectionTitleKey } from '../definitions'
import { CHECKLIST_TYPES, DOCUMENT_KEYS, VERIFICATION_METHODS } from '../types'

type Messages = Record<string, unknown>

/** Looks up a `checklists.*` key in one locale part; undefined when it is missing. */
function lookup(messages: Messages, key: string): unknown {
  const path = key.replace(/^checklists\./, '').split('.')
  let node: unknown = messages
  for (const segment of path) {
    if (node === null || typeof node !== 'object') return undefined
    node = (node as Messages)[segment]
  }
  return node
}

const LOCALES: [string, Messages][] = [
  ['en-GB', enGB],
  ['de-AT', deAT],
]

function leafKeys(obj: Messages, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key
    return value && typeof value === 'object' ? leafKeys(value as Messages, path) : [path]
  })
}

describe.each(CHECKLIST_TYPES)('%s checklist definition', (type) => {
  const definition = CHECKLISTS[type]

  it('has unique item ids and unique section keys', () => {
    const ids = definition.items.map((item) => item.id)
    expect(new Set(ids).size).toBe(ids.length)
    const sections = definition.sections.map((section) => section.key)
    expect(new Set(sections).size).toBe(sections.length)
  })

  it('has no empty parts or sections and starts every section with a main item', () => {
    expect(definition.parts.length).toBeGreaterThan(0)
    for (const part of definition.parts) expect(part.sections.length).toBeGreaterThan(0)
    for (const section of definition.sections) {
      expect(section.items.length).toBeGreaterThan(0)
      expect(section.items[0]?.level).toBe(0)
    }
  })

  it('numbers items cleanly within each section', () => {
    for (const section of definition.sections) {
      const mains = section.items.filter((item) => item.level === 0).map((item) => item.number)
      expect(mains).toEqual(mains.map((_, index) => String(index + 1)))
    }
  })

  it('has every title, item text and hint in both locale parts', () => {
    const keys = [
      ...definition.parts.map((part) => partTitleKey(type, part.key)),
      ...definition.sections.map((section) => sectionTitleKey(type, section.key)),
      ...definition.items.map((item) => itemTextKey(type, item)),
      ...definition.items.filter((item) => item.hint).map((item) => itemHintKey(type, item)),
    ]
    for (const [name, messages] of LOCALES) {
      const missing = keys.filter((key) => typeof lookup(messages, key) !== 'string' || lookup(messages, key) === '')
      expect({ locale: name, missing }).toEqual({ locale: name, missing: [] })
    }
  })

  it('has no orphaned item texts or hints in the locale parts', () => {
    const ids = new Set(definition.items.map((item) => item.id))
    const hinted = new Set(definition.items.filter((item) => item.hint).map((item) => item.id))
    for (const [name, messages] of LOCALES) {
      const typeMessages = messages[type] as Messages
      const orphans = [
        ...leafKeys(typeMessages.items as Messages).filter((id) => !ids.has(id)),
        ...leafKeys(typeMessages.hints as Messages).filter((id) => !hinted.has(id)),
      ]
      expect({ locale: name, orphans }).toEqual({ locale: name, orphans: [] })
    }
  })

  it('cross-references only other items of the same checklist', () => {
    const broken = definition.items.flatMap((item) =>
      item.see.filter((target) => target === item.id || !definition.itemById.has(target)).map((target) => `${item.id} -> ${target}`),
    )
    expect(broken).toEqual([])
  })

  it('cites only known documents', () => {
    const known: readonly string[] = DOCUMENT_KEYS
    const unknown = definition.items.flatMap((item) =>
      item.refs.flatMap((ref) => (ref.kind !== 'machinery' && !known.includes(ref.doc) ? [`${item.id}: ${ref.doc}`] : [])),
    )
    expect(unknown).toEqual([])
  })

  it('lists verification methods for robotics items only', () => {
    const letters: readonly string[] = VERIFICATION_METHODS
    const wrong = definition.items.filter((item) =>
      type === 'robotics'
        ? item.methods.length === 0 || item.methods.some((method) => !letters.includes(method))
        : item.methods.length > 0,
    )
    expect(wrong.map((item) => item.id)).toEqual([])
  })
})

describe('robotics checklist references', () => {
  it('cite ISO 10218-2 first and without clause numbers', () => {
    const items = CHECKLISTS.robotics.items
    const wrong = items.filter(
      (item) =>
        item.refs[0]?.kind !== 'clause' ||
        item.refs[0].doc !== 'iso10218_2' ||
        item.refs.some((ref) => ref.kind !== 'clause' || ref.clause !== undefined),
    )
    expect(wrong.map((item) => item.id)).toEqual([])
  })
})

describe('checklist locale parts', () => {
  it('have an identical key structure', () => {
    expect(leafKeys(deAT).sort()).toEqual(leafKeys(enGB).sort())
  })

  it('label every document', () => {
    for (const [name, messages] of LOCALES) {
      const documents = messages.documents as Messages
      const unlabelled = DOCUMENT_KEYS.filter((key) => typeof documents[key] !== 'string')
      expect({ locale: name, unlabelled }).toEqual({ locale: name, unlabelled: [] })
    }
  })

  it('avoid characters with a meaning in the vue-i18n message syntax', () => {
    for (const [name, messages] of LOCALES) {
      for (const type of CHECKLIST_TYPES) {
        const typeMessages = messages[type] as Messages
        const texts = [...leafKeys(typeMessages)].map((key) => lookup(typeMessages, key))
        const bad = texts.filter((text) => typeof text === 'string' && /[{}@$|]/.test(text))
        expect({ locale: name, type, bad }).toEqual({ locale: name, type, bad: [] })
      }
    }
  })
})
