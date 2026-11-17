import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: {
        items: [
          {
            id: 1,
            public_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
            // A fulfilled demand offers no further action.
            status: 'fulfilled',
            actions: [],
            created: '2026-01-01',
            changed: null,
            quantity: 5,
            unit: 'PCS',
            items_per_unit: 1,
            high_priority: false,
            notify_on_delivery: false,
            note: null,
            desired_delivery_date: null,
            creator_id: 1,
            creator: {
              id: 1,
              username: 'creator',
              full_name: 'Creator',
              email: 'creator@example.com',
              has_avatar: false,
            },
            item_id: 1,
            item_order_code_1: 'OC1',
            item_article_name: 'Bracket',
            item: {
              id: 1,
              order_code_1: 'OC1',
              order_code_2: 'OC2',
              status: 'active',
              deleted: false,
              created: '2026-01-01',
              changed: null,
              article_name: 'Bracket',
              article_groups: [],
              data_source: 'MANUAL',
              mass: null,
              note: null,
              weblink: null,
              successor_item_id: null,
              creator_id: 1,
              creator: null,
              manufacturer_id: null,
              manufacturer_name: '',
            },
            project_id: 1,
            project_number: 'P-001',
            project_customer: 'Acme',
            project_description: 'Test project',
            project_status: 'active',
            bucket_id: null,
          },
        ],
        total: 1,
        limit: 25,
        skip: 0,
      },
    }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import BoughtItemsDemandsTable from '../BoughtItemsDemandsTable.vue'

type MenuEntry = { label?: string; disabled?: boolean; items?: MenuEntry[] }

describe('BoughtItemsDemandsTable status menu on a fulfilled demand', () => {
  it('offers neither cancel nor fulfil, as the demand offers neither', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
    })
    await router.push('/')
    await router.isReady()

    const wrapper = mountWithApp(BoughtItemsDemandsTable, {
      global: {
        plugins: [router, ConfirmationService],
      },
    })
    await flushPromises()
    await flushPromises()
    await flushPromises()

    await wrapper.find('tbody tr').trigger('contextmenu')
    await flushPromises()

    const items = wrapper.findComponent({ name: 'ContextMenu' }).props('model') as MenuEntry[]
    const setStatus = items.find(
      (item) => item.label === i18n.global.t('boughtItems.demands.contextMenu.setStatus'),
    )
    const entries = setStatus?.items ?? []
    const byLabel = (status: string) =>
      entries.find((item) => item.label === i18n.global.t(`boughtItems.demands.status.${status}`))

    expect(byLabel('fulfilled')?.disabled).toBe(true)
    expect(byLabel('canceled')?.disabled).toBe(true)
  })
})
