import { describe, expect, it } from 'vitest'

import { aggregateBomRows, compareBy, type BomRowBase } from '../bomAggregation'

interface Demand {
  item: string
  qty: number
  status: string
  name?: string
}

interface Row extends BomRowBase {
  name: string
}

function aggregate(demands: Demand[]): Row[] {
  return aggregateBomRows<Demand, Row>(demands, {
    key: (d) => d.item,
    seed: (d, key) => ({ key, name: d.name ?? d.item }),
    quantity: (d) => d.qty,
    status: (d) => d.status,
    compare: compareBy(
      (r) => r.name,
      (r) => r.key,
    ),
  })
}

describe('aggregateBomRows', () => {
  it('collapses several demands for the same item into one row', () => {
    const rows = aggregate([
      { item: 'a', qty: 2, status: 'open' },
      { item: 'a', qty: 3, status: 'open' },
    ])

    expect(rows).toHaveLength(1)
    expect(rows[0]?.qtyDemanded).toBe(5)
  })

  it('counts fulfilled quantity separately from demanded', () => {
    const rows = aggregate([
      { item: 'a', qty: 2, status: 'open' },
      { item: 'a', qty: 3, status: 'fulfilled' },
    ])

    expect(rows[0]?.qtyDemanded).toBe(5)
    expect(rows[0]?.qtyFulfilled).toBe(3)
  })

  it('tallies how many demands sit in each status', () => {
    const rows = aggregate([
      { item: 'a', qty: 1, status: 'open' },
      { item: 'a', qty: 1, status: 'open' },
      { item: 'a', qty: 1, status: 'canceled' },
    ])

    expect(rows[0]?.statusCounts).toEqual({ open: 2, canceled: 1 })
  })

  it('keeps distinct keys apart', () => {
    // The source bill prefixes its keys by side because bought-item and
    // source-item ids overlap; this is that collision, spelled out.
    const rows = aggregate([
      { item: 'b:1', qty: 1, status: 'open' },
      { item: 's:1', qty: 4, status: 'open' },
    ])

    expect(rows).toHaveLength(2)
    expect(rows.map((r) => r.qtyDemanded)).toEqual([1, 4])
  })

  it('seeds a row from the first demand seen for that key', () => {
    const rows = aggregate([
      { item: 'a', qty: 1, status: 'open', name: 'first' },
      { item: 'a', qty: 1, status: 'open', name: 'second' },
    ])

    expect(rows[0]?.name).toBe('first')
  })

  it('returns nothing for no demands', () => {
    expect(aggregate([])).toEqual([])
  })

  it('splits an item by project when asked to, keeping its rows together in project order', () => {
    const demands: (Demand & { project: number; projectNumber: string })[] = [
      { item: 'a', qty: 1, status: 'open', project: 2, projectNumber: 'P-2' },
      { item: 'b', qty: 4, status: 'open', project: 1, projectNumber: 'P-1' },
      { item: 'a', qty: 2, status: 'open', project: 1, projectNumber: 'P-1' },
      { item: 'a', qty: 3, status: 'open', project: 2, projectNumber: 'P-2' },
    ]
    const rows = aggregateBomRows<(typeof demands)[number], Row>(demands, {
      key: (d) => d.item,
      seed: (d, key) => ({ key, name: d.item }),
      quantity: (d) => d.qty,
      status: (d) => d.status,
      compare: (a, b) => a.name.localeCompare(b.name),
      project: (d) => ({ id: d.project, number: d.projectNumber }),
    })

    expect(rows.map((r) => [r.name, r.projectNumber, r.qtyDemanded])).toEqual([
      ['a', 'P-1', 2],
      ['a', 'P-2', 4],
      ['b', 'P-1', 4],
    ])
  })

  it('leaves the project out without the split', () => {
    expect(aggregate([{ item: 'a', qty: 1, status: 'open' }])[0]?.projectNumber).toBeUndefined()
  })
})

describe('compareBy', () => {
  it('falls back to the secondary field when the primary ties', () => {
    const rows = [
      { a: 'x', b: '2' },
      { a: 'x', b: '1' },
      { a: 'w', b: '9' },
    ]

    rows.sort(
      compareBy(
        (r) => r.a,
        (r) => r.b,
      ),
    )

    expect(rows).toEqual([
      { a: 'w', b: '9' },
      { a: 'x', b: '1' },
      { a: 'x', b: '2' },
    ])
  })
})
