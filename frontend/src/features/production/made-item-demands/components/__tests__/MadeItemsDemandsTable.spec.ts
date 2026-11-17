import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { i18n } from '@/core/i18n'
import { mountWithApp } from '@/test-utils/mountWithApp'

const demandsResponse = {
  data: {
    items: [
      {
        id: 1,
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
        made_item_id: 1,
        item_part_number: 'PN-1',
        item_article_name: 'Bracket',
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
    ],
    total: 1,
    limit: 25,
    skip: 0,
  },
}

vi.mock('@/core/api', () => ({
  default: {
    // URL-aware: the row-select tests open MadeItemDemandDetailDialog,
    // which fetches allocations/summaries for the demand from other
    // endpoints that expect an array/record shape, not this list envelope;
    // a blanket mock would hand them the wrong shape and crash the dialog's
    // `.find()` on the result (see the FabricationMethodManagementTable
    // spec for the same pattern with a different reason).
    get: vi.fn<(url: string) => Promise<unknown>>().mockImplementation((url: string) => {
      if (url === '/made-items-demands') return Promise.resolve(demandsResponse)
      if (url.startsWith('/made-items-allocations/demand/')) return Promise.resolve({ data: [] })
      if (url === '/made-items-allocations/summary') return Promise.resolve({ data: {} })
      // Generic paginated-envelope fallback for everything else this table
      // lazily prefetches on mount (usersStore, etc.), an empty page, not
      // an empty array, since those stores read `response.items`.
      return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import MadeItemsDemandsTable from '../MadeItemsDemandsTable.vue'
import { useMadeItemsDemandsFiltersStore } from '../../stores/madeItemsDemandsFiltersStore'
import { useMadeItemsProcurementStore } from '../../stores/madeItemsProcurementStore'
import { useMadeItemsDemandsStore } from '@/features/made-items'

describe('MadeItemsDemandsTable', () => {
  it('mounts with all columns without recursive update errors', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountWithApp(MadeItemsDemandsTable, {
      global: {
        stubs: { RouterLink: true },
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
    const wrapper = mountWithApp(MadeItemsDemandsTable, {
      global: {
        stubs: { RouterLink: true },
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
    const copyItem = items.find((item) => item.label === i18n.global.t('madeItems.demands.contextMenu.copy'))

    expect(copyItem).toBeDefined()
    expect(copyItem?.disabled).toBe(true)
  })

  // selectionMode="single" makes every row keyboard-reachable
  // and gives Enter the same effect as a click, via the shared
  // useRowOpenGuard recipe proven on OrdersTable/ArticleGroupManagementTable.
  it('makes the first row keyboard-focusable while the manage-lots panel is closed', async () => {
    const wrapper = mountWithApp(MadeItemsDemandsTable, {
      global: {
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
    const wrapper = mountWithApp(MadeItemsDemandsTable, {
      global: {
        stubs: { RouterLink: true },
      },
    })

    await flushPromises()
    await flushPromises()

    expect(wrapper.findComponent({ name: 'MadeItemDemandDetailDialog' }).props('visible')).toBe(
      false,
    )

    const demand = useMadeItemsDemandsStore().items[0]
    expect(demand).toBeDefined()

    const dataTable = wrapper.findComponent({ name: 'DataTable' })
    dataTable.vm.$emit('row-select', {
      data: demand,
      index: 0,
      type: 'row',
      originalEvent: new Event('keydown'),
    })
    await flushPromises()

    expect(wrapper.findComponent({ name: 'MadeItemDemandDetailDialog' }).props('visible')).toBe(
      true,
    )
  })

  // The Manage Lots panel's bulk checkbox column binds this same DataTable's
  // `selection`/`selectionMode` to an *array* (procurementStore.selectedDemands)
  // for batch lot actions. The new single-row-open wiring must not fight it
  // ("do not clobber existing nested selection" guard, verified empirically).
  it('does not clobber the bulk-lot selection array when a row is checked, then clicked, with the manage-lots panel open', async () => {
    const wrapper = mountWithApp(MadeItemsDemandsTable, {
      global: {
        stubs: { RouterLink: true },
      },
    })
    await flushPromises()
    await flushPromises()

    const filtersStore = useMadeItemsDemandsFiltersStore()
    filtersStore.showManageLotsPanel = true
    await flushPromises()

    const procurementStore = useMadeItemsProcurementStore()
    const checkbox = wrapper.find('input[type="checkbox"]')
    expect(checkbox.exists()).toBe(true)
    await checkbox.setValue(true)
    await flushPromises()

    expect(procurementStore.selectedDemands).toHaveLength(1)
    expect(procurementStore.selectedDemands[0]).toMatchObject({ id: 1 })

    const row = wrapper.find('tbody tr')
    await row.trigger('click')
    await flushPromises()

    expect(procurementStore.selectedDemands).toHaveLength(1)
    expect(procurementStore.selectedDemands[0]).toMatchObject({ id: 1 })
  })

  // The bulk-select checkbox click also bubbles into onRowClick, which would
  // open the detail dialog on top of the Manage Lots panel (see the "does
  // not clobber" test above for selection). onRowClick/onRowSelect are gated
  // on filtersStore.showManageLotsPanel so neither the checkbox nor a plain
  // row click can open the dialog while the panel is active, and selection
  // still works.
  it('does not open the demand detail dialog when the bulk-select checkbox or a plain row click fires with the manage-lots panel open', async () => {
    const wrapper = mountWithApp(MadeItemsDemandsTable, {
      global: { stubs: { RouterLink: true } },
    })
    await flushPromises()
    await flushPromises()

    const filtersStore = useMadeItemsDemandsFiltersStore()
    filtersStore.showManageLotsPanel = true
    await flushPromises()

    const dialog = () => wrapper.findComponent({ name: 'MadeItemDemandDetailDialog' })
    expect(dialog().props('visible')).toBe(false)

    const procurementStore = useMadeItemsProcurementStore()
    const checkbox = wrapper.find('input[type="checkbox"]')
    expect(checkbox.exists()).toBe(true)
    await checkbox.setValue(true)
    await flushPromises()

    expect(procurementStore.selectedDemands).toHaveLength(1)
    expect(dialog().props('visible')).toBe(false)

    const row = wrapper.find('tbody tr')
    await row.trigger('click')
    await flushPromises()

    expect(dialog().props('visible')).toBe(false)
    expect(procurementStore.selectedDemands).toHaveLength(1)
  })

  // The counterpart to the test above: with the panel closed, the row-open
  // gate must stay a no-op so a plain row click still opens the dialog.
  it('still opens the demand detail dialog on a plain row click while the manage-lots panel is closed', async () => {
    const wrapper = mountWithApp(MadeItemsDemandsTable, {
      global: { stubs: { RouterLink: true } },
    })
    await flushPromises()
    await flushPromises()

    const row = wrapper.find('tbody tr')
    await row.trigger('click')
    await flushPromises()

    expect(wrapper.findComponent({ name: 'MadeItemDemandDetailDialog' }).props('visible')).toBe(
      true,
    )
  })
})
