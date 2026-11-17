import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import type { PageResponse } from '@/core/api/types'
import { useCalculationsTableStores } from '../../stores/calculationsTableStores'
import type { CalculationListParams, CalculationSummaryResponse } from '../../types/calculation'

// The date cells load the user list for the actor's card; it stays empty
// here so the request never reaches the network.
vi.mock('@/core/api/users/getUserDirectory', () => ({
  getUserDirectory: async () => ({ items: [], total: 0, limit: 0, skip: 0 }),
}))

const getCalculations = vi.fn<(p: CalculationListParams) => Promise<PageResponse<CalculationSummaryResponse>>>()
vi.mock('../../api/getCalculations', () => ({
  getCalculations: (p: CalculationListParams) => getCalculations(p),
}))

import CalculationsList from '../CalculationsList.vue'
import CalculationsView from '../../views/CalculationsView.vue'
import { controlledDocumentFields } from '@/test-utils/controlledDocument'

function row(overrides: Partial<CalculationSummaryResponse>): CalculationSummaryResponse {
  return {
    ...controlledDocumentFields(),
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-10-08T10:00:00Z',
    changed: '2026-10-08T10:00:00Z',
    tool: 'fit_calculator',
    title: 'Bearing seat',
    note: null,
    results: { size: 25, hole: { code: 'H7' }, shaft: { code: 'g6' }, fit: { type: 'clearance' } },
    input_version: 1,
    engine_version: 1,
    project_id: null,
    project_number: null,
    product_id: null,
    product_number: null,
    product_device_id: null,
    product_device_name: null,
    creator_id: 1,
    creator_full_name: 'Tester',
    released_at: null,
    released_by_id: null,
    released_by_full_name: null,
    ...overrides,
  }
}

async function mount(component: typeof CalculationsList | typeof CalculationsView, props: Record<string, unknown> = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = { id: 1, permissions: ['write:calculations'], is_systemuser: false } as never
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/tools/:tab?/:calc?', name: 'Tools', component: { template: '<div />' } },
    ],
  })
  await router.push('/')
  const wrapper = mountWithApp(component, {
    pinia,
    props,
    global: { plugins: [router, ConfirmationService], directives: { tooltip: Tooltip } },
  })
  await flushPromises()
  return Object.assign(wrapper, { router })
}

function lastParams(): CalculationListParams | undefined {
  return getCalculations.mock.calls.at(-1)?.[0]
}

beforeEach(() => {
  vi.clearAllMocks()
  getCalculations.mockResolvedValue({
    items: [
      row({ id: 1, title: 'Bearing seat' }),
      row({
        id: 2,
        title: 'Spindle',
        project_id: 3,
        project_number: 'P-003',
        released_at: '2026-10-08T11:00:00Z',
        released_by_full_name: 'Tester',
      }),
    ],
    total: 60,
    limit: 25,
    skip: 0,
  })
})

