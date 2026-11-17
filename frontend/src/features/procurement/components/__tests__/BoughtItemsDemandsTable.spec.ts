import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import ConfirmationService from 'openvue/confirmationservice'

import { i18n } from '@/core/i18n'
import { mountWithApp } from '@/test-utils/mountWithApp'

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
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
import { useBoughtItemsDemandsFiltersStore } from '../../stores/boughtItemsDemandsFiltersStore'
import { useBoughtItemsProcurementStore } from '../../stores/boughtItemsProcurementStore'
import { useBoughtItemsDemandsStore } from '@/features/bought-items'

// This table always renders OrderDetailDialog (visibility is a prop, not a
// v-if), and that dialog calls useConfirm() unconditionally in its own
// setup() for its remove-item confirm, so mounting this table
// needs ConfirmationService in scope even though the table itself has no
// confirm of its own.
describe('BoughtItemsDemandsTable', () => {
  it('mounts with all columns without recursive update errors', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    // The nested order detail dialog renders the handbook drawer, which
    // reads the current route, so the smoke mount needs a real router.
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
      { path: '/', component: { template: '<div />' } },
      // Project links in the rows resolve real paths; a catch-all keeps the
      // router quiet about them without listing the app's routes here.
      { path: '/:pathMatch(.*)*', component: { template: '<div />' } },
    ],
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

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(wrapper.exists()).toBe(true)
    expect(logs).toEqual([])
  })

  // Copy is not implemented, so its context-menu entry is disabled and
  // inert rather than a stub that would imply a working feature.
  it('renders the Copy context-menu entry as disabled rather than a live stub', async () => {
    // The nested order detail dialog renders the handbook drawer, which
    // reads the current route, so the smoke mount needs a real router.
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
      { path: '/', component: { template: '<div />' } },
      // Project links in the rows resolve real paths; a catch-all keeps the
      // router quiet about them without listing the app's routes here.
      { path: '/:pathMatch(.*)*', component: { template: '<div />' } },
    ],
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

    const row = wrapper.find('tbody tr')
    expect(row.exists()).toBe(true)
    await row.trigger('contextmenu')
    await flushPromises()

    const contextMenu = wrapper.findComponent({ name: 'ContextMenu' })
    expect(contextMenu.exists()).toBe(true)

    const items = contextMenu.props('model') as Array<{ label?: string; disabled?: boolean }>
    const copyItem = items.find((item) => item.label === i18n.global.t('boughtItems.demands.contextMenu.copy'))

    expect(copyItem).toBeDefined()
    expect(copyItem?.disabled).toBe(true)
  })

  // selectionMode="multiple" with metaKeySelection makes every row
  // keyboard-focusable via the useRowOpenGuard recipe, giving Enter the
  // same effect as a click.
  it('makes the first row keyboard-focusable while the manage-order panel is closed', async () => {
    const wrapper = mountWithApp(BoughtItemsDemandsTable, {
      global: {
        plugins: [ConfirmationService],
        stubs: { RouterLink: true },
      },
    })

    await flushPromises()
    await flushPromises()

    const row = wrapper.find('tr[data-p-selectable-row="true"]')
    expect(row.exists()).toBe(true)
    expect(row.attributes('tabindex')).toBe('0')
  })

  it('opens the demand detail dialog on @row-select the same way @row-click does', async () => {
    const wrapper = mountWithApp(BoughtItemsDemandsTable, {
      global: {
        plugins: [ConfirmationService],
        stubs: { RouterLink: true },
      },
    })

    await flushPromises()
    await flushPromises()

    expect(wrapper.findComponent({ name: 'BoughtItemDemandDetailDialog' }).props('visible')).toBe(false)

    // The real fetched row, not a hand-typed partial; BoughtItemDemandDetailDialog
    // reads several nested fields (item.manufacturer_name, etc.) off it
    // synchronously.
    const demand = useBoughtItemsDemandsStore().items[0]
    expect(demand).toBeDefined()

    const dataTable = wrapper.findComponent({ name: 'DataTable' })
    dataTable.vm.$emit('row-select', {
      data: demand,
      index: 0,
      type: 'row',
      originalEvent: new Event('keydown'),
    })
    await flushPromises()

    expect(wrapper.findComponent({ name: 'BoughtItemDemandDetailDialog' }).props('visible')).toBe(true)
  })

  // The bulk checkbox column binds this same DataTable's `selection` to
  // procurementStore.selectedDemands (an array, shared across the whole
  // table, not just the Manage Orders panel); checking it must not
  // also open the detail dialog (checkbox toggles emit `row-select` with
  // `type: 'checkbox'`, which onRowSelect ignores).
  it('checking the bulk-select checkbox does not open the demand detail dialog', async () => {
    const wrapper = mountWithApp(BoughtItemsDemandsTable, {
      global: { plugins: [ConfirmationService], stubs: { RouterLink: true } },
    })
    await flushPromises()
    await flushPromises()

    const filtersStore = useBoughtItemsDemandsFiltersStore()
    filtersStore.showManageOrderPanel = true
    await flushPromises()

    const dialog = () => wrapper.findComponent({ name: 'BoughtItemDemandDetailDialog' })
    expect(dialog().props('visible')).toBe(false)

    const procurementStore = useBoughtItemsProcurementStore()
    const checkbox = wrapper.find('input[type="checkbox"]')
    expect(checkbox.exists()).toBe(true)
    await checkbox.setValue(true)
    await flushPromises()

    expect(procurementStore.selectedDemands).toHaveLength(1)
    expect(dialog().props('visible')).toBe(false)
  })

  // A plain click always opens the detail dialog and clears the selection.
  // Only the checkbox column (see the test above) or a modifier key keeps
  // the batch selection intact.
  // While a panel owns the selection, a plain row click is a no-op: OpenVue
  // replaces the selection with [row], but onRowSelect restores the panel's
  // working set instead.
  it('a plain click on a row keeps the panel selection and does not open the detail dialog while the Manage Orders panel is open', async () => {
    const wrapper = mountWithApp(BoughtItemsDemandsTable, {
      global: { plugins: [ConfirmationService], stubs: { RouterLink: true } },
    })
    await flushPromises()
    await flushPromises()

    const filtersStore = useBoughtItemsDemandsFiltersStore()
    filtersStore.showManageOrderPanel = true
    await flushPromises()

    const procurementStore = useBoughtItemsProcurementStore()
    const checkbox = wrapper.find('input[type="checkbox"]')
    expect(checkbox.exists()).toBe(true)
    await checkbox.setValue(true)
    await flushPromises()

    expect(procurementStore.selectedDemands).toHaveLength(1)

    const row = wrapper.find('tbody tr')
    await row.trigger('click')
    await flushPromises()

    expect(procurementStore.selectedDemands).toHaveLength(1)
    expect(wrapper.findComponent({ name: 'BoughtItemDemandDetailDialog' }).props('visible')).toBe(false)
  })

  // The counterpart to the test above: with the panel closed,
  // the plain click is the open gesture (and clears any selection).
  it('still opens the demand detail dialog on a plain row click while the manage-order panel is closed', async () => {
    const wrapper = mountWithApp(BoughtItemsDemandsTable, {
      global: { plugins: [ConfirmationService], stubs: { RouterLink: true } },
    })
    await flushPromises()
    await flushPromises()

    const row = wrapper.find('tbody tr')
    await row.trigger('click')
    await flushPromises()

    expect(wrapper.findComponent({ name: 'BoughtItemDemandDetailDialog' }).props('visible')).toBe(true)
  })

  it('ctrl-click toggles the row into the selection without opening the detail dialog', async () => {
    const wrapper = mountWithApp(BoughtItemsDemandsTable, {
      global: { plugins: [ConfirmationService], stubs: { RouterLink: true } },
    })
    await flushPromises()
    await flushPromises()

    const procurementStore = useBoughtItemsProcurementStore()
    expect(procurementStore.selectedDemands).toHaveLength(0)

    const row = wrapper.find('tbody tr')
    await row.trigger('click', { ctrlKey: true })
    await flushPromises()

    expect(procurementStore.selectedDemands).toHaveLength(1)
    expect(wrapper.findComponent({ name: 'BoughtItemDemandDetailDialog' }).props('visible')).toBe(false)
  })

  // Most cells are links, and OpenVue ignores row clicks whose target is
  // clickable, so without the capture-phase replay in the table, a modified
  // click on a link would open the link and not pick the row.
  it('ctrl-click on a link cell picks the row instead of opening the link', async () => {
    const wrapper = mountWithApp(BoughtItemsDemandsTable, {
      global: { plugins: [ConfirmationService], stubs: { RouterLink: true } },
    })
    await flushPromises()
    await flushPromises()

    const procurementStore = useBoughtItemsProcurementStore()
    const link = wrapper.find('tbody tr .item-link')
    expect(link.exists()).toBe(true)
    await link.trigger('click', { ctrlKey: true })
    await flushPromises()

    expect(procurementStore.selectedDemands).toHaveLength(1)
    expect(wrapper.findComponent({ name: 'BoughtItemDetailDialog' }).props('visible')).toBe(false)
    expect(wrapper.findComponent({ name: 'BoughtItemDemandDetailDialog' }).props('visible')).toBe(false)
  })

  it('shows the bulk-select checkbox column only while something is selected or a panel is open', async () => {
    const wrapper = mountWithApp(BoughtItemsDemandsTable, {
      global: { plugins: [ConfirmationService], stubs: { RouterLink: true } },
    })
    await flushPromises()
    await flushPromises()

    expect(wrapper.find('input[type="checkbox"]').exists()).toBe(false)

    const procurementStore = useBoughtItemsProcurementStore()
    const demand = useBoughtItemsDemandsStore().items[0]
    expect(demand).toBeDefined()
    procurementStore.selectedDemands = [demand!]
    await flushPromises()

    expect(wrapper.find('input[type="checkbox"]').exists()).toBe(true)

    procurementStore.clearSelection()
    await flushPromises()

    expect(wrapper.find('input[type="checkbox"]').exists()).toBe(false)

    const filtersStore = useBoughtItemsDemandsFiltersStore()
    filtersStore.showManageStockPanel = true
    await flushPromises()

    expect(wrapper.find('input[type="checkbox"]').exists()).toBe(true)
  })

  it('shows a multi-target context menu when the right-clicked row is part of the current selection', async () => {
    const wrapper = mountWithApp(BoughtItemsDemandsTable, {
      global: { plugins: [ConfirmationService], stubs: { RouterLink: true } },
    })
    await flushPromises()
    await flushPromises()

    const demand = useBoughtItemsDemandsStore().items[0]
    expect(demand).toBeDefined()

    const procurementStore = useBoughtItemsProcurementStore()
    procurementStore.selectedDemands = [demand!, { ...demand!, id: 2 }]

    const row = wrapper.find('tbody tr')
    await row.trigger('contextmenu')
    await flushPromises()

    const contextMenu = wrapper.findComponent({ name: 'ContextMenu' })
    const items = contextMenu.props('model') as Array<{ label?: string }>
    const labels = items.map((item) => item.label)

    expect(labels).toContain(i18n.global.t('boughtItems.demands.contextMenu.setStatus'))
    expect(labels).toContain(i18n.global.t('boughtItems.demands.contextMenu.addToOrder'))
    expect(labels).toContain(i18n.global.t('boughtItems.demands.contextMenu.fulfillFromStock'))
    expect(labels).toContain(i18n.global.t('boughtItems.demands.contextMenu.addToBucket'))
  })

  // Bulk cancel is irreversible and skips the single-row impact preview, so
  // the multi-target "canceled" entry must go through ConfirmActionDialog
  // first and only fire the N updates once confirmed.
  it('asks for confirmation before a multi-target cancel and only then updates every target', async () => {
    const wrapper = mountWithApp(BoughtItemsDemandsTable, {
      global: { plugins: [ConfirmationService], stubs: { RouterLink: true } },
    })
    await flushPromises()
    await flushPromises()

    const demandsStore = useBoughtItemsDemandsStore()
    const demand = demandsStore.items[0]
    expect(demand).toBeDefined()
    const updateSpy = vi.spyOn(demandsStore, 'updateStatus').mockResolvedValue(demand!)

    useBoughtItemsProcurementStore().selectedDemands = [demand!, { ...demand!, id: 2 }]

    await wrapper.find('tbody tr').trigger('contextmenu')
    await flushPromises()

    type Entry = { label?: string; items?: Entry[]; command?: () => void }
    const items = wrapper.findComponent({ name: 'ContextMenu' }).props('model') as Entry[]
    const cancelEntry = items
      .find((item) => item.label === i18n.global.t('boughtItems.demands.contextMenu.setStatus'))
      ?.items?.find((item) => item.label === i18n.global.t('boughtItems.demands.status.canceled'))
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

  // Marking demands fulfilled releases what their order lines have not
  // delivered yet, so the status entry asks first and only then updates.
  it('asks for confirmation before marking demands fulfilled', async () => {
    const wrapper = mountWithApp(BoughtItemsDemandsTable, {
      global: { plugins: [ConfirmationService], stubs: { RouterLink: true } },
    })
    await flushPromises()
    await flushPromises()

    const demandsStore = useBoughtItemsDemandsStore()
    const demand = demandsStore.items[0]
    expect(demand).toBeDefined()
    const updateSpy = vi.spyOn(demandsStore, 'updateStatus').mockResolvedValue(demand!)

    useBoughtItemsProcurementStore().selectedDemands = [demand!, { ...demand!, id: 2 }]

    await wrapper.find('tbody tr').trigger('contextmenu')
    await flushPromises()

    type Entry = { label?: string; items?: Entry[]; command?: () => void }
    const items = wrapper.findComponent({ name: 'ContextMenu' }).props('model') as Entry[]
    const fulfilEntry = items
      .find((item) => item.label === i18n.global.t('boughtItems.demands.contextMenu.setStatus'))
      ?.items?.find((item) => item.label === i18n.global.t('boughtItems.demands.status.fulfilled'))
    expect(fulfilEntry?.command).toBeDefined()

    fulfilEntry!.command!()
    await flushPromises()

    const dialog = wrapper
      .findAllComponents({ name: 'ConfirmActionDialog' })
      .find((d) => d.props('header') === i18n.global.t('boughtItems.demands.contextMenu.fulfilHeader'))!
    expect(dialog.props('visible')).toBe(true)
    expect(updateSpy).not.toHaveBeenCalled()

    dialog.vm.$emit('confirm')
    await flushPromises()

    expect(updateSpy).toHaveBeenCalledTimes(2)
    expect(updateSpy).toHaveBeenCalledWith(2, 'fulfilled')
  })

  // A fulfilled demand's server actions are empty: it takes no allocation,
  // order line or quote request any more, so those entries leave its menu.
  it('leaves the allocation and panel entries out of the menu of a demand without the allocate action', async () => {
    const wrapper = mountWithApp(BoughtItemsDemandsTable, {
      global: { plugins: [ConfirmationService], stubs: { RouterLink: true } },
    })
    await flushPromises()
    await flushPromises()

    const demandsStore = useBoughtItemsDemandsStore()
    demandsStore.items = [{ ...demandsStore.items[0]!, status: 'fulfilled', actions: [] }]
    useBoughtItemsProcurementStore().selectedDemands = []
    await flushPromises()

    await wrapper.find('tbody tr').trigger('contextmenu')
    await flushPromises()

    const items = wrapper.findComponent({ name: 'ContextMenu' }).props('model') as Array<{
      label?: string
    }>
    const labels = items.map((item) => item.label)
    expect(labels).toContain(i18n.global.t('boughtItems.demands.contextMenu.edit'))
    for (const key of [
      'boughtItems.demands.detail.autoAllocate',
      'boughtItems.demands.contextMenu.manageAllocations',
      'boughtItems.demands.detail.fulfillFromStock',
      'boughtItems.demands.contextMenu.addToOrder',
      'boughtItems.demands.contextMenu.addToQuote',
    ]) {
      expect(labels).not.toContain(i18n.global.t(key))
    }
  })
})
