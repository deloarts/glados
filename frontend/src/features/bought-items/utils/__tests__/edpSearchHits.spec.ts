import { describe, it, expect } from 'vitest'

import { exactMatchesFirst, isExactOrderCodeMatch } from '../edpSearchHits'

import type { EdpSearchHit } from '../../types/boughtItemsEdpTypes'

function hit(partId: number, orderCode1: string | null): EdpSearchHit {
  return {
    part: { part_id: partId, part_number: `SIE.${partId}` },
    draft: { edp_part_id: partId, order_code_1: orderCode1 },
    existing_item: null,
  } as EdpSearchHit
}

describe('isExactOrderCodeMatch', () => {
  it('matches the order code 1 character for character', () => {
    expect(isExactOrderCodeMatch(hit(1, '3RT2015-1BB41'), '3RT2015-1BB41')).toBe(true)
  })

  it('ignores only the spaces around the searched text', () => {
    expect(isExactOrderCodeMatch(hit(1, '3RT2015-1BB41'), ' 3RT2015-1BB41 ')).toBe(true)
  })

  it('does not match another case or spelling of the code', () => {
    expect(isExactOrderCodeMatch(hit(1, '3RT2015-1BB41'), '3rt2015-1bb41')).toBe(false)
    expect(isExactOrderCodeMatch(hit(1, '3RT2015-1BB41'), '3RT20151BB41')).toBe(false)
    expect(isExactOrderCodeMatch(hit(1, '3RT2015-1BB41'), '3RT2015')).toBe(false)
  })

  it('does not match a hit without an order code 1', () => {
    expect(isExactOrderCodeMatch(hit(1, null), '')).toBe(false)
  })
})

describe('exactMatchesFirst', () => {
  it('moves the exact matches to the top and keeps the portal order otherwise', () => {
    const hits = [hit(1, '3RT2015-1BB42'), hit(2, '3RT2015-1BB41'), hit(3, '3RT2015-1BB4')]

    expect(exactMatchesFirst(hits, '3RT2015-1BB41').map((h) => h.part.part_id)).toEqual([2, 1, 3])
  })

  it('leaves the order alone without an exact match', () => {
    const hits = [hit(1, 'A'), hit(2, 'B')]

    expect(exactMatchesFirst(hits, 'C').map((h) => h.part.part_id)).toEqual([1, 2])
  })
})
