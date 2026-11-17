import { describe, it, expect } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'
import CatalogueItemLotsCard from '../CatalogueItemLotsCard.vue'

import type { LotSummaryResponse } from '@/features/production'

function lot(overrides: Partial<LotSummaryResponse> = {}): LotSummaryResponse {
  return {
    id: 1,
    lot_number: 'L-2026-001',
    status: 'in_progress',
    quantity: 10,
    quantity_completed: 4,
    project_number: 'P-100',
    required_delivery_date: '2026-04-01',
    created: '2026-03-01',
    ...overrides,
  } as LotSummaryResponse
}

interface Props {
  lots: LotSummaryResponse[]
  loading: boolean
  error: boolean
  truncated: boolean
  limit: number
}

function mountCard(props: Partial<Props> = {}) {
  return mountWithApp(CatalogueItemLotsCard, {
    props: { lots: [], loading: false, error: false, truncated: false, limit: 200, ...props },
  })
}

describe('CatalogueItemLotsCard', () => {
  it('shows the empty state when there are no lots', () => {
    expect(mountCard().text()).toContain('No lots for this item.')
  })

  it('shows a loading spinner only while there are no lots yet', () => {
    expect(mountCard({ loading: true }).find('.loading-state').exists()).toBe(true)
    expect(mountCard({ loading: true, lots: [lot()] }).find('.loading-state').exists()).toBe(false)
  })

  it('shows the section error state', () => {
    expect(mountCard({ error: true }).text()).toContain('Could not load this section.')
  })

  it('shows the truncation notice with the limit', () => {
    expect(mountCard({ lots: [lot()], truncated: true, limit: 200 }).text()).toContain(
      'Showing the first 200 entries only.',
    )
  })

  it('renders a row per lot with number, quantity and project', () => {
    const wrapper = mountCard({ lots: [lot()] })
    expect(wrapper.text()).toContain('L-2026-001')
    expect(wrapper.text()).toContain('4 / 10')
    expect(wrapper.text()).toContain('P-100')
  })

  it('emits open-lot with the lot id on row click', async () => {
    const wrapper = mountCard({ lots: [lot({ id: 9 })] })
    await wrapper.find('tbody tr').trigger('click')
    expect(wrapper.emitted('open-lot')).toEqual([[9]])
  })
})
