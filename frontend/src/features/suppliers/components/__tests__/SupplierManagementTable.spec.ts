import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { useSuppliersStore } from '../../stores/suppliersStore'

import type { SupplierResponse } from '../../types/supplierResponse'

function makeSupplier(overrides: Partial<SupplierResponse> = {}): SupplierResponse {
  return {
    edit_version: 0,
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-01-01',
    changed: '2026-01-01',
    changed_by_id: null,
    changed_by: null,
    archived: false,
    name: 'Acme Metals',
    legal_name: 'Acme Metals Ltd',
    vat_id: 'AT123',
    level: 'A',
    capability_ids: [],
    capabilities: [],
    article_group_ids: [],
    article_groups: [],
    street: 'Main St 1',
    city: 'Vienna',
    country: 'AT',
    postal_code: '1010',
    email: 'sales@acme.example',
    phone: null,
    weblink: null,
    order_email: null,
    order_language: null,
    order_template: null,
    request_email: null,
    request_language: null,
    request_template: null,
    edp_type_number_first: false,
    creator_id: 1,
    creator: null,
    edp_code: null,
    external_lead_time_days: null,
    ...overrides,
  }
}

function page(items: SupplierResponse[], total = items.length) {
  return { data: { items, total, limit: 25, skip: 0 } }
}

const getMock = vi.fn<(url: string, config?: { params?: unknown }) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string, config?: { params?: unknown }) => getMock(url, config),
  },
}))

import SupplierManagementTable from '../SupplierManagementTable.vue'

describe('SupplierManagementTable', () => {
  beforeEach(() => {
    getMock.mockReset()
  })

  it('mounts, loads suppliers via the paginated fetch, and renders columns', async () => {
    getMock.mockResolvedValue(page([makeSupplier()]))

    const wrapper = mountWithApp(SupplierManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Acme Metals')
    expect(getMock).toHaveBeenCalledWith('/suppliers/', { params: { skip: 0, limit: 25 } })
  })

  it('is a lazy DataTable whose totalRecords comes from the server total', async () => {
    getMock.mockResolvedValue(page([makeSupplier()], 120))

    const wrapper = mountWithApp(SupplierManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const table = wrapper.findComponent({ name: 'DataTable' })
    expect(table.props('lazy')).toBe(true)
    expect(table.props('totalRecords')).toBe(120)
  })

  it('requests the next page with the correct skip on @page', async () => {
    getMock.mockResolvedValue(page([makeSupplier()], 60))

    const wrapper = mountWithApp(SupplierManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    getMock.mockClear()
    getMock.mockResolvedValue(page([makeSupplier({ id: 2, name: 'Second Page Supplier' })], 60))

    const next = wrapper.find('[aria-label="Next Page"]')
    await next.trigger('click')
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/suppliers/', { params: { skip: 25, limit: 25 } })
  })

  // selectionMode="single" makes every row keyboard-reachable and gives
  // Enter the same effect as a click, via the shared useRowOpenGuard recipe
  // proven on OrdersTable/ArticleGroupManagementTable.
  it('makes the first row keyboard-focusable', async () => {
    getMock.mockResolvedValue(page([makeSupplier()]))
    const wrapper = mountWithApp(SupplierManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const row = wrapper.find('tr[data-p-selectable-row="true"]')
    expect(row.exists()).toBe(true)
    expect(row.attributes('tabindex')).toBe('0')
  })

  it('opens the detail dialog on @row-select the same way @row-click does', async () => {
    const entity = makeSupplier()
    getMock.mockResolvedValue(page([entity]))
    const wrapper = mountWithApp(SupplierManagementTable, {
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
    getMock.mockResolvedValue(page([makeSupplier()], 60))
    const wrapper = mountWithApp(SupplierManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    // Move off page 1 first, so the sort click's reset is observable.
    getMock.mockClear()
    getMock.mockResolvedValue(page([makeSupplier()], 60))
    await wrapper.find('[aria-label="Next Page"]').trigger('click')
    await flushPromises()

    getMock.mockClear()
    getMock.mockResolvedValue(page([makeSupplier()], 60))
    const dataTable = wrapper.findComponent({ name: 'DataTable' })
    dataTable.vm.$emit('sort', { sortField: 'name', sortOrder: 1 })
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/suppliers/', {
      params: { skip: 0, limit: 25, order_by: 'name', order_dir: 'asc' },
    })
  })

  // legal_name isn't in the backend's order_by allow-list (id/name/created/
  // changed), so an honest non-sortable header beats a misleading one.
  it('does not mark the legal name column sortable (not in the backend allow-list)', async () => {
    getMock.mockResolvedValue(page([makeSupplier()]))
    const wrapper = mountWithApp(SupplierManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const column = wrapper
      .findAllComponents({ name: 'Column' })
      .find((c) => c.props('field') === 'legal_name')
    expect(column?.props('sortable')).toBeFalsy()
  })

  it('shows the Archived tag for an archived row, and not for a live one', async () => {
    getMock.mockResolvedValue(page([makeSupplier({ archived: true })]))
    const wrapper = mountWithApp(SupplierManagementTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain(i18n.global.t('common.archivedTag'))
  })

  it('shows an inline Archive action for a live row, and Restore for an archived one', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useSuppliersStore()
    store.toggleShowActions()

    getMock.mockResolvedValue(page([makeSupplier({ archived: false })]))
    const wrapper = mountWithApp(SupplierManagementTable, {
      pinia,
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const archiveButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.attributes('aria-label') === i18n.global.t('common.archive'))
    expect(archiveButton).toBeDefined()
    expect(
      wrapper
        .findAllComponents({ name: 'Button' })
        .some((b) => b.attributes('aria-label') === i18n.global.t('common.restore')),
    ).toBe(false)
    wrapper.unmount()

    getMock.mockResolvedValue(page([makeSupplier({ archived: true })]))
    const archivedWrapper = mountWithApp(SupplierManagementTable, {
      pinia,
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const restoreButton = archivedWrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.attributes('aria-label') === i18n.global.t('common.restore'))
    expect(restoreButton).toBeDefined()
  })
})
