import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import type { ProjectResponse, ProjectSummaryResponse } from '@/features/projects'

const getCalculationsMock = vi.fn<(params: unknown) => Promise<{ total: number }>>()
const getChecklistsMock = vi.fn<(params: { verdict?: string }) => Promise<{ total: number }>>()
vi.mock('@/features/tools', () => ({ getCalculations: (params: unknown) => getCalculationsMock(params) }))
vi.mock('@/features/checklists', () => ({
  getChecklists: (params: { verdict?: string }) => getChecklistsMock(params),
}))

import ProjectOverviewTab from '../ProjectOverviewTab.vue'

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

function makeSummary(overrides: Partial<ProjectSummaryResponse> = {}): ProjectSummaryResponse {
  return {
    cost_by_supplier: [],
    demand_counts: {},
    order_count: 0,
    total_delivered_cost: 0,
    total_ordered_cost: 0,
    ...overrides,
  }
}

function mountTab(project: ProjectResponse, summary: ProjectSummaryResponse | null = makeSummary(), bomCount = 0) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/workspace/products/:id', name: 'ProductDetail', component: { template: '<div />' } },
    ],
  })
  return mountWithApp(ProjectOverviewTab, {
    pinia,
    props: { project, summary, bomCount },
    global: { plugins: [router], directives: { tooltip: Tooltip } },
  })
}

function count(wrapper: ReturnType<typeof mountTab>, row: string): string {
  return wrapper.get(`[data-testid="project-related-${row}"] [data-testid="related-count"]`).text()
}

describe('ProjectOverviewTab', () => {
  beforeEach(() => {
    getCalculationsMock.mockReset()
    getCalculationsMock.mockResolvedValue({ total: 0 })
    getChecklistsMock.mockReset()
    getChecklistsMock.mockResolvedValue({ total: 0 })
  })

  it('shows the project details, the description first, and links the product', () => {
    const wrapper = mountTab(
      makeProject({
        description: 'Line 2 retrofit',
        status: 'on_hold',
        customer: { id: 3, name: 'ACME Corp' } as ProjectResponse['customer'],
        product_id: 4,
        product: { id: 4, product_number: 'PN-4' } as ProjectResponse['product'],
      }),
    )

    expect(wrapper.findAll('dt').map((dt) => dt.text())[0]).toBe('Description')
    expect(wrapper.text()).toContain('Line 2 retrofit')
    expect(wrapper.text()).toContain('On Hold')
    expect(wrapper.text()).toContain('ACME Corp')
    expect(wrapper.get('[data-testid="project-product-link"]').attributes('href')).toBe('/workspace/products/4')
  })

  it('shows the procurement figures and tags only the demand statuses some demand has', () => {
    const wrapper = mountTab(
      makeProject({ production_time_budget: 480 }),
      makeSummary({ demand_counts: { open: 3, ordered: 2, canceled: 0 } }),
    )

    expect(wrapper.get('[data-testid="project-demands-open"]').text()).toBe('3 Open')
    expect(wrapper.get('[data-testid="project-demands-ordered"]').text()).toBe('2 Ordered')
    expect(wrapper.find('[data-testid="project-demands-canceled"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="project-procurement"]').text()).toContain('480 min')
  })

  it('counts the bill of material, orders, calculations and checklists of the project', async () => {
    getCalculationsMock.mockResolvedValue({ total: 4 })
    getChecklistsMock.mockImplementation(async (params) => ({ total: params.verdict === 'failed' ? 2 : 5 }))
    const wrapper = mountTab(makeProject(), makeSummary({ order_count: 6 }), 12)
    await flushPromises()

    expect(getCalculationsMock).toHaveBeenCalledWith({ project_id: 7, limit: 1 })
    expect(getChecklistsMock).toHaveBeenCalledWith({ project_id: 7, verdict: 'failed', limit: 1 })
    expect(count(wrapper, 'bom')).toBe('12')
    expect(count(wrapper, 'orders')).toBe('6')
    expect(count(wrapper, 'calculations')).toBe('4')
    expect(count(wrapper, 'checklists')).toBe('5')
    expect(wrapper.get('[data-testid="project-checklists-failed"]').text()).toBe('2 with findings')
  })

  it('shows empty figures while the summary is missing', () => {
    const wrapper = mountTab(makeProject(), null)

    expect(count(wrapper, 'orders')).not.toMatch(/\d/)
    expect(wrapper.get('[data-testid="project-total-ordered"]').text()).not.toMatch(/\d/)
  })

  it('opens the tab of a related row', async () => {
    const wrapper = mountTab(makeProject())

    for (const row of ['bom', 'orders', 'calculations', 'checklists']) {
      await wrapper.get(`[data-testid="project-related-${row}"]`).trigger('click')
    }

    expect(wrapper.emitted('openTab')).toEqual([['bom'], ['orders'], ['calculations'], ['checklists']])
  })
})
