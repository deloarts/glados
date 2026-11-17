import { describe, it, expect } from 'vitest'

import { methodOptions } from '../lotStepMethodOptions'

// LotStepList.vue's fabrication and inspection method options, one function
// for both since they differ only in which Pinia store they read.

interface Item {
  id: number
  name: string
  archived: boolean
}

function makeStore(items: Item[]) {
  return { items }
}

function item(overrides: Partial<Item> = {}): Item {
  return { id: 1, name: 'A', archived: false, ...overrides }
}

describe('methodOptions', () => {
  it('returns every item, including archived ones', () => {
    const items = [item({ id: 1, archived: false }), item({ id: 2, archived: true })]

    expect(methodOptions(makeStore(items)).map((i) => i.id)).toEqual([1, 2])
  })

  it('sorts archived methods after live ones', () => {
    const items = [
      item({ id: 1, archived: true }),
      item({ id: 2, archived: false }),
      item({ id: 3, archived: true }),
      item({ id: 4, archived: false }),
    ]

    expect(methodOptions(makeStore(items)).map((i) => i.id)).toEqual([2, 4, 1, 3])
  })

  it('preserves relative order within each group', () => {
    const items = [
      item({ id: 1, archived: false }),
      item({ id: 2, archived: false }),
      item({ id: 3, archived: true }),
      item({ id: 4, archived: true }),
    ]

    expect(methodOptions(makeStore(items)).map((i) => i.id)).toEqual([1, 2, 3, 4])
  })

  it('returns an empty list for an empty store', () => {
    expect(methodOptions(makeStore([]))).toEqual([])
  })
})
