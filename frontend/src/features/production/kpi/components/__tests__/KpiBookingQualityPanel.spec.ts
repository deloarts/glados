import { describe, it, expect } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'

import KpiBookingQualityPanel from '../KpiBookingQualityPanel.vue'
import type { ProductionKpiBookingQualityResult } from '../../types/productionKpiResponse'

function makeResult(
  overrides: Partial<ProductionKpiBookingQualityResult> = {},
): ProductionKpiBookingQualityResult {
  return {
    booking_quality_since: '2026-11-27T08:00:00Z',
    orders_with_bookings: 12,
    outside_working_time: [
      {
        order_id: 1,
        production_order_number: 'PO-0001',
        lot_id: 1,
        lot_number: 'L-1',
        machine_id: 1,
        booked_minutes: 1200,
        outside_minutes: 960,
      },
    ],
    final_completions: 4,
    missing_assessments: [
      {
        order_id: 2,
        production_order_number: 'PO-0002',
        lot_id: 1,
        lot_number: 'L-1',
        machine_id: 1,
        completed_at: '2026-12-02T11:00:00Z',
      },
    ],
    manual_pauses: 3,
    uncaused_pauses: [],
    ...overrides,
  }
}

describe('KpiBookingQualityPanel', () => {
  it('sums up each finding against its total', async () => {
    const wrapper = mountWithApp(KpiBookingQualityPanel, { props: { result: makeResult() } })
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('1 of 12 orders ran through hours without working time')
    expect(text).toContain('1 of 4 final completions have no assessment')
    expect(text).toContain('0 of 3 manual pauses have no cause')
  })

  it('lists every finding with its order and detail', async () => {
    const wrapper = mountWithApp(KpiBookingQualityPanel, { props: { result: makeResult() } })
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('Outside Working Time')
    expect(text).toContain('PO-0001')
    expect(text).toContain('960 of 1200 booked minutes outside working time')
    expect(text).toContain('No Assessment')
    expect(text).toContain('PO-0002')
  })

  it('shows the empty state without findings', async () => {
    const wrapper = mountWithApp(KpiBookingQualityPanel, {
      props: { result: makeResult({ outside_working_time: [], missing_assessments: [] }) },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('No findings in this period.')
  })
})
