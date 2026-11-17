import { describe, it, expect } from 'vitest'

import { groupRowsByLabel } from '../tableRowGrouping'

// groupRowsByLabel is the shared row grouping behind the order item, lot and
// management tables.

interface Row {
  id: number
  status: string
}

describe('groupRowsByLabel', () => {
  it('attaches the group field and sorts rows by its label', () => {
    const items: Row[] = [
      { id: 1, status: 'b' },
      { id: 2, status: 'a' },
      { id: 3, status: 'c' },
    ]

    const result = groupRowsByLabel(items, '_statusGroup', (item) => item.status)

    expect(result.map((r) => r.id)).toEqual([2, 1, 3])
    expect(result.map((r) => r._statusGroup)).toEqual(['a', 'b', 'c'])
  })

  it('keeps rows of the same group label contiguous and stable-ish by original order', () => {
    const items: Row[] = [
      { id: 1, status: 'open' },
      { id: 2, status: 'closed' },
      { id: 3, status: 'open' },
    ]

    const result = groupRowsByLabel(items, '_statusGroup', (item) => item.status)

    expect(result.map((r) => r.id)).toEqual([2, 1, 3])
  })

  it('does not mutate the input array', () => {
    const items: Row[] = [
      { id: 1, status: 'b' },
      { id: 2, status: 'a' },
    ]
    const original = [...items]

    groupRowsByLabel(items, '_statusGroup', (item) => item.status)

    expect(items).toEqual(original)
  })

  it('returns an empty array for an empty input', () => {
    expect(groupRowsByLabel<Row, '_statusGroup'>([], '_statusGroup', (item) => item.status)).toEqual([])
  })

  it('uses locale-aware comparison for the sort', () => {
    const items: Row[] = [
      { id: 1, status: 'Zebra' },
      { id: 2, status: 'apple' },
    ]

    const result = groupRowsByLabel(items, '_statusGroup', (item) => item.status)

    // localeCompare orders case-insensitively-ish ('apple' before 'Zebra'),
    // unlike a plain code-point string sort which would put 'Zebra' first.
    expect(result.map((r) => r.id)).toEqual([2, 1])
  })
})
