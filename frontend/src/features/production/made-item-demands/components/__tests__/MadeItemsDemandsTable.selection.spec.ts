/**
 * Covers made-item demand buckets: the shared-selection/bucket behaviour
 * mirrored from BoughtItemsDemandsTable.spec.ts's template:
 * selectionMode="multiple" + metaKeySelection, the bulk checkbox column's
 * visibility, ctrl-click toggling (including on a link cell, via the
 * capture-phase replay), and the multi-target context menu.
 *
 * Kept as its own file beside MadeItemsDemandsTable.spec.ts so the selection
 * behaviour stays separate from the table's other specs.
 */
import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'

import { i18n } from '@/core/i18n'
import { mountWithApp } from '@/test-utils/mountWithApp'

const demandsResponse = {
  data: {
    items: [
      {
        id: 1,
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
        creator: {
          id: 1,
          username: 'creator',
          full_name: 'Creator',
          email: 'creator@example.com',
          has_avatar: false,
        },
        made_item_id: 1,
        item_part_number: 'PN-1',
        item_article_name: 'Bracket',
        bucket_id: null,
        item: {
          id: 1,
          part_number: 'PN-1',
          status: 'active',
          deleted: false,
          created: '2026-01-01',
          changed: null,
          revision: 'A',
          revision_date: null,
          revision_note: null,
          article_name: 'Bracket',
          article_groups: [],
          data_source: 'MANUAL',
          material: null,
          mass: null,
          base_size: null,
          note: null,
          weblink: null,
          successor_item_id: null,
          creator_id: 1,
          creator: null,
          bought_item_id: null,
          bought_item: null,
          source_item_id: null,
          source_item: null,
          processes: [],
        },
        project_id: 1,
        project_number: 'P-001',
        project_customer: 'Acme',
        project_description: 'Test project',
        project_status: 'active',
      },
      {
        id: 2,
        status: 'open',
        actions: ['cancel', 'fulfil', 'allocate', 'edit_quantity'],
        created: '2026-01-01',
        changed: null,
        quantity: 3,
        unit: 'PCS',
        items_per_unit: 1,
        high_priority: false,
        notify_on_delivery: false,
        note: null,
        desired_delivery_date: null,
        creator_id: 1,
        creator: null,
        made_item_id: 2,
        item_part_number: 'PN-2',
        item_article_name: 'Bolt',
        bucket_id: null,
        item: null,
        project_id: 1,
        project_number: 'P-001',
        project_customer: 'Acme',
        project_description: 'Test project',
        project_status: 'active',
      },
    ],
    total: 2,
    limit: 25,
    skip: 0,
  },
}

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
import { useMadeItemsDemandsFiltersStore } from '../../stores/madeItemsDemandsFiltersStore'
import { useMadeItemsProcurementStore } from '../../stores/madeItemsProcurementStore'
import { useMadeItemsDemandsStore } from '@/features/made-items'

function mountTable() {
  return mountWithApp(MadeItemsDemandsTable, {
    pinia: createPinia(),
    global: { stubs: { RouterLink: true } },
  })
}

