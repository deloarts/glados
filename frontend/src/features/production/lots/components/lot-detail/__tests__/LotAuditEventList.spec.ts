import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'

import { i18n } from '@/core/i18n'

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: {
        items: [{ id: 5, type_name: 'Rod', material: 'Steel', dimension: '10mm' }],
        total: 1,
      },
    }),
  },
}))

import LotAuditEventList from '../LotAuditEventList.vue'
import type { LotEventResponse } from '../../../../types/productionLotsResponse'

// The component reads `production.lots.detail.audit.materialSourceItem`,
// which has no `.events` segment; a wrong path would render as the raw
// dotted key instead of the translated label.
describe('LotAuditEventList', () => {
  it('resolves the material-source-switch label instead of rendering a raw i18n key', async () => {
    const events: LotEventResponse[] = [
      {
        id: 1,
        public_id: '55555555-5555-5555-5555-555555555555',
        lot_id: 1,
        occurred_at: '2026-01-01T00:00:00Z',
        actor_id: 1,
        actor_username: 'someone',
        actor_full_name: 'Some One',
        event_type: 'lot_material_source_switched',
        entity: 'lot',
        entity_id: 1,
        summary: 'Switched material source',
        payload: { source_item_id: 5 },
      },
    ]

    const wrapper = mount(LotAuditEventList, {
      props: { events, loading: false, requiredDeliveryDate: null },
      global: {
        plugins: [createPinia(), i18n],
      },
    })

    await flushPromises()
    await flushPromises()

    const resolved = wrapper.find('.audit-item-resolved')
    expect(resolved.exists()).toBe(true)
    expect(resolved.text()).not.toMatch(/^[a-z]+(\.[a-zA-Z]+)+:/)
    expect(resolved.text()).toContain('Item:')
  })
})
