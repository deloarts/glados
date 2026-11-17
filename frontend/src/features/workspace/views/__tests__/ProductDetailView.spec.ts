import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h } from 'vue'
import { RouterView, type Router } from 'vue-router'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { RouteStub, makeTestRouter } from '@/test-utils/factories'
import { Permission } from '@/core/auth/permissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import type { UserResponse } from '@/core/types/userResponse'
import type { PageResponse } from '@/core/api/types'
import type { ProjectResponse } from '@/features/projects'
import type { ProductResponse } from '@/features/products'

// Generic fallback for anything not mocked below, such as usersStore.refresh().
vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
}))

const getProductsMock = vi.fn<(params: unknown) => Promise<PageResponse<ProductResponse>>>()
vi.mock('@/features/products/api/getProducts', () => ({
  getProducts: (params: unknown) => getProductsMock(params),
}))

const getProjectsMock = vi.fn<(params: unknown) => Promise<PageResponse<ProjectResponse>>>()
vi.mock('@/features/projects', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/features/projects')>()),
  getProjects: (params: unknown) => getProjectsMock(params),
}))

const getProductSummaryMock = vi.fn<(id: number) => Promise<unknown>>()
vi.mock('@/features/products/api/getProductSummary', () => ({
  getProductSummary: (id: number) => getProductSummaryMock(id),
}))

// The Devices tab loads through its own API; only its controls matter here.
vi.mock('@/features/product-devices', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/features/product-devices')>()),
  ProductDevicesTab: { name: 'ProductDevicesTab', template: '<div />' },
}))

import ProductDetailView from '../ProductDetailView.vue'

