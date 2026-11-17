/**
 * Covers source-item demand buckets: the shared-selection/bucket behaviour
 * mirrored from BoughtItemsDemandsTable.spec.ts's template:
 * selectionMode="multiple" + metaKeySelection, the bulk checkbox column's
 * visibility, ctrl-click toggling (including on a link cell, via the
 * capture-phase replay), and the multi-target context menu.
 *
 * Kept as its own file beside SourceItemDemandsTable.spec.ts so the selection
 * behaviour stays separate from the table's other specs.
 */
import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import ConfirmationService from 'openvue/confirmationservice'

import { i18n } from '@/core/i18n'
import { mountWithApp } from '@/test-utils/mountWithApp'

const demandsResponse = {
  data: {
    items: [
      {
        id: 1,
        public_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
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
        bucket_id: null,
        bought_item_id: null,
        bought_item: null,
        source_item_id: 1,
        source_item: {
          id: 1,
          public_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
          status: 'active',
          deleted: false,
          created: '2026-01-01',
          changed: null,
          type_id: 1,
          type_name: 'Rod',
          dimension: '10mm',
          material: 'Steel',
          mass: 100,
          note: null,
          order_code_1: null,
          order_code_2: null,
          successor_item_id: null,
          creator_id: 1,
          creator: null,
          approver_id: null,
          manufacturer_id: null,
          manufacturer_name: '',
        },
        lot_id: 1,
        lot_number: 'LOT-0001',
        project_id: 1,
        project_number: 'P-001',
        project_customer: 'Acme',
        project_description: 'Test project',
        project_status: 'active',
      },
      {
        id: 2,
        public_id: 'cccccccc-cccc-cccc-cccc-cccccccccccc',
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
        bucket_id: null,
        bought_item_id: null,
        bought_item: null,
        source_item_id: 2,
        source_item: null,
        lot_id: 2,
        lot_number: 'LOT-0002',
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
      if (url === '/source-item-demands') return Promise.resolve(demandsResponse)
      return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    put: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import SourceItemDemandsTable from '../SourceItemDemandsTable.vue'
import { useSourceItemDemandsFiltersStore } from '../../stores/sourceItemDemandsFiltersStore'
import { useSourceItemDemandsSelectionStore } from '../../stores/sourceItemDemandsSelectionStore'
import { useSourceItemDemandsStore } from '@/features/source-items'

function mountTable() {
  return mountWithApp(SourceItemDemandsTable, {
    global: { plugins: [ConfirmationService], stubs: { RouterLink: true } },
  })
}

describe('SourceItemDemandsTable selection and buckets', () => {
  it('still opens the demand detail dialog on a plain row click while no panel is open', async () => {
    const wrapper = mountTable()
    await flushPromises()
    await flushPromises()

    const row = wrapper.find('tbody tr')
    await row.trigger('click')
    await flushPromises()

    expect(
      wrapper.findComponent({ name: 'SourceItemDemandDetailDialog' }).props('visible'),
    ).toBe(true)
  })

  it('ctrl-click toggles the row into the selection without opening the detail dialog', async () => {
    const wrapper = mountTable()
    await flushPromises()
    await flushPromises()

    const selectionStore = useSourceItemDemandsSelectionStore()
    expect(selectionStore.selectedDemands).toHaveLength(0)

    const row = wrapper.find('tbody tr')
    await row.trigger('click', { ctrlKey: true })
    await flushPromises()

    expect(selectionStore.selectedDemands).toHaveLength(1)
    expect(
      wrapper.findComponent({ name: 'SourceItemDemandDetailDialog' }).props('visible'),
    ).toBe(false)
  })

  // Most cells are plain text, but the lot number is a clickable link, and
  // OpenVue ignores row clicks whose target is clickable, so without the
  // capture-phase replay in the table, a modified click on it would open the
  // lot detail and not pick the row.
  it('ctrl-click on a link cell picks the row instead of opening the link', async () => {
    const wrapper = mountTable()
    await flushPromises()
    await flushPromises()

    const selectionStore = useSourceItemDemandsSelectionStore()
    const link = wrapper.find('tbody tr .lot-link')
    expect(link.exists()).toBe(true)
    await link.trigger('click', { ctrlKey: true })
    await flushPromises()

    expect(selectionStore.selectedDemands).toHaveLength(1)
    expect(
      wrapper.findComponent({ name: 'SourceItemDemandDetailDialog' }).props('visible'),
    ).toBe(false)
  })

  it('replaces selected rows with their fresh copies when the list refreshes', async () => {
    mountTable()
    await flushPromises()
    await flushPromises()

    const demandsStore = useSourceItemDemandsStore()
    const selectionStore = useSourceItemDemandsSelectionStore()
    const demand = demandsStore.items[0]
    expect(demand).toBeDefined()
    selectionStore.selectedDemands = [demand!]

    demandsStore.items = [{ ...demand!, quantity: 9 }, ...demandsStore.items.slice(1)]
    await flushPromises()

    expect(selectionStore.selectedDemands).toHaveLength(1)
    expect(selectionStore.selectedDemands[0]!.quantity).toBe(9)
  })

  it('shows the bulk-select checkbox column only while something is selected or a panel is open', async () => {
    const wrapper = mountTable()
    await flushPromises()
    await flushPromises()

    expect(wrapper.find('input[type="checkbox"]').exists()).toBe(false)

    const selectionStore = useSourceItemDemandsSelectionStore()
    const demand = useSourceItemDemandsStore().items[0]
    expect(demand).toBeDefined()
    selectionStore.selectedDemands = [demand!]
    await flushPromises()

    expect(wrapper.find('input[type="checkbox"]').exists()).toBe(true)

    selectionStore.clearSelection()
    await flushPromises()

    expect(wrapper.find('input[type="checkbox"]').exists()).toBe(false)

    const filtersStore = useSourceItemDemandsFiltersStore()
    filtersStore.showManageStockPanel = true
    await flushPromises()

    expect(wrapper.find('input[type="checkbox"]').exists()).toBe(true)
  })

  it('a plain click on a row keeps the panel selection and does not open the detail dialog while a panel is open', async () => {
    const wrapper = mountTable()
    await flushPromises()
    await flushPromises()

    const filtersStore = useSourceItemDemandsFiltersStore()
    filtersStore.showManageStockPanel = true
    await flushPromises()

    const selectionStore = useSourceItemDemandsSelectionStore()
    // Scoped to tbody: the selection column also renders a header
    // "select-all" checkbox, which (with 2 fixture rows) would otherwise
    // select both rows instead of just the one this test means to check.
    const checkbox = wrapper.find('tbody input[type="checkbox"]')
    expect(checkbox.exists()).toBe(true)
    await checkbox.setValue(true)
    await flushPromises()

    expect(selectionStore.selectedDemands).toHaveLength(1)

    const row = wrapper.find('tbody tr')
    await row.trigger('click')
    await flushPromises()

    expect(selectionStore.selectedDemands).toHaveLength(1)
    expect(
      wrapper.findComponent({ name: 'SourceItemDemandDetailDialog' }).props('visible'),
    ).toBe(false)
  })

  it('shows a multi-target context menu when the right-clicked row is part of the current selection', async () => {
    const wrapper = mountTable()
    await flushPromises()
    await flushPromises()

    const demand = useSourceItemDemandsStore().items[0]
    expect(demand).toBeDefined()

    const selectionStore = useSourceItemDemandsSelectionStore()
    selectionStore.selectedDemands = [demand!, { ...demand!, id: 2 }]

    const row = wrapper.find('tbody tr')
    await row.trigger('contextmenu')
    await flushPromises()

    const contextMenu = wrapper.findComponent({ name: 'ContextMenu' })
    const items = contextMenu.props('model') as Array<{ label?: string }>
    const labels = items.map((item) => item.label)

    expect(labels).toContain(i18n.global.t('sourceItems.demands.contextMenu.setStatus'))
    expect(labels).toContain(i18n.global.t('sourceItems.demands.contextMenu.addToOrder'))
    expect(labels).toContain(i18n.global.t('sourceItems.demands.contextMenu.fulfillFromStock'))
    expect(labels).toContain(i18n.global.t('sourceItems.demands.contextMenu.addToBucket'))
  })

  // Bulk cancel is irreversible and skips the single-row impact preview, so
  // the multi-target "canceled" entry must go through ConfirmActionDialog
  // first and only fire the N updates once confirmed.
  it('asks what becomes of the lots before a multi-target cancel and only then cancels every target', async () => {
    const wrapper = mountTable()
    await flushPromises()
    await flushPromises()

    const demandsStore = useSourceItemDemandsStore()
    const demand = demandsStore.items[0]
    expect(demand).toBeDefined()
    const updateSpy = vi.spyOn(demandsStore, 'cancelByStatus').mockResolvedValue(demand!)

    useSourceItemDemandsSelectionStore().selectedDemands = [demand!, { ...demand!, id: 2 }]

    await wrapper.find('tbody tr').trigger('contextmenu')
    await flushPromises()

    type Entry = { label?: string; items?: Entry[]; command?: () => void }
    const items = wrapper.findComponent({ name: 'ContextMenu' }).props('model') as Entry[]
    const cancelEntry = items
      .find((item) => item.label === i18n.global.t('sourceItems.demands.contextMenu.setStatus'))
      ?.items?.find((item) => item.label === i18n.global.t('sourceItems.demands.status.canceled'))
    expect(cancelEntry?.command).toBeDefined()

    cancelEntry!.command!()
    await flushPromises()

    const dialog = wrapper.findComponent({ name: 'SourceItemDemandCancelDialog' })
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('demands')).toHaveLength(2)
    expect(updateSpy).not.toHaveBeenCalled()

    dialog.vm.$emit('confirm', true)
    await flushPromises()

    expect(updateSpy).toHaveBeenCalledTimes(2)
    expect(updateSpy).toHaveBeenCalledWith(2, true)
  })
})
