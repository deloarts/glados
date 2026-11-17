import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeOrderResponse } from '@/test-utils/factories'

// OrderFilesCell renders no per-cell spinner: each row fetches its files
// independently (no bulk-files endpoint), so a spinner per cell would flash
// staggered across the Files column during page loads. Zero-file rows render
// nothing whether or not a fetch is in-flight.

let filesById: Record<number, unknown[]>
let loadingIds: Set<number>

vi.mock('../../stores/orderFilesStore', () => ({
  useOrderFilesStore: () => ({
    getFiles: (id: number) => filesById[id] ?? [],
    isLoading: (id: number) => loadingIds.has(id),
    fetchFiles: vi.fn<(itemId: number) => Promise<void>>(),
  }),
}))

import OrderFilesCell from '../OrderFilesCell.vue'
import type { OrderFile, OrderResponse } from '../../types/ordersResponse'

function makeFile(overrides: Partial<OrderFile> = {}): OrderFile {
  return {
    id: 1,
    public_id: 'cccccccc-0000-0000-0000-000000000001',
    order_id: 99,
    file_name: 'photo.jpg',
    stored_name: 'stored-photo.jpg',
    mime_type: 'image/jpeg',
    size_bytes: 1024,
    storage_path: '/files/1',
    sha256: 'abc',
    category: 'picture',
    created: '2026-01-01T00:00:00Z',
    uploaded_by_user_id: 1,
    url: null,
    delivery_id: null,
    ...overrides,
  }
}

function mountCell(order: OrderResponse, canWrite = true) {
  return mountWithApp(OrderFilesCell, {
    attachTo: document.body,
    props: { order, canWrite },
    global: {
      directives: { tooltip: Tooltip },
      stubs: { FilePreviewDialog: true },
    },
  })
}

describe('OrderFilesCell', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    filesById = {}
    loadingIds = new Set()
  })

  it('renders no badge or icon for an order with zero files', () => {
    const wrapper = mountCell(makeOrderResponse({ id: 1 }))

    expect(wrapper.find('.category-badge').exists()).toBe(false)
    expect(wrapper.find('i.mdi').exists()).toBe(false)
  })

  it('renders no badge or icon for a zero-file order even while its files fetch is in flight', () => {
    // Guards against a per-cell loading spinner appearing during fetch: even
    // while files are loading for this row, a zero-file order renders no
    // spinner or badge, so the column stays clean during page loads.
    loadingIds.add(2)
    const wrapper = mountCell(makeOrderResponse({ id: 2 }))

    expect(wrapper.find('.category-badge').exists()).toBe(false)
    expect(wrapper.find('i.mdi').exists()).toBe(false)
    expect(wrapper.find('.files-loading').exists()).toBe(false)
  })

  it('renders a badge for a category that has files', () => {
    filesById[3] = [makeFile({ order_id: 3, category: 'picture' })]
    const wrapper = mountCell(makeOrderResponse({ id: 3 }))

    const badge = wrapper.find('.category-badge.cat-picture')
    expect(badge.exists()).toBe(true)
    expect(badge.classes()).toContain('has-files')
    expect(badge.text()).toContain('1')
  })

  it('renders an invoice badge with its own short label and counts several invoices', () => {
    filesById[4] = [
      makeFile({ id: 1, order_id: 4, category: 'invoice', mime_type: 'application/pdf' }),
      makeFile({ id: 2, order_id: 4, category: 'invoice', mime_type: 'application/pdf' }),
    ]
    const wrapper = mountCell(makeOrderResponse({ id: 4 }))

    const badge = wrapper.find('.category-badge.cat-invoice')
    expect(badge.exists()).toBe(true)
    expect(badge.classes()).toContain('has-files')
    expect(badge.text()).toContain('Inv.')
    expect(badge.text()).toContain('2')
  })

  it('shows Delete disabled with the missing permission without write:orders', async () => {
    filesById[5] = [makeFile({ order_id: 5, category: 'picture' })]
    const wrapper = mountCell(makeOrderResponse({ id: 5 }), false)

    await wrapper.find('.category-badge.cat-picture').trigger('click')
    await flushPromises()

    const remove = document.body.querySelector<HTMLButtonElement>(
      '[data-testid="order-file-delete"]',
    )
    expect(remove).not.toBeNull()
    expect(remove?.disabled).toBe(true)
    const span = remove?.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
    expect(span?.$_ptooltipValue).toBe('This needs the permission Write Orders.')
    wrapper.unmount()
  })
})
