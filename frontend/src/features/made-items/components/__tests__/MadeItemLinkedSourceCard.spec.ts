import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { RouteStub, makeMadeItemResponse, makeTestRouter } from '@/test-utils/factories'

// The linked-material-source card fetches the full bought/source item when
// only the id is present on the made item (see
// MadeItemLinkedSourceCard.vue's linkedBoughtItem/linkedSourceItem
// watchers), so the bought-items feature is mocked to serve it.
const getBoughtItemsMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/bought-items', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/bought-items')>()
  return {
    ...actual,
    getBoughtItems: (...args: unknown[]) => getBoughtItemsMock(...args),
  }
})

const sourceItemsListMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/source-items', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/source-items')>()
  return {
    ...actual,
    sourceItemsApi: {
      ...actual.sourceItemsApi,
      list: (...args: unknown[]) => sourceItemsListMock(...args),
    },
  }
})

import MadeItemLinkedSourceCard from '../MadeItemLinkedSourceCard.vue'

import type { MadeItemResponse } from '../../types/madeItemsResponse'
import type { BoughtItemResponse } from '@/features/bought-items'
import type { SourceItemResponse } from '@/features/source-items'

function makeItem(overrides: Partial<MadeItemResponse> = {}): MadeItemResponse {
  return makeMadeItemResponse({
    id: 9,
    public_id: 'bbbbbbbb-0000-0000-0000-000000000009',
    part_number: 'PN-MADE-9',
    created: '2026-02-01',
    changed: '2026-02-01T00:00:00Z',
    article_name: 'Bracket Assembly',
    mass: 1.25,
    base_size: '100x50',
    creator: {
      id: 1,
      public_id: 'u1',
      username: 'jdoe',
      full_name: 'Jane Doe',
      has_avatar: false,
    },
    ...overrides,
  })
}

function makeBoughtItem(overrides: Partial<BoughtItemResponse> = {}): BoughtItemResponse {
  return {
    edit_version: 0,
    over_delivery_tolerance_percent: null,
    under_delivery_tolerance_percent: null,
    id: 3,
    public_id: 'c3',
    part_number: null,
    status: 'active',
    created: '2026-01-01',
    changed: '2026-01-01T00:00:00Z',
    changed_by_id: null,
    changed_by: null,
    archived: false,
    order_code_1: 'OC-1',
    order_code_2: null,
    gtin: null,
    ean: null,
    tariff_number: null,
    article_name: 'Hex Bolt',
    article_groups: [],
    data_source: 'WEB',
    mass: null,
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
    revision: null,
    vault_id: null,
    ...overrides,
  }
}

function makeSourceItem(overrides: Partial<SourceItemResponse> = {}): SourceItemResponse {
  return {
    edit_version: 0,
    over_delivery_tolerance_percent: null,
    under_delivery_tolerance_percent: null,
    id: 12,
    public_id: '11111111-1111-1111-1111-111111111111',
    status: 'active',
    created: '2026-03-01',
    changed: '2026-03-01T00:00:00Z',
    changed_by_id: null,
    changed_by: null,
    archived: false,
    type_id: 3,
    type_name: { enGB: 'Rod' },
    dimension: 'D20x100',
    material: 'Steel S235',
    mass: 1.5,
    note: null,
    order_code_1: 'OC-1',
    order_code_2: null,
    successor_item_id: null,
    creator_id: 1,
    creator: null,
    approver_id: null,
    manufacturer_id: 4,
    manufacturer_name: 'Acme Steel',
    ...overrides,
  }
}

function makeRouter() {
  return makeTestRouter([
    { path: '/catalogue/made-items/:id', component: RouteStub },
    { path: '/catalogue/bought-items/:id', component: RouteStub },
    { path: '/catalogue/source-items/:id', component: RouteStub },
  ])
}

function mountCard(item: MadeItemResponse) {
  return mountWithApp(MadeItemLinkedSourceCard, {
    props: { item },
    global: { stubs: { BoughtItemDetailFields: true, SourceItemDetailFields: true } },
  })
}

