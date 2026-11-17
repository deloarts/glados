import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'

import type { LotResponse } from '../../../types/productionLotsResponse'
import type { MadeItemFile, MadeItemResponse } from '@/features/made-items'

// The mesh category is deliberately excluded from these fixtures: MeshViewer
// does real three.js/WebGL work on mount that jsdom can't support, so no test
// here ever gives it a blob to render. The files-row and preview-dialog wiring
// (the part that's actually testable in jsdom) doesn't depend on mesh at all.
const { FILES, lotFixture } = vi.hoisted(() => {
  const FILES: MadeItemFile[] = [
    {
      id: 2,
      public_id: 'dddddddd-0000-0000-0000-000000000002',
      made_item_id: 1,
      file_name: 'drawing.pdf',
      stored_name: 'drawing.pdf',
      mime_type: 'application/pdf',
      size_bytes: 200,
      storage_path: '',
      sha256: '',
      category: 'pdf',
      created: '2026-07-01',
      uploaded_by_user_id: 1,
      url: null,
      from_pdm: false,
    },
    {
      id: 3,
      public_id: 'dddddddd-0000-0000-0000-000000000003',
      made_item_id: 1,
      file_name: 'part.step',
      stored_name: 'part.step',
      mime_type: 'application/octet-stream',
      size_bytes: 300,
      storage_path: '',
      sha256: '',
      category: 'step',
      created: '2026-07-01',
      uploaded_by_user_id: 1,
      url: null,
      from_pdm: false,
    },
  ]

  const lotFixture: LotResponse = {
    edit_version: 0,
    id: 1,
    created: '2026-07-01',
    changed: null,
    changed_by: null,
    changed_by_id: null,
    public_id: '00000000-0000-0000-0000-000000000001',
    lot_number: 'LOT-0001',
    quantity: 10,
    quantity_completed: 4,
    status: 'in_progress',
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
    source_label: '',
    source_sublabel: '',
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

  return { FILES, lotFixture }
})

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<(url: string) => Promise<{ data: unknown }>>(async (url) => {
      if (url === '/made-items-files') return { data: FILES }
      if (url.endsWith('/changelog')) return { data: [] }
      return { data: { items: [], total: 0, limit: 1000, skip: 0 } }
    }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import LotRecordItem from '../lot-detail/LotRecordItem.vue'
import { useHostStore } from '@/core/host/stores/hostStore'

function madeItemFixture(overrides: Partial<MadeItemResponse> = {}): MadeItemResponse {
  return {
    edit_version: 0,
    id: 1,
    public_id: 'cccccccc-0000-0000-0000-000000000001',
    part_number: 'PN-1',
    revision: 'A',
    status: 'active',
    created: '2026-07-01',
    changed: '2026-07-01T00:00:00Z',
    archived: false,
    revision_date: null,
    revision_note: null,
    article_name: 'Bracket',
    article_groups: [],
    data_source: 'WEB',
    material: '1.0037',
    mass: null,
    base_size: null,
    note: null,
    weblink: null,
    successor_item_id: null,
    creator_id: 1,
    creator: null,
    bought_item_id: null,
    bought_item: null,
    source_item_id: null,
    customer_id: null,
    customer_name: null,
    customer_part_number: null,
    customer_revision: null,
    source_item: null,
    source_label: '',
    source_sublabel: '',
    processes: [],
    changed_by: null,
    changed_by_id: null,
    pdm_file_id: null,
    pdm_file_version: null,
    pdm_locked_fields: [],
    pdm_source_item_id: null,
    pdm_sync_state: null,
    pdm_synced_at: null,
    vault_id: null,
    ...overrides,
  }
}

function mountItem(madeItem: MadeItemResponse | null = null) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useHostStore().storageEnabled = true

  return mountWithApp(LotRecordItem, {
    pinia,
    attachTo: document.body,
    props: { lot: lotFixture, madeItem },
  })
}

describe('LotRecordItem files row', () => {
  it('labels a PDM-owned item PDM rather than the stored CAD', async () => {
    const wrapper = mountItem(madeItemFixture({ data_source: 'CAD' }))
    await flushPromises()
    await flushPromises()

    expect(wrapper.text()).toContain('PDM')
    expect(wrapper.text()).not.toContain('CAD')

    wrapper.unmount()
  })

  it('shows one icon per file', async () => {
    const wrapper = mountItem()
    await flushPromises()
    await flushPromises()

    const icons = wrapper.findAll('.item-file-icon')
    expect(icons).toHaveLength(2)

    wrapper.unmount()
  })

  it('scrolls the creator/changed footer together with the fields', async () => {
    // The footer only renders once the made item is loaded.
    const wrapper = mountItem(madeItemFixture())
    await flushPromises()
    await flushPromises()

    const scrollBody = wrapper.find('.card-scroll-body')
    expect(scrollBody.exists()).toBe(true)
    expect(scrollBody.find('.item-files').exists()).toBe(true)
    // The footer lives inside the scroll body so it never reserves card
    // height of its own.
    expect(wrapper.find('.record-meta').exists()).toBe(true)
    expect(scrollBody.find('.record-meta').exists()).toBe(true)

    wrapper.unmount()
  })

  it('opens the file preview dialog with the clicked file', async () => {
    const wrapper = mountItem()
    await flushPromises()
    await flushPromises()

    await wrapper.findAll('.item-file-icon')[0]!.trigger('click')
    await flushPromises()

    const dialog = wrapper.findComponent({ name: 'FilePreviewDialog' })
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('filename')).toBe('drawing.pdf')
    expect(dialog.props('mimeType')).toBe('application/pdf')

    wrapper.unmount()
  })
})

describe('LotRecordItem weblink', () => {
  it('renders a safe weblink as a clickable href', async () => {
    const wrapper = mountItem(madeItemFixture({ weblink: 'https://example.com' }))
    await flushPromises()
    await flushPromises()

    const link = wrapper.find('a[href="https://example.com"]')
    expect(link.exists()).toBe(true)
    expect(link.text()).toBe('https://example.com')

    wrapper.unmount()
  })

  it('renders no href for an unsafe weblink, but still shows it as text', async () => {
    const wrapper = mountItem(madeItemFixture({ weblink: 'javascript:alert(1)' }))
    await flushPromises()
    await flushPromises()

    expect(wrapper.find('a').exists()).toBe(false)
    expect(wrapper.text()).toContain('javascript:alert(1)')

    wrapper.unmount()
  })
})
