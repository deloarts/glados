import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import type { ProjectResponse } from '@/features/projects'
import type { ProductResponse } from '@/features/products'

const getCalculationsMock = vi.fn<(params: unknown) => Promise<{ total: number }>>()
const getChecklistsMock = vi.fn<(params: { verdict?: string }) => Promise<{ total: number }>>()
vi.mock('@/features/tools', () => ({ getCalculations: (params: unknown) => getCalculationsMock(params) }))
vi.mock('@/features/checklists', () => ({
  getChecklists: (params: { verdict?: string }) => getChecklistsMock(params),
}))
getCalculationsMock.mockResolvedValue({ total: 0 })
getChecklistsMock.mockResolvedValue({ total: 0 })

import ProductOverviewTab from '../ProductOverviewTab.vue'

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

function makeProject(id: number, status: ProjectResponse['status']): ProjectResponse {
  return {
    id,
    public_id: `dddddddd-0000-0000-0000-00000000000${id}`,
    project_number: `PRJ-00${id}`,
    customer_id: null,
    customer: null,
    product_id: 1,
    product: null,
    description: null,
    status,
    designated_user_id: 1,
    created: '2026-01-01T00:00:00Z',
    changed: null,
    changed_by: null,
    changed_by_id: null,
    creator_id: 1,
    creator: null,
    production_time_budget: null,
    required_delivery_date_made: null,
    required_delivery_date_bought: null,
    edit_version: 0,
    actions: [],
    live_work: null,
  }
}

function mountTab(product: ProductResponse, projects: ProjectResponse[] = []) {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mountWithApp(ProductOverviewTab, {
    pinia,
    props: { product, projects },
    global: { directives: { tooltip: Tooltip } },
  })
}

function count(wrapper: ReturnType<typeof mountTab>, row: string): string {
  return wrapper.get(`[data-testid="product-related-${row}"] [data-testid="related-count"]`).text()
}

describe('ProductOverviewTab', () => {
  it('shows the product details, the description first', () => {
    const wrapper = mountTab(
      makeProduct({
        description: 'Conveyor module',
        customer: { id: 3, name: 'ACME Corp' } as ProductResponse['customer'],
      }),
    )

    const labels = wrapper.findAll('dt').map((dt) => dt.text())
    expect(labels[0]).toBe('Description')
    expect(wrapper.text()).toContain('Conveyor module')
    expect(wrapper.text()).toContain('ACME Corp')
  })

  it('shows the machine data and warns about the Directive after the switch', () => {
    const wrapper = mountTab(
      makeProduct({
        designation: 'Press 12',
        installation_location: 'Hall 3',
        planned_placing_on_market: '2027-03-01',
        legal_basis: 'directive',
        plc_environment_id: null,
        contains_pneumatics: false,
        contains_hydraulics: false,
        contains_electrics: false,
        contains_robotics: false,
      }),
    )

    expect(wrapper.get('[data-testid="product-machine-designation"]').text()).toContain('Press 12')
    expect(wrapper.get('[data-testid="product-machine-installation-location"]').text()).toContain('Hall 3')
    expect(wrapper.get('[data-testid="product-machine-legal-basis"]').text()).toContain('Directive 2006/42/EC')
    expect(wrapper.find('[data-testid="product-legal-basis-warning"]').exists()).toBe(true)
  })

  it('does not warn about the Regulation chosen ahead of the switch', () => {
    const wrapper = mountTab(makeProduct({ planned_placing_on_market: '2026-11-01', legal_basis: 'regulation' }))
    expect(wrapper.find('[data-testid="product-legal-basis-warning"]').exists()).toBe(false)
  })

  it('counts the product\'s projects and tags only the statuses some project has', () => {
    const wrapper = mountTab(makeProduct(), [
      makeProject(1, 'active'),
      makeProject(2, 'active'),
      makeProject(3, 'on_hold'),
      makeProject(4, 'completed'),
    ])

    expect(count(wrapper, 'projects')).toBe('4')
    expect(wrapper.get('[data-testid="product-projects-active"]').text()).toBe('2 Active')
    expect(wrapper.get('[data-testid="product-projects-on_hold"]').text()).toContain('1')
    expect(wrapper.get('[data-testid="product-projects-completed"]').text()).toContain('1')
    expect(wrapper.find('[data-testid="product-projects-archived"]').exists()).toBe(false)
  })

  it('counts the calculations and checklists of the product and its projects', async () => {
    getCalculationsMock.mockResolvedValueOnce({ total: 4 })
    getChecklistsMock.mockImplementation(async (params) => ({ total: params.verdict === 'failed' ? 1 : 3 }))
    const wrapper = mountTab(makeProduct({ id: 5 }))
    await flushPromises()

    expect(getCalculationsMock).toHaveBeenCalledWith({ related_product_id: 5, limit: 1 })
    expect(getChecklistsMock).toHaveBeenCalledWith({ related_product_id: 5, limit: 1 })
    expect(count(wrapper, 'calculations')).toBe('4')
    expect(count(wrapper, 'checklists')).toBe('3')
    expect(wrapper.get('[data-testid="product-checklists-failed"]').text()).toBe('1 with findings')
  })

  it('leaves out the findings tag when no checklist has findings', async () => {
    getChecklistsMock.mockResolvedValue({ total: 0 })
    const wrapper = mountTab(makeProduct())
    await flushPromises()
    expect(wrapper.find('[data-testid="product-checklists-failed"]').exists()).toBe(false)
  })

  it('shows an empty count when one cannot be loaded', async () => {
    getCalculationsMock.mockRejectedValueOnce(new Error('offline'))
    const wrapper = mountTab(makeProduct())
    await flushPromises()
    expect(count(wrapper, 'calculations')).not.toMatch(/\d/)
  })

  it('opens the tab of a related row', async () => {
    const wrapper = mountTab(makeProduct())

    await wrapper.get('[data-testid="product-related-projects"]').trigger('click')
    await wrapper.get('[data-testid="product-related-calculations"]').trigger('click')
    await wrapper.get('[data-testid="product-related-checklists"]').trigger('click')

    expect(wrapper.emitted('openTab')).toEqual([['projects'], ['calculations'], ['checklists']])
  })
})
