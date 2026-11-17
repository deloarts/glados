import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'


vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: [] }),
  },
}))

import LotRecordSource from '../lot-detail/LotRecordSource.vue'
import type { LotResponse } from '../../../types/productionLotsResponse'
import type { LotSourceItem } from '../../composables/useLotRecordData'
import type { BoughtItemResponse } from '@/features/bought-items'
import type { SourceItemResponse } from '@/features/source-items'
import { mountWithApp } from '@/test-utils/mountWithApp'

const lot: LotResponse = {
  edit_version: 0,
  id: 1,
  public_id: '3f2504e0-4f89-11d3-9a0c-0305e82c3301',
  created: '2026-07-01',
  changed: null,
  changed_by: null,
  changed_by_id: null,
  lot_number: 'LOT-0001',
  quantity: 10,
  quantity_completed: 0,
  status: 'draft',
  priority: 'normal',
  note: null,
  required_delivery_date: null,
  creator_id: 1,
  creator: null,
  made_item_id: 1,
  made_item_part_number: 'PN-1',
  made_item_article_name: 'Bracket',
  made_item_revision: 'A',
  made_item_material: '1.0037',
  source_bought_item_id: null,
  source_item_id: null,
  source_made_item_id: null,
  source_label: 'Round bar 20mm',
  source_sublabel: '1.0037',
  demand_status: '',
  is_alteration: false,
  project_id: 42,
  project_number: 'P-001',
  project_customer: 'Acme',
  input_demand_id: null,
  source_approval_status: 'not_required',
  positions: [],
  steps: [],
  actions: [],
  blocked_actions: {},
  canceled_at: null,
  completed_at: null,
  follow_up_lots: [],
  force_completed_at: null,
  held_at: null,
  origin_disposition: null,
  origin_lot_id: null,
  origin_lot_number: null,
  source_approved_by_id: null,
  source_approved_date: null,
  source_delivery_date: null,
  source_expected_delivery_date: null,
  source_order_id: null,
  source_order_number: null,
  source_rejected_by_id: null,
  source_rejected_date: null,
  source_rejection_reason: null,
}

function boughtSource(overrides: Partial<BoughtItemResponse> = {}): LotSourceItem {
  return {
    kind: 'bought',
    item: {
      edit_version: 0,
      over_delivery_tolerance_percent: null,
      under_delivery_tolerance_percent: null,
      id: 5,
      public_id: 'aaaaaaaa-0000-0000-0000-000000000005',
      part_number: 'BP-77',
      status: 'active',
      archived: false,
      created: '2026-06-01',
      changed: '2026-06-01T00:00:00Z',
      changed_by_id: null,
      changed_by: null,
      order_code_1: 'OC-1',
      order_code_2: 'OC-2',
      gtin: '04012345678901',
      ean: '4012345678901',
      tariff_number: '7318 15 90',
      article_name: 'Hex bolt M8',
      article_groups: [],
      data_source: 'WEB',
      mass: 12.5,
      note: 'buy in packs of 100',
      weblink: 'https://example.test/bolt',
      successor_item_id: null,
      creator_id: 1,
      creator: null,
      manufacturer_id: 1,
      manufacturer_name: 'Fastenco',
      pdf_files: [],
      edp_part_id: null,
      edp_synced_at: null,
      pdm_file_id: null,
      pdm_file_version: null,
      pdm_locked_fields: [],
      pdm_sync_state: null,
      pdm_synced_at: null,
      product_family: null,
      product_family_id: null,
      revision: null,
      vault_id: null,
      ...overrides,
    },
  }
}

function stockSource(overrides: Partial<SourceItemResponse> = {}): LotSourceItem {
  return {
    kind: 'source',
    item: {
      edit_version: 0,
      over_delivery_tolerance_percent: null,
      under_delivery_tolerance_percent: null,
      id: 6,
      public_id: 'bbbbbbbb-0000-0000-0000-000000000006',
      status: 'active',
      archived: false,
      created: '2026-06-01',
      changed: '2026-06-01T00:00:00Z',
      changed_by_id: null,
      changed_by: null,
      type_id: 2,
      type_name: { enGB: 'Round bar' },
      dimension: 'D20',
      material: '1.0037',
      mass: 24.7,
      note: 'stock item',
      order_code_1: null,
      order_code_2: null,
      successor_item_id: null,
      creator_id: 1,
      creator: null,
      approver_id: null,
      manufacturer_id: null,
      manufacturer_name: '',
      ...overrides,
    },
  }
}

