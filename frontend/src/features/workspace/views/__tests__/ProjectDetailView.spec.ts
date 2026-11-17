import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { RouteStub, makeTestRouter } from '@/test-utils/factories'
import type { ProjectResponse } from '@/features/projects'

// Generic fallback for anything not mocked below (e.g. usersStore.refresh()).
vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
}))

const getProjectsMock = vi.fn<() => Promise<{ items: ProjectResponse[]; total: number }>>()
vi.mock('@/features/projects/api/getProjects', () => ({
  getProjects: () => getProjectsMock(),
}))

vi.mock('@/features/projects/api/getProjectSummary', () => ({
  getProjectSummary: vi.fn<() => Promise<unknown>>().mockResolvedValue({
    total_ordered_cost: 0,
    total_delivered_cost: 0,
    order_count: 0,
    cost_by_supplier: [],
    demand_counts: {},
  }),
}))

vi.mock('@/features/bought-items', () => ({
  getDemands: vi.fn<() => Promise<unknown>>().mockResolvedValue({ items: [], total: 0 }),
}))
vi.mock('@/features/made-items', () => ({
  getMadeItemDemands: vi.fn<() => Promise<unknown>>().mockResolvedValue({ items: [], total: 0 }),
}))
vi.mock('@/features/source-items', () => ({
  getSourceItemDemands: vi.fn<() => Promise<unknown>>().mockResolvedValue({ items: [], total: 0 }),
}))
vi.mock('@/features/orders', () => ({
  getOrders: vi.fn<() => Promise<unknown>>().mockResolvedValue({ items: [], total: 0 }),
}))

let hasPermissionMock: (permission: string) => boolean = () => true
vi.mock('@/core/composables/usePermissions', () => ({
  usePermissions: () => ({ hasPermission: (...args: unknown[]) => hasPermissionMock(...(args as [string])) }),
}))

import ProjectDetailView from '../ProjectDetailView.vue'

vi.stubGlobal(
  'ResizeObserver',
  class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  },
)

