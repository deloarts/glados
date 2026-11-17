import { describe, expect, it } from 'vitest'

import { dropTarget, placeInList } from '../useRowDragReorder'

const rows = (...ids: number[]) => ids.map((id) => ({ id }))

describe('dropTarget', () => {
  it('names the row above the drop, else the row below, else nothing', () => {
    expect(dropTarget(rows(2, 1, 3), 1)).toEqual({ after_id: 2 })
    expect(dropTarget(rows(3, 1, 2), 0)).toEqual({ before_id: 1 })
    expect(dropTarget(rows(1), 0)).toEqual({})
  })
})

describe('placeInList', () => {
  it('puts the entry after or before its neighbour, or first without one', () => {
    expect(placeInList(rows(1, 2, 3, 4), 1, { after_id: 3 }).map((r) => r.id)).toEqual([2, 3, 1, 4])
    expect(placeInList(rows(1, 2, 3, 4), 4, { before_id: 2 }).map((r) => r.id)).toEqual([1, 4, 2, 3])
    expect(placeInList(rows(1, 2, 3), 3, {}).map((r) => r.id)).toEqual([3, 1, 2])
  })

  it('leaves the list as it is for an unknown entry', () => {
    const list = rows(1, 2)
    expect(placeInList(list, 9, { after_id: 1 })).toBe(list)
  })
})
