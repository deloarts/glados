import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import type { PageResponse } from '@/core/api/types'
import type { CalculationListParams, CalculationSummaryResponse } from '../../types/calculation'

const getCalculations = vi.fn<(p: CalculationListParams) => Promise<PageResponse<CalculationSummaryResponse>>>()
vi.mock('../../api/getCalculations', () => ({
  getCalculations: (p: CalculationListParams) => getCalculations(p),
}))

vi.mock('@/core/api/projects/searchProjects', () => ({
  searchProjects: vi.fn<() => Promise<{ items: never[]; total: number; limit: number; skip: number }>>(
    async () => ({ items: [], total: 0, limit: 50, skip: 0 }),
  ),
}))
vi.mock('@/features/products', () => ({
  useProductsStore: () => ({
    items: [{ id: 4, product_number: 'PR-4', description: 'Press line', archived: false }],
    loading: false,
    refresh: vi.fn<() => Promise<void>>(),
  }),
}))

import LoadCalculationTable from '../LoadCalculationTable.vue'
import { controlledDocumentFields } from '@/test-utils/controlledDocument'

function row(id: number, title: string): CalculationSummaryResponse {
  return {
    ...controlledDocumentFields(),
    id,
    public_id: `00000000-0000-4000-8000-00000000000${id}`,
    created: '2026-10-09T08:00:00Z',
    changed: '2026-10-09T08:00:00Z',
    tool: 'drive_sizing',
    title,
    note: null,
    results: {},
    input_version: 1,
    engine_version: 1,
    project_id: null,
    project_number: null,
    product_id: 4,
    product_number: 'PR-4',
    product_device_id: null,
    product_device_name: null,
    creator_id: 1,
    creator_full_name: 'Tester',
    released_at: null,
    released_by_id: null,
    released_by_full_name: null,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.useRealTimers()
  getCalculations.mockResolvedValue({ items: [row(1, 'Lift axis')], total: 40, limit: 25, skip: 0 })
})

describe('LoadCalculationTable', () => {
  it('loads the first page of the current tool only', async () => {
    const wrapper = mountWithApp(LoadCalculationTable, { props: { tool: 'drive_sizing' } })
    await flushPromises()

    expect(getCalculations).toHaveBeenCalledWith({ tool: 'drive_sizing', skip: 0, limit: 25 })
    expect(wrapper.text()).toContain('Lift axis')
    expect(wrapper.text()).toContain('Product PR-4')
    wrapper.unmount()
  })

  it('searches on the server and starts again at the first page', async () => {
    vi.useFakeTimers()
    const wrapper = mountWithApp(LoadCalculationTable, { props: { tool: 'drive_sizing' } })
    await flushPromises()

    await wrapper.get('[data-testid="calc-load-search"]').setValue('lift')
    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()

    expect(getCalculations).toHaveBeenLastCalledWith({
      tool: 'drive_sizing',
      skip: 0,
      limit: 25,
      search: 'lift',
    })
    wrapper.unmount()
  })

  it('filters by status and owner kind on the server', async () => {
    const wrapper = mountWithApp(LoadCalculationTable, { props: { tool: 'drive_sizing' } })
    await flushPromises()

    const selects = wrapper.findAllComponents({ name: 'Select' })
    const status = selects.find((c) => c.attributes('data-testid') === 'calc-load-status')
    const owner = selects.find((c) => c.attributes('data-testid') === 'calc-load-owner')
    status?.vm.$emit('update:modelValue', 'released')
    await flushPromises()
    expect(getCalculations).toHaveBeenLastCalledWith({
      tool: 'drive_sizing',
      skip: 0,
      limit: 25,
      released: true,
    })

    owner?.vm.$emit('update:modelValue', 'personal')
    await flushPromises()
    expect(getCalculations).toHaveBeenLastCalledWith({
      tool: 'drive_sizing',
      skip: 0,
      limit: 25,
      owner: 'personal',
      released: true,
    })
    wrapper.unmount()
  })

  it('hands the chosen calculation on', async () => {
    const wrapper = mountWithApp(LoadCalculationTable, { props: { tool: 'drive_sizing' } })
    await flushPromises()

    await wrapper.get('[data-testid="calc-load-row-1"]').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('select')?.[0]?.[0]).toMatchObject({ id: 1, title: 'Lift axis' })
    wrapper.unmount()
  })
})
