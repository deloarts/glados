import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'


function makeMethod(overrides: Partial<FabricationMethodResponse> = {}): FabricationMethodResponse {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-01-01',
    changed: '2026-01-01T00:00:00Z',
    changed_by_id: null,
    changed_by: null,
    name: { enGB: 'CNC Milling' },
    description: { enGB: 'Precision milling on CNC machines' },
    label_color: '#ffffff',
    label_font_color: '#000000',
    requires_machine: true,
    required_external: false,
    default_supplier_id: null,
    default_for_assemblies: false,
    archived: false,
    creator_id: 1,
    creator: null,
    lead_time_days: null,
    wait_after_minutes: null,
    ...overrides,
  }
}

function page(items: FabricationMethodResponse[], total = items.length) {
  return { data: { items, total, limit: 25, skip: 0 } }
}

const getMock = vi.fn<(url: string, config?: { params?: unknown }) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string, config?: { params?: unknown }) => {
      if (url === '/fabrication-methods/') {
        return getMock(url, config)
      }
      // e.g. the lazy `/suppliers` prefetch triggered on mount for the
      // default-supplier name lookup; resolve it sensibly rather than
      // requiring every test to know about it.
      return Promise.resolve(page([]))
    },
  },
}))

import FabricationMethodManagementTable from '../FabricationMethodManagementTable.vue'
import type { FabricationMethodResponse } from '@/features/fabrication-methods'

describe('FabricationMethodManagementTable', () => {
  beforeEach(() => {
    getMock.mockReset()
  })

  it('mounts, loads fabrication methods via the paginated fetch, and renders columns', async () => {
    getMock.mockResolvedValue(page([makeMethod()]))

    const wrapper = mountWithApp(FabricationMethodManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('CNC Milling')
    expect(getMock).toHaveBeenCalledWith('/fabrication-methods/', { params: { skip: 0, limit: 25 } })
  })

  it('is a lazy DataTable whose totalRecords comes from the server total', async () => {
    getMock.mockResolvedValue(page([makeMethod()], 120))

    const wrapper = mountWithApp(FabricationMethodManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const table = wrapper.findComponent({ name: 'DataTable' })
    expect(table.props('lazy')).toBe(true)
    expect(table.props('totalRecords')).toBe(120)
  })

  it('requests the next page with the correct skip on @page', async () => {
    getMock.mockResolvedValue(page([makeMethod()], 60))

    const wrapper = mountWithApp(FabricationMethodManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    getMock.mockClear()
    getMock.mockResolvedValue(page([makeMethod({ id: 2, name: { enGB: 'Second Page Method' } })], 60))

    const next = wrapper.find('[aria-label="Next Page"]')
    await next.trigger('click')
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/fabrication-methods/', { params: { skip: 25, limit: 25 } })
  })

  // selectionMode="single" makes every row keyboard-reachable
  // and gives Enter the same effect as a click, via the shared
  // useRowOpenGuard recipe proven on OrdersTable/ArticleGroupManagementTable.
  it('makes the first row keyboard-focusable', async () => {
    getMock.mockResolvedValue(page([makeMethod()]))
    const wrapper = mountWithApp(FabricationMethodManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const row = wrapper.find('tr[data-p-selectable-row="true"]')
    expect(row.exists()).toBe(true)
    expect(row.attributes('tabindex')).toBe('0')
  })

  it('opens the detail dialog on @row-select the same way @row-click does', async () => {
    const entity = makeMethod()
    getMock.mockResolvedValue(page([entity]))
    const wrapper = mountWithApp(FabricationMethodManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    expect(wrapper.findComponent({ name: 'ResourceDetailDialog' }).props('visible')).toBe(false)

    const dataTable = wrapper.findComponent({ name: 'DataTable' })
    dataTable.vm.$emit('row-select', { data: entity, index: 0, originalEvent: new Event('keydown') })
    await flushPromises()

    expect(wrapper.findComponent({ name: 'ResourceDetailDialog' }).props('visible')).toBe(true)
  })

  // Under `lazy` OpenVue, a header click only toggles the header icon and
  // emits @sort by itself; nothing is fetched unless this handler is wired
  // to translate that event into a fetch call.
  it('fetches with order_by/order_dir and resets to page 1 on a header sort click', async () => {
    getMock.mockResolvedValue(page([makeMethod()], 60))
    const wrapper = mountWithApp(FabricationMethodManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    // Move off page 1 first, so the sort click's reset is observable.
    getMock.mockClear()
    getMock.mockResolvedValue(page([makeMethod()], 60))
    await wrapper.find('[aria-label="Next Page"]').trigger('click')
    await flushPromises()

    getMock.mockClear()
    getMock.mockResolvedValue(page([makeMethod()], 60))
    const dataTable = wrapper.findComponent({ name: 'DataTable' })
    dataTable.vm.$emit('sort', { sortField: 'name', sortOrder: 1 })
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/fabrication-methods/', {
      params: { skip: 0, limit: 25, order_by: 'name', order_dir: 'asc' },
    })
  })

  it('shows the Archived tag for an archived row', async () => {
    getMock.mockResolvedValue(page([makeMethod({ archived: true })]))
    const wrapper = mountWithApp(FabricationMethodManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Archived')
  })

  it('shows the assembly default tag for the method flagged default_for_assemblies', async () => {
    getMock.mockResolvedValue(page([makeMethod({ default_for_assemblies: true })]))
    const wrapper = mountWithApp(FabricationMethodManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Assembly default')
  })

  it('does not mark the description column sortable (not in the backend allow-list)', async () => {
    getMock.mockResolvedValue(page([makeMethod()]))
    const wrapper = mountWithApp(FabricationMethodManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const column = wrapper
      .findAllComponents({ name: 'Column' })
      .find((c) => c.props('field') === 'description')
    expect(column?.props('sortable')).toBeFalsy()
  })
})
