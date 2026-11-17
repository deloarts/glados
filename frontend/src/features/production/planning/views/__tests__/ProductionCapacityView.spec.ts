import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { dateToParam } from '@/core/utils/dates'
import type { ScheduleBoardResponse } from '../../../types/scheduleBoardResponse'

const getMock = vi.fn<() => Promise<unknown>>()
vi.mock('@/core/api', () => ({
  default: { get: (...args: unknown[]) => getMock(...(args as [])) },
}))

// Harmless in a unit test (just registers a subscriber on the live store),
// but there's no SSE stream here, so it is stubbed out to keep this spec
// from depending on that module at all.
vi.mock('@/core/realtime/useLiveRefresh', () => ({
  useLiveRefresh: vi.fn<() => void>(),
}))

import ProductionCapacityView from '../ProductionCapacityView.vue'

// "Today" is always inside the default [start of this week, +30 days)
// window the view requests, whatever day the suite happens to run on.
const today = dateToParam(new Date())!

function makeBoard(): ScheduleBoardResponse {
  return {
    machines: [
      {
        machine_id: 1,
        machine_internal_name: 'Machine 1',
        orders: [],
        capacity: [{ date: today, booked_minutes: 90, available_minutes: 600, overbooked_minutes: 0 }],
      },
    ],
    pools: [],
    unassigned: [],
    stale_since: null,
  }
}

describe('ProductionCapacityView - hours formatting', () => {
  beforeEach(() => {
    getMock.mockReset()
    getMock.mockResolvedValue({ data: makeBoard() })
  })

  afterEach(() => {
    i18n.global.locale.value = 'enGB'
  })

  // formatHours must not go through a bare `.toFixed(1)`, which always reads
  // as English-formatted regardless of the UI language picked in Glados.
  it('renders booked/available hours with a period decimal separator for en-GB', async () => {
    const wrapper = mountWithApp(ProductionCapacityView)
    await flushPromises()

    expect(wrapper.text()).toContain('1.5h')
    expect(wrapper.text()).toContain('10.0h')

    wrapper.unmount()
  })

  it('renders booked/available hours with a comma decimal separator for de-AT', async () => {
    i18n.global.locale.value = 'deAT'
    const wrapper = mountWithApp(ProductionCapacityView)
    await flushPromises()

    expect(wrapper.text()).toContain('1,5h')
    expect(wrapper.text()).toContain('10,0h')

    wrapper.unmount()
  })

  it('says when the stored dates still await the background walk', async () => {
    getMock.mockResolvedValue({ data: { ...makeBoard(), stale_since: '2026-10-25T09:00:00Z' } })
    const wrapper = mountWithApp(ProductionCapacityView)
    await flushPromises()

    expect(wrapper.text()).toContain('are still being worked into the stored planned dates')

    wrapper.unmount()
  })

  it('says nothing while no walk is pending', async () => {
    const wrapper = mountWithApp(ProductionCapacityView)
    await flushPromises()

    expect(wrapper.text()).not.toContain('are still being worked into')

    wrapper.unmount()
  })
})
