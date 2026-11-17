import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it, beforeEach } from 'vitest'

import { sourceItemDisplayLabel } from '../madeItemLabel'

import type { MadeItemResponse } from '../../types/madeItemsResponse'
import type { LocalizedText } from '@/shared/utils/localizedText'

type Linked = Pick<MadeItemResponse, 'bought_item' | 'source_item'>

function loc(text: string): LocalizedText {
  return { enGB: text }
}

function linked(overrides: Partial<Linked>): Linked {
  return { bought_item: null, source_item: null, ...overrides } as Linked
}

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('sourceItemDisplayLabel', () => {
  it('shows a bought item with both order codes', () => {
    const item = linked({
      bought_item: { article_name: 'Bracket', order_code_1: 'A-1', order_code_2: 'B-2' },
    } as Partial<Linked>)
    expect(sourceItemDisplayLabel(item)).toBe('Bracket (A-1 / B-2)')
  })

  it('shows a bought item with its first order code alone', () => {
    const item = linked({
      bought_item: { article_name: 'Bracket', order_code_1: 'A-1', order_code_2: null },
    } as Partial<Linked>)
    expect(sourceItemDisplayLabel(item)).toBe('Bracket (A-1)')
  })

  it('shows a source item by type name, else by material', () => {
    expect(
      sourceItemDisplayLabel(linked({ source_item: { type_name: loc('Round bar'), material: 'S235' } } as Partial<Linked>)),
    ).toBe('Round bar')
    expect(
      sourceItemDisplayLabel(linked({ source_item: { type_name: loc(''), material: 'S235' } } as Partial<Linked>)),
    ).toBe('S235')
  })

  it('shows a dash when nothing is linked', () => {
    expect(sourceItemDisplayLabel(linked({}))).toBe('-')
  })
})