function mountSource(sourceItem: LotSourceItem | null) {
  return mountWithApp(LotRecordSource, {
    attachTo: document.body,
    props: {
      lot,
      sourceItem,
      // The raw-material demand is a section of this same card; these
      // tests cover the source item itself, so it stays empty.
      sourceItemDemand: null,
      sourceItemDemandArrived: 0,
      summary: null,
      allocations: [],
      sourceOrder: null,
      manageMode: false,
      canWrite: false,
    },
  })
}

describe('LotRecordSource', () => {
  it('shows every bought-item field explicitly', async () => {
    const wrapper = mountSource(boughtSource())
    await flushPromises()

    const text = wrapper.text()
    const missing = [
      'BP-77',
      'Hex bolt M8',
      'Fastenco',
      'OC-1',
      'OC-2',
      '04012345678901',
      '4012345678901',
      '7318 15 90',
      '12.5',
      'Web',
      'buy in packs of 100',
      'https://example.test/bolt',
      'aaaaaaaa-0000-0000-0000-000000000005',
      'Active',
    ].filter((value) => !text.includes(value))

    expect(missing).toEqual([])
    // The data source shows its label, never the stored value.
    expect(text).not.toContain('WEB')

    wrapper.unmount()
  })

  it('shows source-item material and dimension as their own fields, not only in the label', async () => {
    const wrapper = mountSource(stockSource())
    await flushPromises()

    // Labels are uppercased in CSS, so the DOM text stays title-case.
    const labels = wrapper.findAll('.field-label').map((l) => l.text())
    expect(labels).toContain('Material')
    expect(labels).toContain('Dimension')
    expect(labels).toContain('Type')

    const text = wrapper.text()
    expect(text).toContain('Round bar')
    expect(text).toContain('D20')
    expect(text).toContain('24.7')

    wrapper.unmount()
  })

  it('flags an archived catalogue entry', async () => {
    const wrapper = mountSource(boughtSource({ archived: true }))
    await flushPromises()

    expect(wrapper.text()).toContain('Archived')

    wrapper.unmount()
  })

  it('renders the weblink as a real external link', async () => {
    const wrapper = mountSource(boughtSource())
    await flushPromises()

    const link = wrapper.find('a[href="https://example.test/bolt"]')
    expect(link.exists()).toBe(true)
    expect(link.attributes('target')).toBe('_blank')
    expect(link.attributes('rel')).toBe('noopener noreferrer')

    wrapper.unmount()
  })

  it('renders no href for an unsafe weblink, but still shows it as text', async () => {
    const wrapper = mountSource(boughtSource({ weblink: 'javascript:alert(1)' }))
    await flushPromises()

    expect(wrapper.find('a').exists()).toBe(false)
    expect(wrapper.text()).toContain('javascript:alert(1)')

    wrapper.unmount()
  })

  it('renders the raw-material demand as a section of this same card', async () => {
    const wrapper = mountWithApp(LotRecordSource, {
      attachTo: document.body,
      props: {
        lot: { ...lot, input_demand_id: null },
        sourceItem: boughtSource(),
        sourceItemDemand: null,
        sourceItemDemandArrived: 0,
        summary: null,
        allocations: [],
        sourceOrder: null,
        manageMode: false,
        canWrite: false,
      },
    })
    await flushPromises()

    // One card, two sections, not two cards.
    expect(wrapper.findAllComponents({ name: 'Panel' })).toHaveLength(1)
    expect(wrapper.findComponent({ name: 'LotRecordSourceDemand' }).exists()).toBe(true)
    expect(wrapper.text()).toContain('This lot has no raw-material demand.')

    wrapper.unmount()
  })

  it('renders the catalogue status as a severity-coloured tag, not plain text', async () => {
    const wrapper = mountSource(boughtSource({ status: 'replaced' }))
    await flushPromises()

    const statusTag = wrapper
      .findAllComponents({ name: 'Tag' })
      .find((tag) => tag.props('value') === 'Replaced')
    expect(statusTag).toBeTruthy()
    expect(statusTag!.props('severity')).toBe('warn')

    wrapper.unmount()
  })

  it('keeps the creator/changed footer outside the scrolling region', async () => {
    const wrapper = mountSource(boughtSource())
    await flushPromises()

    const scrollBody = wrapper.find('.card-scroll-body')
    expect(scrollBody.exists()).toBe(true)
    // The footer must be a sibling of the scroll body, never a descendant:
    // that is what keeps it pinned and always visible.
    expect(scrollBody.find('.record-meta').exists()).toBe(false)
    expect(wrapper.find('.record-meta').exists()).toBe(true)

    wrapper.unmount()
  })

  it('omits the weblink field entirely for a source item, which has none', async () => {
    const wrapper = mountSource(stockSource())
    await flushPromises()

    expect(wrapper.findAll('.field-label').map((l) => l.text())).not.toContain('Weblink')

    wrapper.unmount()
  })
})