function makeProduct(overrides: Partial<ProductResponse> = {}): ProductResponse {
  return {
    edit_version: 0,
    id: 1,
    public_id: 'aaaaaaaa-0000-0000-0000-000000000001',
    product_number: 'PN-1',
    customer_id: null,
    customer: null,
    description: 'A widget',
    is_active: true,
    archived: false,
    designated_user_id: 1,
    created: '2026-01-01T00:00:00Z',
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

function makeProject(overrides: Partial<ProjectResponse> = {}): ProjectResponse {
  return {
    id: 7,
    public_id: 'dddddddd-0000-0000-0000-000000000007',
    project_number: 'PRJ-007',
    customer_id: null,
    customer: null,
    product_id: 1,
    product: null,
    description: null,
    status: 'active',
    designated_user_id: 1,
    created: '2026-01-01T00:00:00Z',
    changed: null,
    changed_by_id: null,
    changed_by: null,
    creator_id: 1,
    creator: null,
    production_time_budget: null,
    required_delivery_date_made: null,
    required_delivery_date_bought: null,
    edit_version: 0,
    actions: [],
    live_work: null,
    ...overrides,
  }
}

function page<T>(items: T[]): PageResponse<T> {
  return { items, total: items.length, limit: 500, skip: 0 }
}

function makeRouter(): Router {
  return makeTestRouter([
    {
      path: '/workspace/products/:id(\\d+)/:tab?',
      name: 'ProductDetail',
      component: ProductDetailView,
    },
    { path: '/workspace/products', component: RouteStub },
  ])
}

interface MountOptions {
  id?: string
  userId?: number
  permissions?: string[]
  storageEnabled?: boolean
}

// The view renders real OpenVue Tabs, whose TabList schedules a timer it
// never clears, so every wrapper is unmounted after each test.
const mounted: VueWrapper[] = []

async function mountView(options: MountOptions = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = {
    id: options.userId ?? 1,
    is_systemuser: false,
    permissions: options.permissions ?? [],
  } as unknown as UserResponse
  useHostStore().storageEnabled = options.storageEnabled ?? false

  const router = makeRouter()
  await router.push(`/workspace/products/${options.id ?? '1'}`)
  await router.isReady()

  // A RouterView renders the page, so a route change reuses the component
  // instance as it does in the app.
  const host = defineComponent({ render: () => h(RouterView) })
  const wrapper = mountWithApp(host, {
    pinia,
    global: {
      plugins: [router],
      directives: { tooltip: Tooltip },
      stubs: {
        ProductOverviewTab: true,
        ProductProjectsTab: true,
        ProductFilesTab: true,
        ProductFormDialog: true,
        CalculationsList: true,
        ChecklistsList: true,
        NewCalculationButton: true,
        NewChecklistButton: true,
        ProjectBomTab: true,
        ProjectOrdersTab: true,
        ProjectCostsTab: true,
      },
    },
  })
  mounted.push(wrapper)
  await flushPromises()
  await flushPromises()
  return { wrapper, router }
}

function tab(wrapper: VueWrapper, label: string) {
  return wrapper.findAll('[role="tab"]').find((t) => t.text() === label)!
}

function buttonLabelled(wrapper: VueWrapper, label: string) {
  return wrapper.findAll('button').find((b) => b.text().includes(label))
}

describe('ProductDetailView', () => {
  beforeEach(() => {
    getProductsMock.mockReset()
    getProductsMock.mockResolvedValue(page([makeProduct()]))
    getProjectsMock.mockReset()
    getProjectsMock.mockResolvedValue(page([makeProject()]))
    getProductSummaryMock.mockReset()
  })

  afterEach(() => {
    mounted.splice(0).forEach((wrapper) => wrapper.unmount())
  })

  it('shows the product identity in the info bar', async () => {
    getProductsMock.mockResolvedValue(
      page([
        makeProduct({
          product_number: 'PN-42',
          customer: { id: 3, name: 'ACME Corp' } as ProductResponse['customer'],
        }),
      ]),
    )

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('PN-42')
    expect(wrapper.text()).toContain('Active')
    expect(wrapper.text()).toContain('ACME Corp')
    expect(wrapper.text()).toContain('A widget')
  })

  it('loads the product and its projects together', async () => {
    await mountView({ id: '5' })

    expect(getProductsMock).toHaveBeenCalledWith({ id: 5, limit: 1 })
    expect(getProjectsMock).toHaveBeenCalledWith(
      expect.objectContaining({ product_id: 5, limit: 500 }),
    )
  })

  it('shows the overview, projects, bill of material, orders, costs, devices, sequences, calculations and checklists tabs', async () => {
    const { wrapper } = await mountView()

    const tabs = wrapper.findAll('[role="tab"]').map((tab) => tab.text())
    expect(tabs).toEqual([
      'Overview',
      'Projects',
      'Meeting Notes',
      'Bill of Material',
      'Orders',
      'Costs',
      'Devices',
      'Sequences',
      'Calculations',
      'Checklists',
    ])
  })

  it('adds the files tab when file storage is enabled', async () => {
    const { wrapper } = await mountView({ storageEnabled: true })

    const tabs = wrapper.findAll('[role="tab"]').map((tab) => tab.text())
    expect(tabs).toEqual([
      'Overview',
      'Projects',
      'Meeting Notes',
      'Bill of Material',
      'Orders',
      'Costs',
      'Files',
      'Devices',
      'Sequences',
      'Calculations',
      'Checklists',
    ])
  })

  it('loads the bill of material, orders and costs of all projects only when one of their tabs opens', async () => {
    const summary = { cost_by_supplier: [], demand_counts: {}, order_count: 3, total_delivered_cost: 0, total_ordered_cost: 0 }
    getProductSummaryMock.mockResolvedValue(summary)
    const { wrapper } = await mountView()
    expect(getProductSummaryMock).not.toHaveBeenCalled()

    await tab(wrapper, 'Costs').trigger('click')
    await flushPromises()
    expect(getProductSummaryMock).toHaveBeenCalledWith(1)
    expect(wrapper.findComponent({ name: 'ProjectCostsTab' }).props('summary')).toEqual(summary)

    await tab(wrapper, 'Orders').trigger('click')
    await flushPromises()
    expect(getProductSummaryMock).toHaveBeenCalledTimes(1)
    expect(wrapper.findComponent({ name: 'ProjectOrdersTab' }).props()).toMatchObject({
      projectIds: [7],
      costLabel: 'Product Cost',
    })

    await tab(wrapper, 'Bill of Material').trigger('click')
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ProjectBomTab' }).props('byProject')).toBe(true)
  })

  it('shows an error on those tabs when their data cannot be loaded', async () => {
    getProductSummaryMock.mockRejectedValue(new Error('offline'))
    const { wrapper } = await mountView()

    await tab(wrapper, 'Bill of Material').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('The bill of material, orders and costs could not be loaded.')
    expect(wrapper.findComponent({ name: 'ProjectBomTab' }).exists()).toBe(false)
  })

  it('shows the not-found screen when the product list comes back empty', async () => {
    getProductsMock.mockResolvedValue(page([]))

    const { wrapper } = await mountView({ id: '999' })

    expect(wrapper.text()).toContain('This product does not exist or has been deleted.')
  })

  it('shows the load-error screen when the product request throws', async () => {
    getProductsMock.mockRejectedValue(new Error('network down'))

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('The product could not be loaded.')
  })

  it('shows the load-error screen when the projects request throws', async () => {
    getProjectsMock.mockRejectedValue(new Error('network down'))

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('The product could not be loaded.')
  })

  it('navigates back to the products list', async () => {
    const { wrapper, router } = await mountView()

    const back = buttonLabelled(wrapper, 'Back to Products')
    expect(back).toBeTruthy()
    await back!.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/workspace/products')
  })

  it.each([
    {
      name: 'without permissions',
      userId: 1,
      permissions: [],
      enabled: false,
      reason: 'This needs the permission Write Projects.',
    },
    {
      name: 'with write:projects on another user\'s product',
      userId: 2,
      permissions: [Permission.WRITE_PROJECTS],
      enabled: false,
      reason: 'Only the designated user or a project manager edits this product.',
    },
    {
      name: 'with write:projects as the designated user',
      userId: 1,
      permissions: [Permission.WRITE_PROJECTS],
      enabled: true,
      reason: undefined,
    },
    {
      name: 'with manage:projects',
      userId: 2,
      permissions: [Permission.MANAGE_PROJECTS],
      enabled: true,
      reason: undefined,
    },
  ])('gates the edit button $name', async ({ userId, permissions, enabled, reason }) => {
    const { wrapper } = await mountView({ userId, permissions })

    const edit = wrapper.get('[data-testid="product-edit"]')
    expect(edit.attributes('disabled') === undefined).toBe(enabled)
    const span = edit.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
    expect(span?.$_ptooltipValue).toBe(reason)
  })

  it('offers Back to Products and Edit Product on the overview only', async () => {
    const { wrapper } = await mountView({ permissions: [Permission.MANAGE_PROJECTS] })
    expect(buttonLabelled(wrapper, 'Back to Products')).toBeTruthy()
    expect(buttonLabelled(wrapper, 'Edit Product')).toBeTruthy()

    await tab(wrapper, 'Devices').trigger('click')
    await flushPromises()
    expect(buttonLabelled(wrapper, 'Back to Products')).toBeFalsy()
    expect(buttonLabelled(wrapper, 'Edit Product')).toBeFalsy()

    // Costs has no actions, so the page shows no empty controls bar.
    await tab(wrapper, 'Costs').trigger('click')
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ControlsBar' }).exists()).toBe(false)
  })

  it('offers New Calculation and New Checklist only on their tabs', async () => {
    const { wrapper } = await mountView({
      permissions: [Permission.WRITE_CALCULATIONS, Permission.WRITE_CHECKLISTS],
    })
    const newCalculation = () => wrapper.findComponent({ name: 'NewCalculationButton' })
    const newChecklist = () => wrapper.findComponent({ name: 'NewChecklistButton' })
    expect(newCalculation().exists()).toBe(false)
    expect(newChecklist().exists()).toBe(false)

    await tab(wrapper, 'Calculations').trigger('click')
    await flushPromises()
    expect(newCalculation().props('owner')).toBe('product:1:PN-1')
    expect(newChecklist().exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'CalculationsList' }).props()).toMatchObject({
      productId: 1,
      includeProductProjects: true,
    })

    await tab(wrapper, 'Checklists').trigger('click')
    await flushPromises()
    expect(newCalculation().exists()).toBe(false)
    expect(newChecklist().props()).toMatchObject({ productId: 1, ownerLabel: 'PN-1' })
    expect(wrapper.findComponent({ name: 'ChecklistsList' }).props()).toMatchObject({
      productId: 1,
      includeProductProjects: true,
    })
  })

  it('puts the open tab into the URL and the overview on the bare product URL', async () => {
    const { wrapper, router } = await mountView({ permissions: [Permission.MANAGE_PROJECTS] })

    await tab(wrapper, 'Devices').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/workspace/products/1/devices')

    await tab(wrapper, 'Overview').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/workspace/products/1')
  })

  it('opens the tab the URL names', async () => {
    const { wrapper } = await mountView({ id: '1/devices' })
    expect(tab(wrapper, 'Devices').attributes('aria-selected')).toBe('true')
  })

  it('puts the device controls into the controls bar on the Devices tab', async () => {
    const { wrapper } = await mountView({ permissions: [Permission.MANAGE_PROJECTS] })
    const newDevice = () => wrapper.find('[data-testid="product-device-create"]')
    expect(newDevice().exists()).toBe(false)

    await tab(wrapper, 'Devices').trigger('click')
    await flushPromises()
    expect(newDevice().exists()).toBe(true)
    expect(wrapper.find('[data-testid="product-devices-overview"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="product-devices-archived"]').exists()).toBe(true)
  })

  it('shows New Calculation and New Checklist disabled with the missing permission without the write permissions', async () => {
    const { wrapper } = await mountView({ permissions: [Permission.MANAGE_PROJECTS] })

    await tab(wrapper, 'Calculations').trigger('click')
    await flushPromises()
    const calculation = wrapper.findComponent({ name: 'NewCalculationButton' })
    expect(calculation.props('disabled')).toBe(true)
    expect((calculation.element.parentElement as HTMLElement & { $_ptooltipValue?: string }).$_ptooltipValue).toBe(
      'This needs the permission Write Calculations.',
    )
    await tab(wrapper, 'Checklists').trigger('click')
    await flushPromises()
    const checklist = wrapper.findComponent({ name: 'NewChecklistButton' })
    expect(checklist.props('disabled')).toBe(true)
    expect((checklist.element.parentElement as HTMLElement & { $_ptooltipValue?: string }).$_ptooltipValue).toBe(
      'This needs the permission Write Checklists.',
    )
  })

  it('shows the saved product after an edit', async () => {
    const { wrapper } = await mountView({ permissions: [Permission.MANAGE_PROJECTS] })

    wrapper
      .findComponent({ name: 'ProductFormDialog' })
      .vm.$emit('saved', makeProduct({ product_number: 'PN-RENAMED' }))
    await flushPromises()

    expect(wrapper.text()).toContain('PN-RENAMED')
  })

  it('reloads when the route moves to another product', async () => {
    const { wrapper, router } = await mountView()
    getProductsMock.mockResolvedValue(page([makeProduct({ id: 2, product_number: 'PN-2' })]))

    await router.push('/workspace/products/2')
    await flushPromises()
    await flushPromises()

    expect(getProductsMock).toHaveBeenLastCalledWith({ id: 2, limit: 1 })
    expect(getProjectsMock).toHaveBeenLastCalledWith(expect.objectContaining({ product_id: 2 }))
    expect(wrapper.text()).toContain('PN-2')
  })
})
