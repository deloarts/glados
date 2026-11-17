import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'


function makeInspectionMethod(
  overrides: Partial<InspectionMethodResponse> = {},
): InspectionMethodResponse {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-01-01',
    changed: '2026-01-01T00:00:00Z',
    changed_by_id: null,
    changed_by: null,
    name: { enGB: 'Visual Inspection' },
    description: { enGB: 'Visual check against the drawing' },
    label_color: '#607d8b',
    label_font_color: '#ffffff',
    default_setup_minutes: null,
    default_minutes_per_piece: null,
    requires_evidence: false,
    default_machine_id: null,
    default_machine_name: null,
    archived: false,
    creator_id: 1,
    creator: null,
    ...overrides,
  }
}

function page(items: InspectionMethodResponse[], total = items.length) {
  return { data: { items, total, limit: 25, skip: 0 } }
}

const getMock = vi.fn<(url: string, config?: { params?: unknown }) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string, config?: { params?: unknown }) => getMock(url, config),
  },
}))

import InspectionMethodManagementTable from '../InspectionMethodManagementTable.vue'
import type { InspectionMethodResponse } from '@/features/inspection-methods'

describe('InspectionMethodManagementTable', () => {
  beforeEach(() => {
    getMock.mockReset()
  })

  it('mounts, loads inspection methods via the paginated fetch, and renders columns', async () => {
    getMock.mockResolvedValue(page([makeInspectionMethod()]))

    const wrapper = mountWithApp(InspectionMethodManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Visual Inspection')
    expect(getMock).toHaveBeenCalledWith('/inspection-methods/', {
      params: { skip: 0, limit: 25 },
    })
  })

  it('is a lazy DataTable whose totalRecords comes from the server total', async () => {
    getMock.mockResolvedValue(page([makeInspectionMethod()], 120))

    const wrapper = mountWithApp(InspectionMethodManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const table = wrapper.findComponent({ name: 'DataTable' })
    expect(table.props('lazy')).toBe(true)
    expect(table.props('totalRecords')).toBe(120)
  })

  it('requests the next page with the correct skip on @page', async () => {
    getMock.mockResolvedValue(page([makeInspectionMethod()], 60))

    const wrapper = mountWithApp(InspectionMethodManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    getMock.mockClear()
    getMock.mockResolvedValue(
      page([makeInspectionMethod({ id: 2, name: { enGB: 'Second Page Method' } })], 60),
    )

    const next = wrapper.find('[aria-label="Next Page"]')
    await next.trigger('click')
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/inspection-methods/', {
      params: { skip: 25, limit: 25 },
    })
  })

  // selectionMode="single" makes every row keyboard-reachable and gives Enter
  // the same effect as a click, via the shared useRowOpenGuard recipe.
  it('makes the first row keyboard-focusable', async () => {
    getMock.mockResolvedValue(page([makeInspectionMethod()]))
    const wrapper = mountWithApp(InspectionMethodManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const row = wrapper.find('tr[data-p-selectable-row="true"]')
    expect(row.exists()).toBe(true)
    expect(row.attributes('tabindex')).toBe('0')
  })

  it('opens the detail dialog on @row-select the same way @row-click does', async () => {
    const entity = makeInspectionMethod()
    getMock.mockResolvedValue(page([entity]))
    const wrapper = mountWithApp(InspectionMethodManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    expect(wrapper.findComponent({ name: 'ResourceDetailDialog' }).props('visible')).toBe(false)

    const dataTable = wrapper.findComponent({ name: 'DataTable' })
    dataTable.vm.$emit('row-select', {
      data: entity,
      index: 0,
      originalEvent: new Event('keydown'),
    })
    await flushPromises()

    expect(wrapper.findComponent({ name: 'ResourceDetailDialog' }).props('visible')).toBe(true)
  })

  // Under `lazy` OpenVue only emits @sort and fetches nothing itself, so the
  // table must wire the event or a header click would only toggle the icon.
  it('fetches with order_by/order_dir and resets to page 1 on a header sort click', async () => {
    getMock.mockResolvedValue(page([makeInspectionMethod()], 60))
    const wrapper = mountWithApp(InspectionMethodManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    // Move off page 1 first, so the sort click's reset is observable.
    getMock.mockClear()
    getMock.mockResolvedValue(page([makeInspectionMethod()], 60))
    await wrapper.find('[aria-label="Next Page"]').trigger('click')
    await flushPromises()

    getMock.mockClear()
    getMock.mockResolvedValue(page([makeInspectionMethod()], 60))
    const dataTable = wrapper.findComponent({ name: 'DataTable' })
    dataTable.vm.$emit('sort', { sortField: 'name', sortOrder: 1 })
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/inspection-methods/', {
      params: { skip: 0, limit: 25, order_by: 'name', order_dir: 'asc' },
    })
  })

  it('does not mark the description column sortable (not in the backend allow-list)', async () => {
    getMock.mockResolvedValue(page([makeInspectionMethod()]))
    const wrapper = mountWithApp(InspectionMethodManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const column = wrapper
      .findAllComponents({ name: 'Column' })
      .find((c) => c.props('field') === 'description')
    expect(column?.props('sortable')).toBeFalsy()
  })

  it('shows the Archived tag for an archived row', async () => {
    getMock.mockResolvedValue(page([makeInspectionMethod({ archived: true })]))
    const wrapper = mountWithApp(InspectionMethodManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Archived')
  })

  it('renders the default machine name when set', async () => {
    getMock.mockResolvedValue(
      page([makeInspectionMethod({ default_machine_id: 7, default_machine_name: 'CMM-07' })]),
    )
    const wrapper = mountWithApp(InspectionMethodManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('CMM-07')
  })

  it('renders the empty placeholder when no default machine is set', async () => {
    getMock.mockResolvedValue(
      page([
        makeInspectionMethod({
          name: { enGB: 'Manual QA Only' },
          default_machine_id: null,
          default_machine_name: null,
        }),
      ]),
    )
    const wrapper = mountWithApp(InspectionMethodManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('-')
  })
})
