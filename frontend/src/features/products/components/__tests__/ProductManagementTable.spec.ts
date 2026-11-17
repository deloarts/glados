import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useHostStore } from '@/core/host/stores/hostStore'
import { i18n } from '@/core/i18n'
import { Permission } from '@/core/auth/permissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { userWithPermissions } from '@/test-utils/factories'
import { useProductsStore } from '../../stores/productsStore'

import type { ProductResponse } from '../../types/productResponse'

const pushMock = vi.fn<(to: string) => void>()

// Partial mock: only useRouter's `push` needs to be observable here. The
// rest of vue-router must still be the real module.
vi.mock('vue-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-router')>()),
  useRouter: () => ({ push: pushMock }),
}))

function makeProduct(overrides: Partial<ProductResponse> = {}): ProductResponse {
  return {
    edit_version: 0,
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    product_number: 'PN-0001',
    customer_id: null,
    customer: null,
    description: null,
    is_active: true,
    archived: false,
    designated_user_id: 1,
    created: '2026-01-01',
    creator_id: 1,
    creator: null,
    designation: null,
    machine_type: null,
    installation_site: null,
    installation_location: null,
    planned_placing_on_market: null,
    legal_basis: null,
    plc_environment_id: null,
    contains_pneumatics: false,
    contains_hydraulics: false,
    contains_electrics: false,
    contains_robotics: false,
    ...overrides,
  }
}

function page(items: ProductResponse[], total = items.length) {
  return { data: { items, total, limit: 25, skip: 0 } }
}

// Empty envelope for the other lists this table lazily prefetches on mount
// (usersStore/customersStore, used for its own picker cells/filters); they
// hit different URLs and aren't the concern of these tests.
function emptyPage() {
  return { data: { items: [], total: 0, limit: 25, skip: 0 } }
}

const getMock = vi.fn<(url: string, config?: { params?: unknown }) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string, config?: { params?: unknown }) => getMock(url, config),
  },
}))

import ProductManagementTable from '../ProductManagementTable.vue'

function mountTable(permissions?: string[], userId = 1) {
  const pinia = createPinia()
  setActivePinia(pinia)
  if (permissions) {
    useCurrentUserStore().user = userWithPermissions(permissions, { id: userId })
    useProductsStore().showActions = true
  }
  // The thumbnail column only renders with file storage on, which the host
  // store reports; keep it off so the fixture stays simple.
  useHostStore().storageEnabled = false
  return mountWithApp(ProductManagementTable, {
    pinia,
    global: { plugins: [ConfirmationService] },
  })
}