describe('MadeItemsDemandsTable selection and buckets', () => {
  it('still opens the demand detail dialog on a plain row click while no panel is open', async () => {
    const wrapper = mountTable()
    await flushPromises()
    await flushPromises()

    const row = wrapper.find('tbody tr')
    await row.trigger('click')
    await flushPromises()

    expect(wrapper.findComponent({ name: 'MadeItemDemandDetailDialog' }).props('visible')).toBe(true)
  })

  it('ctrl-click toggles the row into the selection without opening the detail dialog', async () => {
    const wrapper = mountTable()
    await flushPromises()
    await flushPromises()

    const procurementStore = useMadeItemsProcurementStore()
    expect(procurementStore.selectedDemands).toHaveLength(0)

    const row = wrapper.find('tbody tr')
    await row.trigger('click', { ctrlKey: true })
    await flushPromises()

    expect(procurementStore.selectedDemands).toHaveLength(1)
    expect(wrapper.findComponent({ name: 'MadeItemDemandDetailDialog' }).props('visible')).toBe(false)
  })

  // Most cells are links, and OpenVue ignores row clicks whose target is
  // clickable, so without the capture-phase replay in the table, a
  // modified click on a link would open the link and not pick the row.
  it('ctrl-click on a link cell picks the row instead of opening the link', async () => {
    const wrapper = mountTable()
    await flushPromises()
    await flushPromises()

    const procurementStore = useMadeItemsProcurementStore()
    const link = wrapper.find('tbody tr .item-link')
    expect(link.exists()).toBe(true)
    await link.trigger('click', { ctrlKey: true })
    await flushPromises()

    expect(procurementStore.selectedDemands).toHaveLength(1)
    expect(wrapper.findComponent({ name: 'MadeItemDetailDialog' }).props('visible')).toBe(false)
    expect(wrapper.findComponent({ name: 'MadeItemDemandDetailDialog' }).props('visible')).toBe(false)
  })

  it('shows the bulk-select checkbox column only while something is selected or a panel is open', async () => {
    const wrapper = mountTable()
    await flushPromises()
    await flushPromises()

    expect(wrapper.find('input[type="checkbox"]').exists()).toBe(false)

    const procurementStore = useMadeItemsProcurementStore()
    const demand = useMadeItemsDemandsStore().items[0]
    expect(demand).toBeDefined()
    procurementStore.selectedDemands = [demand!]
    await flushPromises()

    expect(wrapper.find('input[type="checkbox"]').exists()).toBe(true)

    procurementStore.clearSelection()
    await flushPromises()

    expect(wrapper.find('input[type="checkbox"]').exists()).toBe(false)

    const filtersStore = useMadeItemsDemandsFiltersStore()
    filtersStore.showManageStockPanel = true
    await flushPromises()

    expect(wrapper.find('input[type="checkbox"]').exists()).toBe(true)
  })

  it('a plain click on a row keeps the panel selection and does not open the detail dialog while a panel is open', async () => {
    const wrapper = mountTable()
    await flushPromises()
    await flushPromises()

    const filtersStore = useMadeItemsDemandsFiltersStore()
    filtersStore.showManageStockPanel = true
    await flushPromises()

    const procurementStore = useMadeItemsProcurementStore()
    // Scoped to tbody: the selection column also renders a header
    // "select-all" checkbox, which (with 2 fixture rows) would otherwise
    // select both rows instead of just the one this test means to check.
    const checkbox = wrapper.find('tbody input[type="checkbox"]')
    expect(checkbox.exists()).toBe(true)
    await checkbox.setValue(true)
    await flushPromises()

    expect(procurementStore.selectedDemands).toHaveLength(1)

    const row = wrapper.find('tbody tr')
    await row.trigger('click')
    await flushPromises()

    expect(procurementStore.selectedDemands).toHaveLength(1)
    expect(wrapper.findComponent({ name: 'MadeItemDemandDetailDialog' }).props('visible')).toBe(false)
  })

  it('shows a multi-target context menu when the right-clicked row is part of the current selection', async () => {
    const wrapper = mountTable()
    await flushPromises()
    await flushPromises()

    const demand = useMadeItemsDemandsStore().items[0]
    expect(demand).toBeDefined()

    const procurementStore = useMadeItemsProcurementStore()
    procurementStore.selectedDemands = [demand!, { ...demand!, id: 2 }]

    const row = wrapper.find('tbody tr')
    await row.trigger('contextmenu')
    await flushPromises()

    const contextMenu = wrapper.findComponent({ name: 'ContextMenu' })
    const items = contextMenu.props('model') as Array<{ label?: string }>
    const labels = items.map((item) => item.label)

    expect(labels).toContain(i18n.global.t('madeItems.demands.contextMenu.setStatus'))
    expect(labels).toContain(i18n.global.t('madeItems.demands.contextMenu.addToLots'))
    expect(labels).toContain(i18n.global.t('madeItems.demands.contextMenu.fulfillFromStock'))
    expect(labels).toContain(i18n.global.t('madeItems.demands.contextMenu.addToBucket'))
  })

  // Bulk cancel is irreversible and skips the single-row impact preview, so
  // the multi-target "canceled" entry must go through ConfirmActionDialog
  // first and only fire the N updates once confirmed.
  it('asks for confirmation before a multi-target cancel and only then updates every target', async () => {
    const wrapper = mountTable()
    await flushPromises()
    await flushPromises()

    const demandsStore = useMadeItemsDemandsStore()
    const demand = demandsStore.items[0]
    expect(demand).toBeDefined()
    const updateSpy = vi.spyOn(demandsStore, 'updateStatus').mockResolvedValue(demand!)

    useMadeItemsProcurementStore().selectedDemands = [demand!, { ...demand!, id: 2 }]

    await wrapper.find('tbody tr').trigger('contextmenu')
    await flushPromises()

    type Entry = { label?: string; items?: Entry[]; command?: () => void }
    const items = wrapper.findComponent({ name: 'ContextMenu' }).props('model') as Entry[]
    const cancelEntry = items
      .find((item) => item.label === i18n.global.t('madeItems.demands.contextMenu.setStatus'))
      ?.items?.find((item) => item.label === i18n.global.t('madeItems.demands.status.canceled'))
    expect(cancelEntry?.command).toBeDefined()

    cancelEntry!.command!()
    await flushPromises()

    const dialog = wrapper.findComponent({ name: 'ConfirmActionDialog' })
    expect(dialog.props('visible')).toBe(true)
    expect(updateSpy).not.toHaveBeenCalled()

    dialog.vm.$emit('confirm')
    await flushPromises()

    expect(updateSpy).toHaveBeenCalledTimes(2)
    expect(dialog.props('visible')).toBe(false)
  })
})
