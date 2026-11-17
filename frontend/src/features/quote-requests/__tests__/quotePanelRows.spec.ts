import { describe, it, expect } from 'vitest'

import {
  mergeQuotePanelRows,
  quotePanelLines,
  rowSharesExceedLine,
  rowShowsShares,
} from '../utils/quotePanelRows'
import type { QuotePanelRow } from '../utils/quotePanelRows'

function row(overrides: Partial<QuotePanelRow> = {}): QuotePanelRow {
  return {
    key: 'k',
    title: 'Screw',
    subtitle: '',
    projectNumber: 'P-1',
    unit: 'PCS',
    quantity: 0,
    quantityEdited: false,
    shares: [{ family: 'bought', demandId: 1, quantity: 3 }],
    identity: { bought_item_id: 5, project_id: 3 },
    ...overrides,
  }
}

describe('quotePanelRows', () => {
  it('follows the shares until the quantity was typed', () => {
    const [fresh] = mergeQuotePanelRows([], [row()])
    expect(fresh!.quantity).toBe(3)

    const [kept] = mergeQuotePanelRows([row({ quantity: 10, quantityEdited: true })], [row()])
    expect(kept!.quantity).toBe(10)
  })

  it('keeps the share a user entered for a demand', () => {
    const previous = row({ shares: [{ family: 'bought', demandId: 1, quantity: 1 }] })
    const [merged] = mergeQuotePanelRows([previous], [row()])
    expect(merged!.shares[0]!.quantity).toBe(1)
  })

  it('turns rows into request lines without empty shares', () => {
    const lines = quotePanelLines([
      row({
        quantity: 5,
        shares: [
          { family: 'bought', demandId: 1, quantity: 3 },
          { family: 'bought', demandId: 2, quantity: 0 },
        ],
      }),
    ])
    expect(lines).toEqual([
      {
        bought_item_id: 5,
        project_id: 3,
        quantity: 5,
        unit: 'PCS',
        demands: [{ family: 'bought', demand_item_id: 1, quantity: 3 }],
      },
    ])
  })

  it('finds shares beyond the line when a row shows them', () => {
    const shares = [
      { family: 'bought' as const, demandId: 1, quantity: 3 },
      { family: 'bought' as const, demandId: 2, quantity: 2 },
    ]
    expect(rowSharesExceedLine(row({ quantity: 4, shares }))).toBe(true)
    expect(rowSharesExceedLine(row({ quantity: 5, shares }))).toBe(false)
    expect(rowShowsShares(row({ shares }))).toBe(true)
  })

  it('hides the one share of a single demand and cuts it to the line', () => {
    const single = row({ quantity: 2 })
    expect(rowShowsShares(single)).toBe(false)
    expect(rowSharesExceedLine(single)).toBe(false)
    expect(quotePanelLines([single])[0]!.demands).toEqual([
      { family: 'bought', demand_item_id: 1, quantity: 2 },
    ])
  })
})
