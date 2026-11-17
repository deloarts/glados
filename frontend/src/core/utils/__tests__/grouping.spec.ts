import { describe, it, expect } from 'vitest'

import { boundariesFromGroups, computeGroups, normalizeGroupIndexes } from '../grouping'

describe('computeGroups', () => {
  it('splits at every boundary', () => {
    expect(computeGroups([1, 2, 3, 4], new Set([3]))).toEqual([
      [1, 2],
      [3, 4],
    ])
  })

  it('with no boundaries, everything is one group', () => {
    expect(computeGroups([1, 2, 3], new Set())).toEqual([[1, 2, 3]])
  })

  it('every id a boundary splits into singleton groups', () => {
    expect(computeGroups([1, 2, 3], new Set([2, 3]))).toEqual([[1], [2], [3]])
  })

  it('an empty id list produces no groups', () => {
    expect(computeGroups([], new Set())).toEqual([])
  })
})

describe('boundariesFromGroups', () => {
  it('is the first id of every group but the first', () => {
    expect(boundariesFromGroups([[1, 2], [3, 4], [5]])).toEqual(new Set([3, 5]))
  })

  it('a single group has no boundaries', () => {
    expect(boundariesFromGroups([[1, 2, 3]])).toEqual(new Set())
  })

  it('round-trips through computeGroups', () => {
    const groups = [[1], [2, 3], [4]]
    const boundaries = boundariesFromGroups(groups)
    expect(computeGroups([1, 2, 3, 4], boundaries)).toEqual(groups)
  })
})

describe('normalizeGroupIndexes', () => {
  it('preserves an adjacent same-group run', () => {
    const result = normalizeGroupIndexes([
      { id: 'a', group_index: 0 },
      { id: 'b', group_index: 0 },
      { id: 'c', group_index: 1 },
    ])
    expect(result.map((r) => r.group_index)).toEqual([0, 0, 1])
  })

  it('splits a run torn apart by a reorder', () => {
    // a,b were one group; c moved in between them.
    const result = normalizeGroupIndexes([
      { id: 'a', group_index: 0 },
      { id: 'c', group_index: 1 },
      { id: 'b', group_index: 0 },
    ])
    expect(result.map((r) => r.group_index)).toEqual([0, 1, 2])
  })

  it('merges a previously non-adjacent pair that a reorder makes adjacent', () => {
    // Original order a(0), b(0), c(1). Reordered to c, a, b, so c no longer
    // separates anything, and a and b re-merge into one group.
    const result = normalizeGroupIndexes([
      { id: 'c', group_index: 1 },
      { id: 'a', group_index: 0 },
      { id: 'b', group_index: 0 },
    ])
    expect(result.map((r) => r.group_index)).toEqual([0, 1, 1])
  })

  it('a null/undefined group_index always starts its own new group', () => {
    const result = normalizeGroupIndexes([
      { id: 'a', group_index: null },
      { id: 'b', group_index: null },
      { id: 'c', group_index: 0 },
    ])
    expect(result.map((r) => r.group_index)).toEqual([0, 1, 2])
  })

  it('normalizes non-contiguous raw indexes gracefully', () => {
    const result = normalizeGroupIndexes([
      { id: 'a', group_index: 5 },
      { id: 'b', group_index: 5 },
      { id: 'c', group_index: 2 },
    ])
    expect(result.map((r) => r.group_index)).toEqual([0, 0, 1])
  })

  it('an empty list produces an empty result', () => {
    expect(normalizeGroupIndexes([])).toEqual([])
  })
})