describe('MadeItemLinkedSourceCard', () => {
  beforeEach(() => {
    getBoughtItemsMock.mockReset().mockResolvedValue({ items: [], total: 0 })
    sourceItemsListMock.mockReset().mockResolvedValue({ items: [], total: 0 })
  })

  it('renders as a Panel with the "Material Source" header', () => {
    const wrapper = mountCard(makeItem())
    const panel = wrapper.findComponent({ name: 'Panel' })
    expect(panel.exists()).toBe(true)
    expect(panel.props('header')).toBe('Material Source')
  })

  it('renders the embedded bought item through BoughtItemDetailFields', () => {
    const boughtItem = makeBoughtItem({ id: 3, article_name: 'Hex Bolt' })
    const wrapper = mountCard(makeItem({ bought_item_id: 3, bought_item: boughtItem }))

    const nested = wrapper.findComponent({ name: 'BoughtItemDetailFields' })
    expect(nested.exists()).toBe(true)
    expect(nested.props('item')).toEqual(boughtItem)
    expect(nested.props('showStatus')).toBe(false)
    expect(nested.props('showMeta')).toBe(false)
    expect(wrapper.findComponent({ name: 'SourceItemDetailFields' }).exists()).toBe(false)
  })

  it('renders the embedded source item through SourceItemDetailFields', () => {
    const sourceItem = makeSourceItem({ id: 12, type_name: { enGB: 'Rod' } })
    const wrapper = mountCard(makeItem({ source_item_id: 12, source_item: sourceItem }))

    const nested = wrapper.findComponent({ name: 'SourceItemDetailFields' })
    expect(nested.exists()).toBe(true)
    expect(nested.props('item')).toEqual(sourceItem)
    expect(nested.props('showStatus')).toBe(false)
    expect(nested.props('showMeta')).toBe(false)
    expect(wrapper.findComponent({ name: 'BoughtItemDetailFields' }).exists()).toBe(false)
  })

  it('fetches the bought item when only bought_item_id is present', async () => {
    const boughtItem = makeBoughtItem({ id: 55, article_name: 'Fetched Bolt' })
    getBoughtItemsMock.mockResolvedValue({ items: [boughtItem], total: 1 })

    const wrapper = mountCard(makeItem({ bought_item_id: 55, bought_item: null }))
    await flushPromises()

    expect(getBoughtItemsMock).toHaveBeenCalledWith({ id: 55, limit: 1 })
    const nested = wrapper.findComponent({ name: 'BoughtItemDetailFields' })
    expect(nested.exists()).toBe(true)
    expect(nested.props('item')).toEqual(boughtItem)
  })

  it('fetches the source item when only source_item_id is present', async () => {
    const sourceItem = makeSourceItem({ id: 66, type_name: { enGB: 'Fetched Rod' } })
    sourceItemsListMock.mockResolvedValue({ items: [sourceItem], total: 1 })

    const wrapper = mountCard(makeItem({ source_item_id: 66, source_item: null }))
    await flushPromises()

    expect(sourceItemsListMock).toHaveBeenCalledWith({ id: 66, limit: 1 })
    const nested = wrapper.findComponent({ name: 'SourceItemDetailFields' })
    expect(nested.exists()).toBe(true)
    expect(nested.props('item')).toEqual(sourceItem)
  })

  it('falls back to the existing no-source text when neither is set', () => {
    const wrapper = mountCard(makeItem({ bought_item: null, source_item: null }))

    expect(wrapper.find('.linked-source').text()).toContain('-')
    expect(wrapper.findComponent({ name: 'BoughtItemDetailFields' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'SourceItemDetailFields' }).exists()).toBe(false)
  })

  it('renders the open-page link for the linked source when a router is installed', async () => {
    const router = makeRouter()
    await router.push('/')
    await router.isReady()

    const boughtItem = makeBoughtItem({ id: 3 })
    const wrapper = mountWithApp(MadeItemLinkedSourceCard, {
      props: { item: makeItem({ bought_item_id: 3, bought_item: boughtItem }) },
      global: {
        plugins: [router],
        stubs: { BoughtItemDetailFields: true, SourceItemDetailFields: true },
      },
    })

    const link = wrapper.find('.linked-source-header a.field-link')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('/catalogue/bought-items/3')
  })

  it('renders the open-page link for a linked source item when a router is installed', async () => {
    const router = makeRouter()
    await router.push('/')
    await router.isReady()

    const sourceItem = makeSourceItem({ id: 12 })
    const wrapper = mountWithApp(MadeItemLinkedSourceCard, {
      props: { item: makeItem({ source_item_id: 12, source_item: sourceItem }) },
      global: {
        plugins: [router],
        stubs: { BoughtItemDetailFields: true, SourceItemDetailFields: true },
      },
    })

    const link = wrapper.find('.linked-source-header a.field-link')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('/catalogue/source-items/12')
  })

  it('renders plain text (no link) for the linked source when no router is installed', () => {
    const boughtItem = makeBoughtItem({ id: 3 })
    const wrapper = mountCard(makeItem({ bought_item_id: 3, bought_item: boughtItem }))

    expect(wrapper.find('.linked-source-header a.field-link').exists()).toBe(false)
    expect(wrapper.find('.linked-source-header').text()).toContain('#3')
  })
})
