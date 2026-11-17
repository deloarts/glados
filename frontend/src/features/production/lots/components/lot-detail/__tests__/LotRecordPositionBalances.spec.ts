import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'

import type { LotPositionBalanceResponse } from '../../../../types/productionLotsResponse'

const getLotPositionBalances = vi.hoisted(() =>
  vi.fn<(id: number) => Promise<LotPositionBalanceResponse[]>>(),
)

vi.mock('../../../api/getLotPositionBalances', () => ({ getLotPositionBalances }))

import LotRecordPositionBalances from '../LotRecordPositionBalances.vue'

function balance(overrides: Partial<LotPositionBalanceResponse>): LotPositionBalanceResponse {
  return {
    position_id: 1,
    sequence: 1,
    kind: 'internal',
    arrived: 10,
    good: 7,
    scrap: 1,
    rework: 0,
    lost: 0,
    wip: 2,
    difference: 0,
    produced: 8,
    ...overrides,
  }
}

describe('LotRecordPositionBalances', () => {
  beforeEach(() => getLotPositionBalances.mockReset())

  it('shows each position with its pieces and flags an over-booking', async () => {
    getLotPositionBalances.mockResolvedValue([
      balance({}),
      balance({ position_id: 2, sequence: 2, arrived: 7, good: 8, wip: 0, difference: -1 }),
    ])

    const wrapper = mountWithApp(LotRecordPositionBalances, { props: { lotId: 3 } })
    await flushPromises()

    expect(getLotPositionBalances).toHaveBeenCalledWith(3)
    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(2)
    expect(rows[0]!.find('.difference').exists()).toBe(false)
    expect(rows[1]!.find('.difference').text()).toContain('-1')

    wrapper.unmount()
  })
})
