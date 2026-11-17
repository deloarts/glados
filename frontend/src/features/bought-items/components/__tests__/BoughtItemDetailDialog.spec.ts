import { describe, it, expect, vi, afterEach } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { answerCadClaim } from '@/test-utils/cadClaim'
import { i18n } from '@/core/i18n'

// Generic fallback for everything this dialog's descendants touch besides
// getBoughtItems below (suppliersStore.refresh, articleGroupsStore.refresh,
// the files store); mirrors MadeItemDetailDialog.spec.ts's own generic mock.
vi.mock('@/core/api', () => ({
  default: {
    get: vi
      .fn<(url: string) => Promise<unknown>>()
      .mockResolvedValue({ data: { items: [], total: 0, limit: 1000, skip: 0 } }),
    put: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    post: vi.fn<() => Promise<unknown>>(),
  },
}))

const getBoughtItemsMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('../../api/getBoughtItems', () => ({
  getBoughtItems: (...args: unknown[]) => getBoughtItemsMock(...args),
}))

import BoughtItemDetailDialog from '../BoughtItemDetailDialog.vue'
import type { BoughtItemResponse } from '../../types/boughtItemsResponse'

function makeItem(overrides: Partial<BoughtItemResponse> = {}): BoughtItemResponse {
  return {
    edit_version: 0,
    over_delivery_tolerance_percent: null,
    under_delivery_tolerance_percent: null,
    id: 1,
    public_id: '00000000-0000-0000-0000-000000000001',
    part_number: 'PN-1',
    revision: null,
    status: 'active',
    archived: false,
    created: '2026-01-01',
    changed: '2026-01-01T00:00:00Z',
    changed_by_id: null,
    changed_by: null,
    order_code_1: 'OC-1',
    order_code_2: null,
    gtin: null,
    ean: null,
    tariff_number: null,
    article_name: 'Hex Bolt',
    article_groups: [],
    data_source: 'WEB',
    mass: 10,
    note: null,
    weblink: null,
    successor_item_id: null,
    creator_id: 1,
    creator: null,
    manufacturer_id: 3,
    manufacturer_name: 'ACME Corp',
    edp_part_id: null,
    edp_synced_at: null,
    pdf_files: [],
    pdm_file_id: null,
    pdm_file_version: null,
    pdm_locked_fields: [],
    pdm_sync_state: null,
    pdm_synced_at: null,
    product_family: null,
    product_family_id: null,
    vault_id: null,
    ...overrides,
  }
}

const mounted: VueWrapper[] = []

let pinia: ReturnType<typeof createPinia>

async function mountDialog(item: BoughtItemResponse, editOnOpen = false) {
  const wrapper = mountWithApp(BoughtItemDetailDialog, {
    pinia,
    attachTo: document.body,
    props: { visible: false, item, editOnOpen },
  })
  mounted.push(wrapper)
  await wrapper.setProps({ visible: true })
  await flushPromises()
  await flushPromises()
  // A PDM-claimed item asks before its form opens; these tests are about the form.
  await answerCadClaim()
  return wrapper
}

