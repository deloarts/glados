import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'

import type { SourceItemTypeResponse } from '../../types/sourceItemTypeResponse'

function makeSourceItemType(
  overrides: Partial<SourceItemTypeResponse> = {},
): SourceItemTypeResponse {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-01-01',
    changed: '2026-01-01T00:00:00Z',
    changed_by_id: null,
    changed_by: null,
    archived: false,
    name: { enGB: 'Raw Steel' },
    label_color: '#ffffff',
    label_font_color: '#000000',
    description: { enGB: 'Raw steel stock' },
    creator_id: 1,
    creator: null,
    ...overrides,
  }
}

function page(items: SourceItemTypeResponse[], total = items.length) {
  return { data: { items, total, limit: 25, skip: 0 } }
}

const getMock = vi.fn<(url: string, config?: { params?: unknown }) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string, config?: { params?: unknown }) => getMock(url, config),
  },
}))

import SourceItemTypeManagementTable from '../SourceItemTypeManagementTable.vue'

describe('SourceItemTypeManagementTable', () => {
  beforeEach(() => {
    getMock.mockReset()
  })

  it('mounts, loads source item types via the paginated fetch, and renders columns', async () => {
    getMock.mockResolvedValue(page([makeSourceItemType()]))

    const wrapper = mountWithApp(SourceItemTypeManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Raw Steel')
    expect(getMock).toHaveBeenCalledWith('/source-item-types/', { params: { skip: 0, limit: 25 } })
  })

  it('is a lazy DataTable whose totalRecords comes from the server total', async () => {
    getMock.mockResolvedValue(page([makeSourceItemType()], 120))

    const wrapper = mountWithApp(SourceItemTypeManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const table = wrapper.findComponent({ name: 'DataTable' })
    expect(table.props('lazy')).toBe(true)
    expect(table.props('totalRecords')).toBe(120)
  })

  it('requests the next page with the correct skip on @page', async () => {
    getMock.mockResolvedValue(page([makeSourceItemType()], 60))

    const wrapper = mountWithApp(SourceItemTypeManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    getMock.mockClear()
    getMock.mockResolvedValue(
      page([makeSourceItemType({ id: 2, name: { enGB: 'Second Page Type' } })], 60),
    )

    const next = wrapper.find('[aria-label="Next Page"]')
    await next.trigger('click')
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/source-item-types/', { params: { skip: 25, limit: 25 } })
  })

  // selectionMode="single" makes every row keyboard-reachable and gives
  // Enter the same effect as a click, via the shared useRowOpenGuard recipe.
  it('makes the first row keyboard-focusable', async () => {
    getMock.mockResolvedValue(page([makeSourceItemType()]))
    const wrapper = mountWithApp(SourceItemTypeManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const row = wrapper.find('tr[data-p-selectable-row="true"]')
    expect(row.exists()).toBe(true)
    expect(row.attributes('tabindex')).toBe('0')
  })

  it('opens the detail dialog on @row-select the same way @row-click does', async () => {
    const entity = makeSourceItemType()
    getMock.mockResolvedValue(page([entity]))
    const wrapper = mountWithApp(SourceItemTypeManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    expect(wrapper.findComponent({ name: 'ResourceDetailDialog' }).props('visible')).toBe(false)

    const dataTable = wrapper.findComponent({ name: 'DataTable' })
    dataTable.vm.$emit('row-select', { data: entity, index: 0, originalEvent: new Event('keydown') })
    await flushPromises()

    expect(wrapper.findComponent({ name: 'ResourceDetailDialog' }).props('visible')).toBe(true)
  })

  // Under `lazy` OpenVue only emits @sort and fetches nothing itself, so the
  // table must wire the event or a header click would only toggle the icon.
  it('fetches with order_by/order_dir and resets to page 1 on a header sort click', async () => {
    getMock.mockResolvedValue(page([makeSourceItemType()], 60))
    const wrapper = mountWithApp(SourceItemTypeManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    // Move off page 1 first, so the sort click's reset is observable.
    getMock.mockClear()
    getMock.mockResolvedValue(page([makeSourceItemType()], 60))
    await wrapper.find('[aria-label="Next Page"]').trigger('click')
    await flushPromises()

    getMock.mockClear()
    getMock.mockResolvedValue(page([makeSourceItemType()], 60))
    const dataTable = wrapper.findComponent({ name: 'DataTable' })
    dataTable.vm.$emit('sort', { sortField: 'name', sortOrder: 1 })
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/source-item-types/', {
      params: { skip: 0, limit: 25, order_by: 'name', order_dir: 'asc' },
    })
  })

  it('shows the Archived tag for an archived row', async () => {
    getMock.mockResolvedValue(page([makeSourceItemType({ archived: true })]))
    const wrapper = mountWithApp(SourceItemTypeManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Archived')
  })

  it('does not mark the description column sortable (not in the backend allow-list)', async () => {
    getMock.mockResolvedValue(page([makeSourceItemType()]))
    const wrapper = mountWithApp(SourceItemTypeManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const column = wrapper
      .findAllComponents({ name: 'Column' })
      .find((c) => c.props('field') === 'description')
    expect(column?.props('sortable')).toBeFalsy()
  })
})