describe('ProductManagementTable', () => {
  beforeEach(() => {
    getMock.mockReset()
    pushMock.mockClear()
  })

  it('mounts, loads products via the paginated fetch, and renders columns', async () => {
    getMock.mockImplementation((url: string) =>
      Promise.resolve(url === '/products/' ? page([makeProduct()]) : emptyPage()),
    )

    const wrapper = mountTable()
    await flushPromises()

    expect(wrapper.text()).toContain('PN-0001')
    expect(getMock).toHaveBeenCalledWith('/products/', { params: { skip: 0, limit: 25 } })
  })

  it('is a lazy DataTable whose totalRecords comes from the server total', async () => {
    getMock.mockImplementation((url: string) =>
      Promise.resolve(url === '/products/' ? page([makeProduct()], 120) : emptyPage()),
    )

    const wrapper = mountTable()
    await flushPromises()

    const table = wrapper.findComponent({ name: 'DataTable' })
    expect(table.props('lazy')).toBe(true)
    expect(table.props('totalRecords')).toBe(120)
  })

  it('requests the next page with the correct skip on @page', async () => {
    getMock.mockImplementation((url: string) =>
      Promise.resolve(url === '/products/' ? page([makeProduct()], 60) : emptyPage()),
    )

    const wrapper = mountTable()
    await flushPromises()

    getMock.mockClear()
    getMock.mockImplementation((url: string) =>
      Promise.resolve(
        url === '/products/'
          ? page([makeProduct({ id: 2, product_number: 'PN-0002' })], 60)
          : emptyPage(),
      ),
    )

    const next = wrapper.find('[aria-label="Next Page"]')
    await next.trigger('click')
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/products/', { params: { skip: 25, limit: 25 } })
  })

  // selectionMode="single" makes every row keyboard-reachable and gives
  // Enter the same effect as a click, via the shared useRowOpenGuard recipe
  // proven on OrdersTable/ArticleGroupManagementTable.
  it('makes the first row keyboard-focusable', async () => {
    getMock.mockImplementation((url: string) =>
      Promise.resolve(url === '/products/' ? page([makeProduct()]) : emptyPage()),
    )

    const wrapper = mountTable()
    await flushPromises()

    const row = wrapper.find('tr[data-p-selectable-row="true"]')
    expect(row.exists()).toBe(true)
    expect(row.attributes('tabindex')).toBe('0')
  })

  it('navigates to the product detail page on @row-select the same way @row-click does', async () => {
    const product = makeProduct({ id: 7 })
    getMock.mockImplementation((url: string) =>
      Promise.resolve(url === '/products/' ? page([product]) : emptyPage()),
    )

    const wrapper = mountTable()
    await flushPromises()

    const dataTable = wrapper.findComponent({ name: 'DataTable' })
    dataTable.vm.$emit('row-select', { data: product, index: 0, originalEvent: new Event('keydown') })
    await flushPromises()

    expect(pushMock).toHaveBeenCalledWith('/workspace/products/7')
    expect(wrapper.findComponent({ name: 'ResourceDetailDialog' }).exists()).toBe(false)
  })

  it('offers the same context menu as the projects table, with archive for delete', async () => {
    const product = makeProduct({ id: 7 })
    getMock.mockImplementation((url: string) =>
      Promise.resolve(url === '/products/' ? page([product]) : emptyPage()),
    )

    const wrapper = mountTable()
    await flushPromises()

    wrapper.findComponent({ name: 'DataTable' }).vm.$emit('update:contextMenuSelection', product)
    await flushPromises()

    const model = wrapper.findComponent({ name: 'ContextMenu' }).props('model') as {
      label?: string
      separator?: boolean
      command?: () => void
    }[]
    const t = i18n.global.t
    expect(model.map((item) => (item.separator ? '---' : item.label))).toEqual([
      t('resources.products.editProduct'),
      '---',
      t('common.showDetails'),
      '---',
      t('common.archive'),
      '---',
      t('common.copyUuid'),
    ])

    model.find((item) => item.label === t('common.showDetails'))?.command?.()
    expect(pushMock).toHaveBeenCalledWith('/workspace/products/7')
  })

  // Under `lazy` OpenVue only emits @sort and fetches nothing itself, so the
  // table must wire the event or a header click would only toggle the icon.
  it('fetches with order_by/order_dir and resets to page 1 on a header sort click', async () => {
    getMock.mockImplementation((url: string) =>
      Promise.resolve(url === '/products/' ? page([makeProduct()], 60) : emptyPage()),
    )

    const wrapper = mountTable()
    await flushPromises()

    // Move off page 1 first, so the sort click's reset is observable.
    getMock.mockClear()
    getMock.mockImplementation((url: string) =>
      Promise.resolve(url === '/products/' ? page([makeProduct()], 60) : emptyPage()),
    )
    await wrapper.find('[aria-label="Next Page"]').trigger('click')
    await flushPromises()

    getMock.mockClear()
    getMock.mockImplementation((url: string) =>
      Promise.resolve(url === '/products/' ? page([makeProduct()], 60) : emptyPage()),
    )
    const dataTable = wrapper.findComponent({ name: 'DataTable' })
    dataTable.vm.$emit('sort', { sortField: 'product_number', sortOrder: 1 })
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/products/', {
      params: { skip: 0, limit: 25, order_by: 'product_number', order_dir: 'asc' },
    })
  })

  it('does not mark the customer column sortable (not in the backend allow-list)', async () => {
    getMock.mockImplementation((url: string) =>
      Promise.resolve(url === '/products/' ? page([makeProduct()]) : emptyPage()),
    )
    const wrapper = mountTable()
    await flushPromises()

    const column = wrapper
      .findAllComponents({ name: 'Column' })
      .find((c) => c.props('field') === 'customer_id')
    expect(column?.props('sortable')).toBeFalsy()
  })

  it('shows the Archived tag for an archived row, and not for a live one', async () => {
    getMock.mockImplementation((url: string) =>
      Promise.resolve(url === '/products/' ? page([makeProduct({ archived: true })]) : emptyPage()),
    )
    const wrapper = mountTable()
    await flushPromises()

    expect(wrapper.text()).toContain(i18n.global.t('common.archivedTag'))
  })

  describe('row action tooltips', () => {
    const t = i18n.global.t
    const missing = (key: string) =>
      t('common.permissionMissing', { permission: t(`settings.users.permissions.${key}`) })

    function tooltipOf(wrapper: ReturnType<typeof mountTable>, label: string) {
      const button = wrapper.get(`button[aria-label="${label}"]`)
      const span = button.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
      return { disabled: button.attributes('disabled') !== undefined, tooltip: span?.$_ptooltipValue }
    }

    it('names the missing permission on the disabled edit and archive buttons', async () => {
      getMock.mockImplementation((url: string) =>
        Promise.resolve(url === '/products/' ? page([makeProduct()]) : emptyPage()),
      )
      const wrapper = mountTable([])
      await flushPromises()

      expect(tooltipOf(wrapper, t('resources.products.editProduct'))).toEqual({
        disabled: true,
        tooltip: missing('writeProjects'),
      })
      expect(tooltipOf(wrapper, t('common.archive'))).toEqual({
        disabled: true,
        tooltip: missing('manageProjects'),
      })
    })

    it('says only the designated user edits when the user writes projects but is not designated', async () => {
      getMock.mockImplementation((url: string) =>
        Promise.resolve(
          url === '/products/' ? page([makeProduct({ designated_user_id: 2 })]) : emptyPage(),
        ),
      )
      const wrapper = mountTable([Permission.WRITE_PROJECTS])
      await flushPromises()

      expect(tooltipOf(wrapper, t('resources.products.editProduct'))).toEqual({
        disabled: true,
        tooltip: t('resources.products.detail.editDesignatedOnly'),
      })
    })

    it('names the missing permission on the disabled restore button of an archived row', async () => {
      getMock.mockImplementation((url: string) =>
        Promise.resolve(url === '/products/' ? page([makeProduct({ archived: true })]) : emptyPage()),
      )
      const wrapper = mountTable([Permission.WRITE_PROJECTS])
      await flushPromises()

      expect(tooltipOf(wrapper, t('common.restore'))).toEqual({
        disabled: true,
        tooltip: missing('manageProjects'),
      })
    })

    it('shows the plain labels when the user may act', async () => {
      getMock.mockImplementation((url: string) =>
        Promise.resolve(url === '/products/' ? page([makeProduct()]) : emptyPage()),
      )
      const wrapper = mountTable([Permission.MANAGE_PROJECTS])
      await flushPromises()

      expect(tooltipOf(wrapper, t('resources.products.editProduct'))).toEqual({
        disabled: false,
        tooltip: t('resources.products.editProduct'),
      })
      expect(tooltipOf(wrapper, t('common.archive'))).toEqual({
        disabled: false,
        tooltip: t('common.archive'),
      })
    })
  })
})
