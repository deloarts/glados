/**
 * The "Set status" entries of the source item demand context menu offer only
 * fulfilled and canceled. The backend's demand status rule reserves both for
 * holders of write:demand_items and manage:demand_items, so the entries stay
 * disabled for everyone else, a lot writer included, and the menu never
 * offers a change the backend refuses. Cancel keeps its own write:lots gate.
 */
import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'

import { i18n } from '@/core/i18n'
import { Permission } from '@/core/auth/permissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { mountWithApp } from '@/test-utils/mountWithApp'
import { userWithPermissions } from '@/test-utils/factories'

function demand(id: number) {
  return {
    id,
    public_id: `aaaaaaaa-aaaa-aaaa-aaaa-00000000000${id}`,
    status: 'open',
    actions: ['cancel', 'fulfil', 'allocate', 'edit_quantity'],
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
    bucket_id: null,
    bought_item_id: null,
    bought_item: null,
    source_item_id: id,
    source_item: null,
    lot_id: id,
    lot_number: `LOT-000${id}`,
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
      if (url === '/source-item-demands') return Promise.resolve(demandsResponse)
      return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    put: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import SourceItemDemandsTable from '../SourceItemDemandsTable.vue'
import { useSourceItemDemandsSelectionStore } from '../../stores/sourceItemDemandsSelectionStore'
import { useSourceItemDemandsStore } from '@/features/source-items'

type MenuEntry = { label?: string; disabled?: boolean; title?: string; items?: MenuEntry[] }

async function contextMenuFor(permissions: string[], severalRows: boolean): Promise<MenuEntry[]> {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  const wrapper = mountWithApp(SourceItemDemandsTable, {
    pinia,
    global: { plugins: [ConfirmationService], stubs: { RouterLink: true } },
  })
  await flushPromises()
  await flushPromises()

  if (severalRows) {
    const [first, second] = useSourceItemDemandsStore().items
    useSourceItemDemandsSelectionStore().selectedDemands = [first!, second!]
  }
  await wrapper.find('tbody tr').trigger('contextmenu')
  await flushPromises()

  return wrapper.findComponent({ name: 'ContextMenu' }).props('model') as MenuEntry[]
}

function entry(items: MenuEntry[], key: string): MenuEntry | undefined {
  return items.find((item) => item.label === i18n.global.t(key))
}

const SET_STATUS = 'sourceItems.demands.contextMenu.setStatus'

describe('SourceItemDemandsTable context menu for several selected rows', () => {
  it('is the multi-target menu the cases below rely on', async () => {
    const items = await contextMenuFor(
      [Permission.WRITE_DEMAND_ITEMS, Permission.MANAGE_DEMAND_ITEMS],
      true,
    )
    expect(items[0]?.label).toBe(
      i18n.global.t('sourceItems.demands.contextMenu.selectedCount', { count: 2 }),
    )
  })
})

describe.each([
  ['one row', false],
  ['several selected rows', true],
])('SourceItemDemandsTable "Set status" menu for %s', (_, severalRows) => {
  it('is disabled for a lot writer without demand permissions', async () => {
    const items = await contextMenuFor([Permission.WRITE_LOTS], severalRows)
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

describe('SourceItemDemandsTable cancel entry', () => {
  it('stays gated on write:lots, since canceling unlinks the demand from its lot', async () => {
    const items = await contextMenuFor([Permission.WRITE_LOTS], false)
    expect(entry(items, 'sourceItems.demands.contextMenu.cancel')?.disabled).toBe(false)
  })

  it('is disabled once the lot started, which the server no longer offers the cancel for', async () => {
    const first = demandsResponse.data.items[0]!
    const offered = first.actions
    first.actions = ['fulfil', 'allocate', 'edit_quantity']
    try {
      const items = await contextMenuFor([Permission.WRITE_LOTS], false)
      expect(entry(items, 'sourceItems.demands.contextMenu.cancel')?.disabled).toBe(true)
    } finally {
      first.actions = offered
    }
  })

  it('says why on a started lot, in both Cancel and Set Status, as the dialog button does', async () => {
    const first = demandsResponse.data.items[0]!
    const offered = first.actions
    first.actions = ['fulfil', 'allocate', 'edit_quantity']
    try {
      const items = await contextMenuFor(
        [Permission.WRITE_LOTS, Permission.WRITE_DEMAND_ITEMS, Permission.MANAGE_DEMAND_ITEMS],
        false,
      )
      const reason = i18n.global.t('sourceItems.demands.detail.cancelBlocked.lotStarted', {
        lot: 'LOT-0001',
      })
      expect(entry(items, 'sourceItems.demands.contextMenu.cancel')).toMatchObject({
        disabled: true,
        title: reason,
      })
      const canceled = entry(items, SET_STATUS)?.items?.find(
        (item) => item.label === i18n.global.t('sourceItems.demands.status.canceled'),
      )
      expect(canceled).toMatchObject({ disabled: true, title: reason })
    } finally {
      first.actions = offered
    }
  })

  it('names the missing permission on a disabled Cancel', async () => {
    const items = await contextMenuFor([Permission.WRITE_DEMAND_ITEMS], false)
    expect(entry(items, 'sourceItems.demands.contextMenu.cancel')).toMatchObject({
      disabled: true,
      title: i18n.global.t('sourceItems.demands.detail.cancelBlocked.permission'),
    })
  })
})