function makeProject(overrides: Partial<ProjectResponse> = {}): ProjectResponse {
  return {
    id: 7,
    public_id: 'dddddddd-0000-0000-0000-000000000007',
    project_number: 'PRJ-007',
    customer_id: null,
    customer: null,
    product_id: null,
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

function makeRouter() {
  return makeTestRouter([
    { path: '/workspace/projects/:id/:tab?', name: 'ProjectDetail', component: ProjectDetailView },
    { path: '/workspace/projects', component: RouteStub },
  ])
}

// Tracks every wrapper `mountView()` produces so `afterEach` below can
// unmount them all, since some tests (e.g. "gates the edit button on canEdit")
// call `mountView()` twice in one `it`.
const mountedWrappers: ReturnType<typeof mount>[] = []

async function mountView() {
  const router = makeRouter()
  await router.push('/workspace/projects/7')
  await router.isReady()

  const wrapper = mountWithApp(ProjectDetailView, {
    global: {
      plugins: [router],
      stubs: {
        ProjectOverviewTab: true,
        ProjectBomTab: true,
        ProjectOrdersTab: true,
        ProjectCostsTab: true,
        ProjectFormDialog: true,
        CalculationsList: true,
        ChecklistsList: true,
        NewCalculationButton: true,
        NewChecklistButton: true,
      },
    },
  })
  mountedWrappers.push(wrapper)
  await flushPromises()
  await flushPromises()
  return { wrapper, router }
}

describe('ProjectDetailView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getProjectsMock.mockReset()
    hasPermissionMock = () => true
  })

  afterEach(() => {
    // The view renders real OpenVue Tabs/TabList (only the tab-content
    // components above are stubbed), and TabList's `mounted()` hook
    // schedules an inkbar-position `setTimeout` that it never clears on
    // unmount. Leaving the wrapper mounted lets that timer fire later
    // against this file's already-torn-down jsdom environment, throwing an
    // unhandled `ReferenceError: HTMLElement is not defined` that surfaces
    // against whatever spec happens to be running when it lands in a
    // full-suite run, reproduced via `npx vitest run`. Unmounting here
    // matches the convention already used by every other spec that mounts
    // real Tabs/TabList (AccountView, ResourcesView, WorkspaceView,
    // ProcurementView, CatalogueView, HandbookLayout): once unmounted, Vue
    // nulls the component's template refs, so the stray timer's callback
    // becomes a no-op instead of touching detached DOM.
    mountedWrappers.splice(0).forEach((wrapper) => wrapper.unmount())
  })

  it('renders inside PageLayout and shows the project identity in the info bar', async () => {
    getProjectsMock.mockResolvedValue({
      items: [makeProject({ customer: { id: 1, name: 'ACME Corp' } as never, description: 'A widget line' })],
      total: 1,
    })

    const { wrapper } = await mountView()

    expect(wrapper.findComponent({ name: 'PageLayout' }).exists()).toBe(true)
    expect(wrapper.text()).toContain('PRJ-007')
    expect(wrapper.text()).toContain('ACME Corp')
    expect(wrapper.text()).toContain('A widget line')
    // The tab strip (the view's main content) still renders under PageLayout.
    expect(wrapper.text()).toContain('Bill of Material')
  })

  it('routes back to the projects list', async () => {
    getProjectsMock.mockResolvedValue({ items: [makeProject()], total: 1 })

    const { wrapper, router } = await mountView()

    const back = wrapper.findAll('button').find((b) => b.text().includes('Back to Projects'))
    expect(back).toBeTruthy()
    await back!.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/workspace/projects')
  })

  it('shows the edit button disabled without the right, enabled with it', async () => {
    getProjectsMock.mockResolvedValue({ items: [makeProject()], total: 1 })
    const editButton = (wrapper: VueWrapper) =>
      wrapper.find<HTMLButtonElement>('[data-testid="project-edit"]')

    hasPermissionMock = () => false
    const { wrapper: withoutPermission } = await mountView()
    expect(editButton(withoutPermission).exists()).toBe(true)
    expect(editButton(withoutPermission).element.disabled).toBe(true)

    hasPermissionMock = () => true
    const { wrapper: withPermission } = await mountView()
    expect(editButton(withPermission).element.disabled).toBe(false)
  })

  it('offers New Calculation on its tab and no New Checklist, as checklists belong to products', async () => {
    getProjectsMock.mockResolvedValue({ items: [makeProject()], total: 1 })
    const { wrapper } = await mountView()
    const tab = (label: string) => wrapper.findAll('[role="tab"]').find((t) => t.text() === label)!
    const newCalculation = () => wrapper.findComponent({ name: 'NewCalculationButton' })
    const newChecklist = () => wrapper.findComponent({ name: 'NewChecklistButton' })
    expect(newCalculation().exists()).toBe(false)
    expect(newChecklist().exists()).toBe(false)

    await tab('Calculations').trigger('click')
    await flushPromises()
    expect(newCalculation().props('owner')).toBe('project:7:PRJ-007')
    expect(newChecklist().exists()).toBe(false)

    await tab('Checklists').trigger('click')
    await flushPromises()
    expect(newCalculation().exists()).toBe(false)
    expect(newChecklist().exists()).toBe(false)
  })

  it('shows New Calculation disabled with the missing permission without write:calculations', async () => {
    getProjectsMock.mockResolvedValue({ items: [makeProject()], total: 1 })
    hasPermissionMock = (permission: string) => permission !== 'write:calculations'
    const { wrapper } = await mountView()
    const tab = (label: string) => wrapper.findAll('[role="tab"]').find((t) => t.text() === label)!

    await tab('Calculations').trigger('click')
    await flushPromises()
    const newCalculation = wrapper.findComponent({ name: 'NewCalculationButton' })
    expect(newCalculation.props('disabled')).toBe(true)
    const span = newCalculation.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
    expect(span?.$_ptooltipValue).toBe('This needs the permission Write Calculations.')
  })

  it('offers Back to Projects and Edit Project on the overview only', async () => {
    getProjectsMock.mockResolvedValue({ items: [makeProject()], total: 1 })
    hasPermissionMock = () => true
    const { wrapper } = await mountView()
    const labelled = (label: string) => wrapper.findAll('button').some((b) => b.text().includes(label))
    expect(labelled('Back to Projects')).toBe(true)
    expect(labelled('Edit Project')).toBe(true)

    await wrapper.findAll('[role="tab"]').find((t) => t.text() === 'Costs')!.trigger('click')
    await flushPromises()
    expect(labelled('Back to Projects')).toBe(false)
    expect(labelled('Edit Project')).toBe(false)
    // Costs has no actions, so the page shows no empty controls bar.
    expect(wrapper.findComponent({ name: 'ControlsBar' }).exists()).toBe(false)
  })

  it('puts the open tab into the URL and the overview on the bare project URL', async () => {
    getProjectsMock.mockResolvedValue({ items: [makeProject()], total: 1 })
    const { wrapper, router } = await mountView()
    const tab = (label: string) => wrapper.findAll('[role="tab"]').find((t) => t.text() === label)!

    await tab('Costs').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/workspace/projects/7/costs')

    await tab('Overview').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/workspace/projects/7')
  })

  it('shows the not-found state when the project does not exist', async () => {
    getProjectsMock.mockResolvedValue({ items: [], total: 0 })

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('Project not found.')
  })

  it('shows the load-error state when a request fails', async () => {
    getProjectsMock.mockRejectedValue(new Error('network error'))

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('Failed to load project data.')
  })
})
