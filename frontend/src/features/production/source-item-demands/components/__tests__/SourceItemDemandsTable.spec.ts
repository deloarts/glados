import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import ConfirmationService from 'openvue/confirmationservice'

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
        ],
        total: 1,
        limit: 25,
        skip: 0,
      },
    }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import SourceItemDemandsTable from '../SourceItemDemandsTable.vue'
import { useSourceItemDemandsFiltersStore } from '../../stores/sourceItemDemandsFiltersStore'
import { useSourceItemDemandsSelectionStore } from '../../stores/sourceItemDemandsSelectionStore'
import { useSourceItemsAllocationsStore } from '../../stores/sourceItemsAllocationsStore'
import { useSourceItemDemandsStore } from '@/features/source-items'

// The nested order detail dialog renders the handbook drawer, which reads
// the current route, so the table mounts with a real memory router.
async function mountTable() {
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
  return mountWithApp(SourceItemDemandsTable, {
    global: {
      plugins: [router, ConfirmationService],
    },
  })
}

// selectionMode="single" makes every row keyboard-reachable and
// gives Enter the same effect as a click, via the shared useRowOpenGuard
// recipe proven on OrdersTable/ArticleGroupManagementTable. This table had
// no general smoke spec before (only the manage-order-filter one), so this
// file is new.
describe('SourceItemDemandsTable', () => {
  it('mounts with all columns without recursive update errors', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = await mountTable()
    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(wrapper.exists()).toBe(true)
    expect(logs).toEqual([])
  })

  it('makes the first row keyboard-focusable while the manage-order panel is closed', async () => {
    const wrapper = await mountTable()
    await flushPromises()
    await flushPromises()

    const row = wrapper.find('tr[data-p-selectable-row="true"]')
    expect(row.exists()).toBe(true)
    expect(row.attributes('tabindex')).toBe('0')
  })

  it('opens the demand detail dialog on @row-select the same way @row-click does', async () => {
    const wrapper = await mountTable()
    await flushPromises()
    await flushPromises()

    expect(wrapper.findComponent({ name: 'SourceItemDemandDetailDialog' }).props('visible')).toBe(
      false,
    )

    const demand = useSourceItemDemandsStore().items[0]
    expect(demand).toBeDefined()

    const dataTable = wrapper.findComponent({ name: 'DataTable' })
    dataTable.vm.$emit('row-select', {
      data: demand,
      index: 0,
      type: 'row',
      originalEvent: new Event('keydown'),
    })
    await flushPromises()

    expect(wrapper.findComponent({ name: 'SourceItemDemandDetailDialog' }).props('visible')).toBe(
      true,
    )
  })

  // The Manage Orders panel's bulk checkbox column binds this same
  // DataTable's `selection`/`selectionMode` to an *array*
  // (selectionStore.selectedDemands) for batch order actions, and the new
  // single-row-open wiring must not fight it (the "do not clobber
  // existing nested selection" guard, verified empirically).
  it('does not clobber the bulk-order selection array when a row is checked, then clicked, with the manage-order panel open', async () => {
    const wrapper = await mountTable()
    await flushPromises()
    await flushPromises()

    const filtersStore = useSourceItemDemandsFiltersStore()
    filtersStore.showManageOrderPanel = true
    await flushPromises()

    const selectionStore = useSourceItemDemandsSelectionStore()
    const checkbox = wrapper.find('input[type="checkbox"]')
    expect(checkbox.exists()).toBe(true)
    await checkbox.setValue(true)
    await flushPromises()

    expect(selectionStore.selectedDemands).toHaveLength(1)
    expect(selectionStore.selectedDemands[0]).toMatchObject({ id: 1 })

    const row = wrapper.find('tbody tr')
    await row.trigger('click')
    await flushPromises()

    expect(selectionStore.selectedDemands).toHaveLength(1)
    expect(selectionStore.selectedDemands[0]).toMatchObject({ id: 1 })
  })

  // The bulk-select checkbox click also bubbles into onRowClick, which would
  // open the detail dialog on top of the Manage Orders panel (see the "does
  // not clobber" test above for selection). onRowClick/onRowSelect are gated
  // on filtersStore.showManageOrderPanel so neither the checkbox nor a plain
  // row click can open the dialog while the panel is active, and selection
  // still works.
  it('does not open the demand detail dialog when the bulk-select checkbox or a plain row click fires with the manage-order panel open', async () => {
    const wrapper = mountWithApp(SourceItemDemandsTable, {
      global: { plugins: [ConfirmationService], stubs: { RouterLink: true } },
    })
    await flushPromises()
    await flushPromises()

    const filtersStore = useSourceItemDemandsFiltersStore()
    filtersStore.showManageOrderPanel = true
    await flushPromises()

    const dialog = () => wrapper.findComponent({ name: 'SourceItemDemandDetailDialog' })
    expect(dialog().props('visible')).toBe(false)

    const selectionStore = useSourceItemDemandsSelectionStore()
    const checkbox = wrapper.find('input[type="checkbox"]')
    expect(checkbox.exists()).toBe(true)
    await checkbox.setValue(true)
    await flushPromises()

    expect(selectionStore.selectedDemands).toHaveLength(1)
    expect(dialog().props('visible')).toBe(false)

    const row = wrapper.find('tbody tr')
    await row.trigger('click')
    await flushPromises()

    expect(dialog().props('visible')).toBe(false)
    expect(selectionStore.selectedDemands).toHaveLength(1)
  })

  // The counterpart to the test above: with the panel closed, the row-open
  // gate must stay a no-op so a plain row click still opens the dialog.
  it('still opens the demand detail dialog on a plain row click while the manage-order panel is closed', async () => {
    const wrapper = mountWithApp(SourceItemDemandsTable, {
      global: { plugins: [ConfirmationService], stubs: { RouterLink: true } },
    })
    await flushPromises()
    await flushPromises()

    const row = wrapper.find('tbody tr')
    await row.trigger('click')
    await flushPromises()

    expect(
      wrapper.findComponent({ name: 'SourceItemDemandDetailDialog' }).props('visible'),
    ).toBe(true)
  })

  it('closes the demand detail dialog once the dialog reports an update, as after a cancel', async () => {
    const wrapper = await mountTable()
    await flushPromises()
    await flushPromises()

    await wrapper.find('tbody tr').trigger('click')
    await flushPromises()
    const dialog = wrapper.findComponent({ name: 'SourceItemDemandDetailDialog' })
    expect(dialog.props('visible')).toBe(true)

    const demand = useSourceItemDemandsStore().items[0]
    dialog.vm.$emit('updated', { ...demand, status: 'canceled', actions: [] })
    await flushPromises()

    expect(
      wrapper.findComponent({ name: 'SourceItemDemandDetailDialog' }).props('visible'),
    ).toBe(false)
  })

  it('renders a substitution label in the item column when the allocation summary carries one', async () => {
    const wrapper = await mountTable()
    await flushPromises()
    await flushPromises()

    const allocationsStore = useSourceItemsAllocationsStore()
    allocationsStore.summaries[1] = {
      demand_item_id: 1,
      unit: 'PCS',
      total: 5,
      allocated: 5,
      fulfilled_from_stock: 0,
      ordered: 5,
      delivered: 0,
      remaining: 5,
      unallocated: 0,
      pending: 5,
      in_transit: 0,
      is_fully_allocated: true,
      is_fully_delivered: false,
      unit_mismatch: false,
      order_ids: [],
      order_numbers: [],
      substitutions: [
        {
          substitute_source_item_id: 2,
          substitute_item_article_name: '12mm',
          substitute_item_order_code_1: 'RB-12',
          substitute_item_specification: '',
          substitute_reason: 'Preferred stock size',
          quantity: 5,
        },
      ],
    }
    await flushPromises()

    const substInfo = wrapper.find('.subst-info')
    expect(substInfo.exists()).toBe(true)
    expect(substInfo.find('.subst-label').text()).toBe('12mm - RB-12')
  })
})