describe('CalculationsList on a project', () => {
  it('loads the first page of the project as a plain table with the row actions', async () => {
    const wrapper = await mount(CalculationsList, { projectId: 3 })

    expect(getCalculations).toHaveBeenCalledWith({ skip: 0, limit: 25, project_id: 3 })
    expect(wrapper.text()).toContain('Bearing seat')
    expect(wrapper.text()).toContain('Ø25 H7/g6, Clearance fit')
    // The page around the tab offers New Calculation; the tab has no bars or filters.
    expect(wrapper.find('[data-testid="calc-new"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="calculations-controls"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="calc-filter-title"]').exists()).toBe(false)
    const firstCell = wrapper.get('[data-testid="calculations-table"] tbody tr td')
    expect(firstCell.find('[data-testid="calc-row-actions-1"]').exists()).toBe(true)
    // The owner is the project for every row.
    expect(wrapper.text()).not.toContain('Belongs to')
  })

  it('ignores the filters, sort and grouping of the view stores', async () => {
    const wrapper = await mount(CalculationsList, { projectId: 4 })
    const { view, filters } = useCalculationsTableStores('project')
    ;(filters.filters.status as { value: unknown }).value = 'released'
    view.setSort('title', 'asc')
    view.setGroupBy('status')
    await flushPromises()

    expect(getCalculations.mock.calls.length).toBeGreaterThan(1)
    expect(lastParams()).toEqual({ skip: 0, limit: 25, project_id: 4 })
    expect(wrapper.findAll('.group-header-label')).toHaveLength(0)
  })

  it('opens a calculation with a click anywhere on its row, but not from a row action', async () => {
    const wrapper = await mount(CalculationsList, { projectId: 3 })

    const firstRow = wrapper.get('[data-testid="calculations-table"] tbody tr')
    await firstRow.findAll('button').at(-1)?.trigger('click')
    await flushPromises()
    expect(wrapper.router.currentRoute.value.path).toBe('/')

    await firstRow.findAll('td').at(4)?.trigger('click')
    await flushPromises()
    expect(wrapper.router.currentRoute.value.path).toBe('/tools/fit-calculator/11111111-1111-1111-1111-111111111111')
  })

  it('shows revision, lock, tool version, invalid marking and release of each row', async () => {
    getCalculations.mockResolvedValue({
      items: [
        row({
          id: 1,
          engine_version: 0,
          locked_by_id: 2,
          locked_by_full_name: 'Jane Doe',
          lock_expires_at: new Date(Date.now() + 600_000).toISOString(),
        }),
        row({
          id: 2,
          released_at: '2026-10-08T11:00:00Z',
          released_by_full_name: 'Reviewer',
          invalid_at: '2026-10-09T08:00:00Z',
          invalid_reason: 'Wrong load case',
        }),
      ],
      total: 2,
      limit: 25,
      skip: 0,
    })
    const wrapper = await mount(CalculationsList, { projectId: 3 })

    expect(wrapper.get('[data-testid="calc-revision-1"]').text()).toMatch(/^Rev\. /)
    expect(wrapper.find('[data-testid="calc-locked-1"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="calc-locked-2"]').exists()).toBe(false)
    // The fit calculator is at engine version 1; the row was calculated with 0.
    expect(wrapper.find('[data-testid="calc-outdated-1"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="calc-outdated-2"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="calc-invalid-2"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="calc-released-2"]').text()).toContain('Reviewer')
  })

  it('opens a context menu on a row that leaves the document steps to the calculation page', async () => {
    const wrapper = await mount(CalculationsList, { projectId: 3 })
    const rows = wrapper.findAll('[data-testid="calculations-table"] tbody tr')

    await rows[1]!.trigger('contextmenu')
    await flushPromises()
    const item = (label: string) =>
      [...document.querySelectorAll<HTMLElement>('[data-testid="calc-row-menu"] li[role="menuitem"]')].find(
        (li) => li.textContent?.trim() === label,
      )
    // The second row is released: it is kept as a record and continues in a new revision.
    expect(item('Delete')?.getAttribute('aria-disabled')).toBe('true')
    expect(item('Edit')?.getAttribute('aria-disabled')).toBe('true')
    expect(item('New Revision')?.getAttribute('aria-disabled')).not.toBe('true')

    await rows[0]!.trigger('contextmenu')
    await flushPromises()
    expect(item('Delete')?.getAttribute('aria-disabled')).not.toBe('true')
    item('Edit')?.querySelector<HTMLElement>('a, [data-pc-section="itemlink"], div')?.click()
    await flushPromises()
    expect(wrapper.router.currentRoute.value.fullPath).toBe('/tools/fit-calculator/11111111-1111-1111-1111-111111111111?action=edit')
    wrapper.unmount()
  })
})

describe('CalculationsList on a product', () => {
  it('lists the calculations of the product and of its projects and shows what each belongs to', async () => {
    const wrapper = await mount(CalculationsList, { productId: 7, includeProductProjects: true })

    expect(getCalculations).toHaveBeenCalledWith({ skip: 0, limit: 25, related_product_id: 7 })
    expect(wrapper.text()).toContain('Belongs to')
    expect(wrapper.text()).toContain('Project P-003')
  })
})

describe('CalculationsView', () => {
  it('lists every visible calculation with the owner column and pages', async () => {
    const wrapper = await mount(CalculationsView)

    expect(getCalculations).toHaveBeenCalledWith({ skip: 0, limit: 25 })
    expect(wrapper.text()).toContain('Belongs to')
    expect(wrapper.text()).toContain('Project P-003')
    expect(wrapper.findComponent({ name: 'Paginator' }).exists()).toBe(true)
    expect(wrapper.find('[data-testid="calc-new"]').exists()).toBe(true)
  })

  it('sends the filters of the header row, the author and the sort to the server', async () => {
    const wrapper = await mount(CalculationsView)

    await wrapper.get('[data-testid="calc-filter-title"]').setValue('bear')
    await vi.waitFor(() => expect(lastParams()).toMatchObject({ search: 'bear', skip: 0 }), { timeout: 2000 })

    const { view, filters } = useCalculationsTableStores('page')
    ;(filters.filters.author as { value: unknown }).value = 'me'
    view.setSort('title', 'asc')
    await vi.waitFor(() =>
      expect(lastParams()).toMatchObject({ search: 'bear', mine: true, order_by: 'title', order_dir: 'asc' }),
    )

    filters.clearAll()
    await vi.waitFor(() => expect(lastParams()).toEqual({ skip: 0, limit: 25, order_by: 'title', order_dir: 'asc' }))
  })

  it('shows the row actions at the far left only when asked to', async () => {
    const wrapper = await mount(CalculationsView)
    expect(wrapper.find('[data-testid="calc-row-actions-1"]').exists()).toBe(false)

    useCalculationsTableStores('page').view.toggleShowActions()
    await flushPromises()

    const firstCell = wrapper.get('[data-testid="calculations-table"] tbody tr td')
    expect(firstCell.find('[data-testid="calc-row-actions-1"]').exists()).toBe(true)
  })

  it('groups the rows of the page by status', async () => {
    const wrapper = await mount(CalculationsView)

    useCalculationsTableStores('page').view.setGroupBy('status')
    await flushPromises()

    expect(wrapper.findAll('.group-header-label').map((h) => h.text())).toEqual(['Draft', 'Released'])
  })
})
