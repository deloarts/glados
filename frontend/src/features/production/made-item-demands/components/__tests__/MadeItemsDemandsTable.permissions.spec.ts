/**
 * The "Set status" entries of the made item demand context menu offer only
 * fulfilled and canceled. The backend's demand status rule reserves both for
 * holders of write:demand_items and manage:demand_items, so the entries stay
 * disabled for everyone else and the menu never offers a change the backend
 * refuses. Editing keeps its own write:demand_items gate.
 */
import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { i18n } from '@/core/i18n'
import { Permission } from '@/core/auth/permissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { mountWithApp } from '@/test-utils/mountWithApp'
import { userWithPermissions } from '@/test-utils/factories'

function demand(id: number) {
  return {
    id,
    status: 'open',
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
    creator: null,
    made_item_id: id,
    item_part_number: `PN-${id}`,
    item_article_name: 'Bracket',
    bucket_id: null,
    item: null,
    project_id: 1,
    project_number: 'P-001',
    project_customer: 'Acme',
    project_description: 'Test project',
    project_status: 'active',
  }
}

const demandsResponse = { data: { items: [demand(1), demand(2)], total: 2, limit: 25, skip: 0 } }

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<(url: string) => Promise<unknown>>().mockImplementation((url: string) => {
      if (url === '/made-items-demands') return Promise.resolve(demandsResponse)
      if (url.startsWith('/made-items-allocations/demand/')) return Promise.resolve({ data: [] })
      if (url === '/made-items-allocations/summary') return Promise.resolve({ data: {} })
      return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    put: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import MadeItemsDemandsTable from '../MadeItemsDemandsTable.vue'
import { useMadeItemsProcurementStore } from '../../stores/madeItemsProcurementStore'
import { useMadeItemsDemandsStore } from '@/features/made-items'

type MenuEntry = { label?: string; disabled?: boolean }

async function contextMenuFor(permissions: string[], severalRows: boolean): Promise<MenuEntry[]> {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  const wrapper = mountWithApp(MadeItemsDemandsTable, {
    pinia,
    global: { stubs: { RouterLink: true } },
  })
  await flushPromises()
  await flushPromises()

  if (severalRows) {
    const [first, second] = useMadeItemsDemandsStore().items
    useMadeItemsProcurementStore().selectedDemands = [first!, second!]
  }
  await wrapper.find('tbody tr').trigger('contextmenu')
  await flushPromises()

  return wrapper.findComponent({ name: 'ContextMenu' }).props('model') as MenuEntry[]
}

function entry(items: MenuEntry[], key: string): MenuEntry | undefined {
  return items.find((item) => item.label === i18n.global.t(key))
}

const SET_STATUS = 'madeItems.demands.contextMenu.setStatus'

describe('MadeItemsDemandsTable context menu for several selected rows', () => {
  it('is the multi-target menu the cases below rely on', async () => {
    const items = await contextMenuFor(
      [Permission.WRITE_DEMAND_ITEMS, Permission.MANAGE_DEMAND_ITEMS],
      true,
    )
    expect(items[0]?.label).toBe(
      i18n.global.t('madeItems.demands.contextMenu.selectedCount', { count: 2 }),
    )
  })
})

describe.each([
  ['one row', false],
  ['several selected rows', true],
])('MadeItemsDemandsTable "Set status" menu for %s', (_, severalRows) => {
  it('is disabled for a user without demand permissions', async () => {
    const items = await contextMenuFor([], severalRows)
    expect(entry(items, SET_STATUS)?.disabled).toBe(true)
  })

  it('is disabled for a demand writer without manage:demand_items', async () => {
    const items = await contextMenuFor([Permission.WRITE_DEMAND_ITEMS], severalRows)
    expect(entry(items, SET_STATUS)?.disabled).toBe(true)
  })

  it('is enabled for a demand writer with manage:demand_items', async () => {
    const items = await contextMenuFor(
      [Permission.WRITE_DEMAND_ITEMS, Permission.MANAGE_DEMAND_ITEMS],
      severalRows,
    )
    expect(entry(items, SET_STATUS)?.disabled).toBe(false)
  })
})

describe('MadeItemsDemandsTable edit entry', () => {
  it('stays enabled for a demand writer without manage:demand_items', async () => {
    const items = await contextMenuFor([Permission.WRITE_DEMAND_ITEMS], false)
    expect(entry(items, 'madeItems.demands.contextMenu.edit')?.disabled).toBe(false)
  })
})