describe('BoughtItemDetailDialog', () => {
  afterEach(() => {
    mounted.splice(0).forEach((wrapper) => wrapper.unmount())
  })

  // The lock list is server-provided (item.pdm_locked_fields)
  // rather than a client-side mirror of the ownership table combined with
  // the host PDM policy, so these tests drive it straight off the item
  // fixture instead of hostStore.

  it('leaves fields editable on a WEB item (the server never locks a WEB row)', async () => {
    pinia = createPinia()
    setActivePinia(pinia)
    getBoughtItemsMock.mockResolvedValue({ items: [], total: 0 })

    await mountDialog(makeItem({ data_source: 'WEB', pdm_locked_fields: [] }), true)

    expect((document.querySelector('#bid-article-name') as HTMLInputElement).disabled).toBe(false)
    expect((document.querySelector('#bid-order-code-1') as HTMLInputElement).disabled).toBe(false)
    expect((document.querySelector('#bid-gtin') as HTMLInputElement).disabled).toBe(false)
  })

  it('locks the fields named in item.pdm_locked_fields', async () => {
    pinia = createPinia()
    setActivePinia(pinia)
    getBoughtItemsMock.mockResolvedValue({ items: [], total: 0 })

    await mountDialog(
      makeItem({
        data_source: 'CAD',
        pdm_locked_fields: [
          'article_name',
          'order_code_1',
          'order_code_2',
          'gtin',
          'ean',
          'tariff_number',
          'weblink',
          'note',
        ],
      }),
      true,
    )

    expect((document.querySelector('#bid-article-name') as HTMLInputElement).disabled).toBe(true)
    expect((document.querySelector('#bid-order-code-1') as HTMLInputElement).disabled).toBe(true)
    expect((document.querySelector('#bid-order-code-2') as HTMLInputElement).disabled).toBe(true)
    expect((document.querySelector('#bid-gtin') as HTMLInputElement).disabled).toBe(true)
    expect((document.querySelector('#bid-ean') as HTMLInputElement).disabled).toBe(true)
    expect((document.querySelector('#bid-tariff-number') as HTMLInputElement).disabled).toBe(true)
    expect((document.querySelector('#bid-weblink') as HTMLInputElement).disabled).toBe(true)
    expect((document.querySelector('#bid-note') as HTMLTextAreaElement).disabled).toBe(true)
  })

  it('leaves status editable on a locked CAD item when status itself is not in pdm_locked_fields', async () => {
    pinia = createPinia()
    setActivePinia(pinia)
    getBoughtItemsMock.mockResolvedValue({ items: [], total: 0 })

    await mountDialog(
      makeItem({ data_source: 'CAD', pdm_locked_fields: ['article_name', 'gtin'] }),
      true,
    )

    const statusSelect = document.querySelector('#bid-status')
    expect(statusSelect?.classList.contains('p-disabled')).toBe(false)
  })

  // ── Lifecycle status feature (docs/PDM_INTEGRATION.md's "lifecycle
  // mapping" section): status is itself a server-lockable field
  // (driven by the file's own PDM workflow state), and the successor
  // picker on a locked row gives way to an explanatory hint until the
  // row's status is already replaced. ─────────────────────────────────

  it('locks the status Select when pdm_locked_fields includes status', async () => {
    pinia = createPinia()
    setActivePinia(pinia)
    getBoughtItemsMock.mockResolvedValue({ items: [], total: 0 })

    await mountDialog(
      makeItem({ data_source: 'CAD', status: 'active', pdm_locked_fields: ['status'] }),
      true,
    )

    const statusSelect = document.querySelector('#bid-status')
    expect(statusSelect?.classList.contains('p-disabled')).toBe(true)
  })

  it('still shows the successor picker on a locked row whose status is already replaced', async () => {
    pinia = createPinia()
    setActivePinia(pinia)
    getBoughtItemsMock.mockResolvedValue({ items: [], total: 0 })

    await mountDialog(
      makeItem({ data_source: 'CAD', status: 'replaced', pdm_locked_fields: ['status'] }),
      true,
    )

    expect(document.querySelector('#bid-successor-item')).not.toBeNull()
    expect(document.body.textContent).not.toContain(
      i18n.global.t('boughtItems.edit.pdmManagedStatusHint'),
    )
  })

  it('shows the PDM-managed-status hint instead of the successor picker on a locked row not yet replaced', async () => {
    pinia = createPinia()
    setActivePinia(pinia)
    getBoughtItemsMock.mockResolvedValue({ items: [], total: 0 })

    await mountDialog(
      makeItem({ data_source: 'CAD', status: 'active', pdm_locked_fields: ['status'] }),
      true,
    )

    expect(document.querySelector('#bid-successor-item')).toBeNull()
    expect(document.body.textContent).toContain(
      i18n.global.t('boughtItems.edit.pdmManagedStatusHint'),
    )
  })

  it('does not lock any field when pdm_locked_fields is empty', async () => {
    pinia = createPinia()
    setActivePinia(pinia)
    getBoughtItemsMock.mockResolvedValue({ items: [], total: 0 })

    await mountDialog(makeItem({ data_source: 'CAD', pdm_locked_fields: [] }), true)

    expect((document.querySelector('#bid-article-name') as HTMLInputElement).disabled).toBe(false)
    expect((document.querySelector('#bid-gtin') as HTMLInputElement).disabled).toBe(false)
  })
})
