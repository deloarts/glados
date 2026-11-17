import { describe, it, expect } from 'vitest'

import { bySequence, sortedBySequence } from '../sequence'

describe('sortedBySequence', () => {
  it('returns a sorted copy and leaves the input alone', () => {
    const input = [
      { id: 'b', sequence: 2 },
      { id: 'c', sequence: 3 },
      { id: 'a', sequence: 1 },
    ]
    expect(sortedBySequence(input).map((x) => x.id)).toEqual(['a', 'b', 'c'])
    expect(input.map((x) => x.id)).toEqual(['b', 'c', 'a'])
  })

  it('gives an empty list for a missing one', () => {
    expect(sortedBySequence(undefined)).toEqual([])
    expect(sortedBySequence(null)).toEqual([])
  })
})

describe('bySequence', () => {
  it('orders ascending by sequence', () => {
    expect([{ sequence: 3 }, { sequence: 1 }].sort(bySequence)).toEqual([
      { sequence: 1 },
      { sequence: 3 },
    ])
  })
})
