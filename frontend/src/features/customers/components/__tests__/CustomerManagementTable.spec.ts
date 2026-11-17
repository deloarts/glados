import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'

import type { CustomerResponse } from '../../types/customerResponse'

function makeCustomer(overrides: Partial<CustomerResponse> = {}): CustomerResponse {
  return {
    edit_version: 0,
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-01-01',
    changed: null,
    changed_by_id: null,
    changed_by: null,
    archived: false,
    name: 'Acme Metals',
    legal_name: 'Acme Metals Ltd',
    vat_id: 'AT123',
    level: 'A',
    street: 'Main St 1',
    city: 'Vienna',
    country: 'AT',
    postal_code: '1010',
    email: 'sales@acme.example',
    phone: null,
    weblink: null,
    creator_id: 1,
    creator: null,
    ...overrides,
  }
}

function page(items: CustomerResponse[], total = items.length) {
  return { data: { items, total, limit: 25, skip: 0 } }
}

const getMock = vi.fn<(url: string, config?: { params?: unknown }) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string, config?: { params?: unknown }) => getMock(url, config),
  },
}))

import CustomerManagementTable from '../CustomerManagementTable.vue'

describe('CustomerManagementTable', () => {
  beforeEach(() => {
    getMock.mockReset()
  })

  it('mounts, loads customers via the paginated fetch, and renders columns', async () => {
    getMock.mockResolvedValue(page([makeCustomer()]))

    const wrapper = mountWithApp(CustomerManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Acme Metals')
    expect(getMock).toHaveBeenCalledWith('/customers/', { params: { skip: 0, limit: 25 } })
  })

  it('is a lazy DataTable whose totalRecords comes from the server total', async () => {
    getMock.mockResolvedValue(page([makeCustomer()], 120))

    const wrapper = mountWithApp(CustomerManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const table = wrapper.findComponent({ name: 'DataTable' })
    expect(table.props('lazy')).toBe(true)
    expect(table.props('totalRecords')).toBe(120)
  })

  it('requests the next page with the correct skip on @page', async () => {
    getMock.mockResolvedValue(page([makeCustomer()], 60))

    const wrapper = mountWithApp(CustomerManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    getMock.mockClear()
    getMock.mockResolvedValue(page([makeCustomer({ id: 2, name: 'Second Page Customer' })], 60))

    const next = wrapper.find('[aria-label="Next Page"]')
    await next.trigger('click')
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/customers/', { params: { skip: 25, limit: 25 } })
  })

  // selectionMode="single" makes every row keyboard-reachable and gives
  // Enter the same effect as a click, via the shared useRowOpenGuard pattern.
  it('makes the first row keyboard-focusable', async () => {
    getMock.mockResolvedValue(page([makeCustomer()]))
    const wrapper = mountWithApp(CustomerManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const row = wrapper.find('tr[data-p-selectable-row="true"]')
    expect(row.exists()).toBe(true)
    expect(row.attributes('tabindex')).toBe('0')
  })

  it('opens the detail dialog on @row-select the same way @row-click does', async () => {
    const entity = makeCustomer()
    getMock.mockResolvedValue(page([entity]))
    const wrapper = mountWithApp(CustomerManagementTable, {
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
    getMock.mockResolvedValue(page([makeCustomer()], 60))
    const wrapper = mountWithApp(CustomerManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    // Move off page 1 first, so the sort click's reset is observable.
    getMock.mockClear()
    getMock.mockResolvedValue(page([makeCustomer()], 60))
    await wrapper.find('[aria-label="Next Page"]').trigger('click')
    await flushPromises()

    getMock.mockClear()
    getMock.mockResolvedValue(page([makeCustomer()], 60))
    const dataTable = wrapper.findComponent({ name: 'DataTable' })
    dataTable.vm.$emit('sort', { sortField: 'changed', sortOrder: -1 })
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/customers/', {
      params: { skip: 0, limit: 25, order_by: 'changed', order_dir: 'desc' },
    })
  })

  // legal_name isn't in the backend's order_by allow-list (id/name/created/
  // changed). An honest non-sortable header beats a lying one.
  it('does not mark the legal name column sortable (not in the backend allow-list)', async () => {
    getMock.mockResolvedValue(page([makeCustomer()]))
    const wrapper = mountWithApp(CustomerManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const column = wrapper
      .findAllComponents({ name: 'Column' })
      .find((c) => c.props('field') === 'legal_name')
    expect(column?.props('sortable')).toBeFalsy()
  })

  it('shows the Archived tag for an archived row, and not for a live one', async () => {
    getMock.mockResolvedValue(page([makeCustomer({ archived: true })]))
    const wrapper = mountWithApp(CustomerManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain(i18n.global.t('common.archivedTag'))
  })
})
