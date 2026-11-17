import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'


vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: { items: [], total: 0, limit: 1000, skip: 0 },
    }),
  },
}))

import LotRecordAudit from '../lot-detail/LotRecordAudit.vue'
import type { LotEventResponse } from '../../../types/productionLotsResponse'
import type { LotChangelogEntry } from '../../types/lotChangelogResponse'
import { mountWithApp } from '@/test-utils/mountWithApp'

// OpenVue's TabList observes its own width to decide whether to show
// scroll buttons; jsdom has no ResizeObserver.

const event: LotEventResponse = {
  id: 1,
  public_id: '55555555-5555-5555-5555-555555555555',
  lot_id: 1,
  occurred_at: '2026-07-01T10:00:00',
  actor_id: 1,
  actor_username: 'phil',
  actor_full_name: 'Sam Doe',
  event_type: 'lot_created',
  entity: 'lot',
  entity_id: null,
  summary: 'Lot LOT-1 created.',
  payload: null,
}

function mountAudit(changelog: LotChangelogEntry[], events: LotEventResponse[] = [event]) {
  return mountWithApp(LotRecordAudit, {
    attachTo: document.body,
    props: { events, changelog, loading: false, requiredDeliveryDate: null },
  })
}

describe('LotRecordAudit', () => {
  it('shows the structured event trail on the default tab', async () => {
    const wrapper = mountAudit([])
    await flushPromises()

    expect(wrapper.text()).toContain('Lot LOT-1 created.')

    wrapper.unmount()
  })

  it('shows the lot changelog on its own tab, including multi-line diff entries', async () => {
    const wrapper = mountAudit([
      {
        timestamp: '2026-08-06 11:00:00',
        username: 'Sam',
        message: "Lot updated:\n  • note: None → 'urgent rework'",
      },
    ])
    await flushPromises()

    const changelogTab = wrapper.findAll('[role="tab"]').find((t) => t.text() === 'Changelog')
    expect(changelogTab).toBeTruthy()
    await changelogTab!.trigger('click')
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('Sam')
    expect(text).toContain('urgent rework')

    wrapper.unmount()
  })

  it('shows an empty state on the changelog tab when nothing has changed', async () => {
    const wrapper = mountAudit([])
    await flushPromises()

    const changelogTab = wrapper.findAll('[role="tab"]').find((t) => t.text() === 'Changelog')
    await changelogTab!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('No changes recorded yet.')

    wrapper.unmount()
  })
})
