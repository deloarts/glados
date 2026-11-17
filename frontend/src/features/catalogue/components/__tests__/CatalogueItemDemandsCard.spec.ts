import { describe, it, expect } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'
import CatalogueItemDemandsCard from '../CatalogueItemDemandsCard.vue'

import type { CatalogueItemKind, ItemDemandRow } from '../../types/itemDetail'

interface Props {
  kind: CatalogueItemKind
  rows: ItemDemandRow[]
  loading: boolean
  error: boolean
  truncated: boolean
  limit: number
  extraLabel?: string
}

function row(overrides: Partial<ItemDemandRow> = {}): ItemDemandRow {
  return {
    id: 1,
    status: 'open',
    quantity: 5,
    unit: 'PCS',
    highPriority: false,
    projectNumber: 'P-100',
    projectCustomer: 'ACME',
    desiredDeliveryDate: '2026-04-01',
    created: '2026-03-01',
    creatorName: 'Jane Doe',
    ...overrides,
  }
}

function mountCard(props: Partial<Props> = {}) {
  return mountWithApp(CatalogueItemDemandsCard, {
    props: {
      kind: 'made',
      rows: [],
      loading: false,
      error: false,
      truncated: false,
      limit: 200,
      ...props,
    },
  })
}

describe('CatalogueItemDemandsCard', () => {
  it('shows the empty state when there are no rows', () => {
    const wrapper = mountCard()
    expect(wrapper.text()).toContain('No demands for this item.')
  })

  it('shows a loading spinner only while there are no rows yet', () => {
    const wrapper = mountCard({ loading: true })
    expect(wrapper.find('.loading-state').exists()).toBe(true)
  })

  it('does not show the loading spinner once rows are present, even while loading (quiet reload)', () => {
    const wrapper = mountCard({ loading: true, rows: [row()] })
    expect(wrapper.find('.loading-state').exists()).toBe(false)
    expect(wrapper.text()).toContain('#1')
  })

  it('shows the section error state and hides the empty/table state', () => {
    const wrapper = mountCard({ error: true })
    expect(wrapper.text()).toContain('Could not load this section.')
  })

  it('shows the truncation notice with the limit when truncated', () => {
    const wrapper = mountCard({ rows: [row()], truncated: true, limit: 200 })
    expect(wrapper.text()).toContain('Showing the first 200 entries only.')
  })

  it('renders a row per demand with id, quantity and project', () => {
    const wrapper = mountCard({ rows: [row({ id: 42, quantity: 3.5, unit: 'KG' })] })
    expect(wrapper.text()).toContain('#42')
    expect(wrapper.text()).toContain('3.5 kg')
    expect(wrapper.text()).toContain('P-100')
  })

  it('formats the unit code through formatUnit rather than showing the raw stored code', () => {
    const wrapper = mountCard({ rows: [row({ unit: 'M2' })] })
    expect(wrapper.text()).not.toContain('M2')
    expect(wrapper.text()).toContain('m²')
  })

  it('emits open with the row id on row click', async () => {
    const wrapper = mountCard({ rows: [row({ id: 7 })] })
    await wrapper.find('tbody tr').trigger('click')
    expect(wrapper.emitted('open')).toEqual([[7]])
  })

  it('shows a flag icon only for high-priority rows', () => {
    const wrapper = mountCard({ rows: [row({ id: 1, highPriority: false }), row({ id: 2, highPriority: true })] })
    expect(wrapper.findAll('.demand-flag')).toHaveLength(1)
  })

  it('renders no extra column when extraLabel is omitted', () => {
    const wrapper = mountCard({ rows: [row({ extra: 'L-2026-001' })] })
    expect(wrapper.text()).not.toContain('L-2026-001')
  })

  it('renders the extra column with its header when extraLabel is given', () => {
    const wrapper = mountCard({ rows: [row({ extra: 'L-2026-001' })], extraLabel: 'Lot' })
    expect(wrapper.text()).toContain('Lot')
    expect(wrapper.text()).toContain('L-2026-001')
  })

  it('resolves the status label from the given kind namespace', () => {
    const wrapper = mountCard({ kind: 'bought', rows: [row({ status: 'fulfilled' })] })
    expect(wrapper.text()).toContain('Fulfilled')
  })
})
