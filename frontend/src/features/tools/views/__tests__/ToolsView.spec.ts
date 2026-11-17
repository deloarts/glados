import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import ConfirmationService from 'openvue/confirmationservice'

import { asyncTabStub } from '@/test-utils/asyncTabStub'
import { mountWithApp } from '@/test-utils/mountWithApp'

// The tabs are lazy-loaded through asyncTab; mock them so this spec checks the
// tab shell, not the tools.
vi.mock('@/features/tools/components/FitCalculatorTab.vue', () => asyncTabStub('FitCalculatorTab', '<div>fit-calculator-stub</div>'))
vi.mock('@/features/tools/components/DriveSizingTab.vue', () => asyncTabStub('DriveSizingTab', '<div>drive-sizing-stub</div>'))
const getCalculationByPublicId = vi.fn<(id: string) => Promise<CalculationResponse>>()
vi.mock('@/features/tools/api/getCalculationByPublicId', () => ({
  getCalculationByPublicId: (id: string) => getCalculationByPublicId(id),
}))

import ToolsView from '../ToolsView.vue'
import type { CalculationResponse } from '../../types/calculation'
import { controlledDocumentFields } from '@/test-utils/controlledDocument'

const PUBLIC_ID = '0b5f8a62-3c1e-4d7a-9f20-6e8d4c2b1a90'

// jsdom does not implement ResizeObserver; OpenVue's TabList binds one.
vi.stubGlobal(
  'ResizeObserver',
  class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  },
)

async function mountAt(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/tools/:tab?/:calc?', name: 'Tools', component: ToolsView }],
  })
  router.push(path)
  await router.isReady()
  // The calculation bar above the tools asks for confirmations.
  const wrapper = mountWithApp(ToolsView, { global: { plugins: [router, ConfirmationService] } })
  return { router, wrapper }
}

describe('ToolsView', () => {
  it('opens the fit calculator tab by default', async () => {
    const { wrapper } = await mountAt('/tools')

    await vi.waitFor(
      () => expect(wrapper.findComponent({ name: 'FitCalculatorTab' }).exists()).toBe(true),
      { timeout: 2000, interval: 25 },
    )
    await flushPromises()

    expect(wrapper.text()).toContain('Fit calculator')
    wrapper.unmount()
  })

  it('falls back to the fit calculator for an unknown tab', async () => {
    const { wrapper } = await mountAt('/tools/unknown')

    await vi.waitFor(
      () => expect(wrapper.findComponent({ name: 'FitCalculatorTab' }).exists()).toBe(true),
      { timeout: 2000, interval: 25 },
    )
    wrapper.unmount()
  })

  it('opens a saved calculation named by its public id and shows it in the info bar', async () => {
    getCalculationByPublicId.mockResolvedValue({
      ...controlledDocumentFields(),
      id: 5,
      public_id: PUBLIC_ID,
      created: '2026-10-08T10:00:00Z',
      changed: '2026-10-08T10:00:00Z',
      tool: 'drive_sizing',
      title: 'Lift axis',
      note: null,
      inputs: { d: '25', hole: 'H7', shaft: 'g6' },
      results: {},
      input_version: 1,
      engine_version: 1,
      project_id: 3,
      project_number: 'P-003',
      product_id: null,
      product_number: null,
      product_device_id: null,
      product_device_name: null,
      creator_id: 1,
      creator_full_name: 'Tester',
      released_at: null,
      released_by_id: null,
      released_by_full_name: null,
      changes: [],
    })
    const { wrapper } = await mountAt(`/tools/drive-sizing/${PUBLIC_ID}`)

    await vi.waitFor(
      () => expect(wrapper.find('[data-testid="calc-title-display"]').exists()).toBe(true),
      { timeout: 2000, interval: 25 },
    )
    expect(getCalculationByPublicId).toHaveBeenCalledWith(PUBLIC_ID)
    expect(wrapper.text()).toContain('Lift axis')
    expect(wrapper.get('[data-testid="calc-association"]').text()).toBe('P-003')
    wrapper.unmount()
  })

  it('shows no calculation bars on a reference tool', async () => {
    const { wrapper } = await mountAt('/tools/fit-calculator')

    await vi.waitFor(
      () => expect(wrapper.findComponent({ name: 'FitCalculatorTab' }).exists()).toBe(true),
      { timeout: 2000, interval: 25 },
    )
    expect(wrapper.find('[data-testid="calc-not-saved"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="tool-calculation-controls"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('marks a calculation that is not saved in the info bar', async () => {
    const { wrapper } = await mountAt('/tools/drive-sizing')

    await vi.waitFor(
      () => expect(wrapper.find('[data-testid="calc-not-saved"]').exists()).toBe(true),
      { timeout: 2000, interval: 25 },
    )
    expect(wrapper.find('[data-testid="calc-not-saved"]').text()).toBe('Not saved')
    wrapper.unmount()
  })

  it('opens a tool from the route and leaves the reference tables to /tables', async () => {
    const { wrapper } = await mountAt('/tools/drive-sizing')

    await vi.waitFor(
      () => expect(wrapper.findComponent({ name: 'DriveSizingTab' }).exists()).toBe(true),
      { timeout: 2000, interval: 25 },
    )

    expect(wrapper.findComponent({ name: 'FitCalculatorTab' }).exists()).toBe(false)
    expect(wrapper.text()).not.toContain('General tolerances')
    expect(wrapper.text()).not.toContain('Threads')
    wrapper.unmount()
  })
})
