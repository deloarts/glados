import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useHostStore } from '@/core/host/stores/hostStore'
import { RouteStub, makeTestRouter } from '@/test-utils/factories'

// One file per category so the Files-card-categories test (pdf only, see
// CatalogueItemFilesCard.vue and BoughtItemDetailView.vue's own
// FILES_CARD_CATEGORIES comment) can assert both what shows and what's
// excluded. `vi.hoisted` because the `@/core/api` mock factory below needs
// it and vi.mock factories are hoisted above normal module-scope consts.
const { BOUGHT_ITEM_FILES } = vi.hoisted(() => {
  function file(overrides: Record<string, unknown>) {
    return {
      id: 0,
      public_id: 'ffffffff-0000-0000-0000-000000000000',
      bought_item_id: 1,
      file_name: '',
      stored_name: '',
      mime_type: 'application/octet-stream',
      size_bytes: 100,
      storage_path: '',
      sha256: '',
      created: '2026-01-01T00:00:00Z',
      uploaded_by_user_id: 1,
      url: null,
      ...overrides,
    }
  }
  // No 'mesh' category file here on purpose. MeshViewer does real
  // three.js/WebGL work on mount that jsdom can't support, same reasoning
  // as LotRecordItem.spec.ts's own fixtures. CatalogueItemMedia.spec.ts
  // already covers the mesh-tile branch at the unit level.
  const BOUGHT_ITEM_FILES = [
    file({ id: 203, file_name: 'spec.pdf', mime_type: 'application/pdf', category: 'pdf' }),
  ]
  return { BOUGHT_ITEM_FILES }
})

// Generic fallback for anything not mocked below (e.g. store refreshes
// triggered by a stubbed dialog's props). Mirrors ProjectDetailView.spec.ts.
// `/bought-items-files` (useBoughtItemFilesStore's batched fetch, see
// createFilesStore.ts) gets real fixture files instead of the empty-page
// fallback so the Files-card-categories test below has something to filter.
vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<(url: string) => Promise<{ data: unknown }>>(async (url) => {
      if (url === '/bought-items-files') return { data: BOUGHT_ITEM_FILES }
      if (url.includes('/pictures')) return { data: [] }
      return { data: { items: [], total: 0 } }
    }),
  },
}))

const getBoughtItemsMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/bought-items/api/getBoughtItems', () => ({
  getBoughtItems: (...args: unknown[]) => getBoughtItemsMock(...args),
}))

const getDemandsMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/bought-items/api/boughtItemDemandsApi', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/features/bought-items/api/boughtItemDemandsApi')>()),
  getDemands: (...args: unknown[]) => getDemandsMock(...args),
}))

const getBoughtItemChangelogMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/bought-items/api/getBoughtItemChangelog', () => ({
  getBoughtItemChangelog: (...args: unknown[]) => getBoughtItemChangelogMock(...args),
}))

const getOrdersMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
// Partial mock (importOriginal): CatalogueItemOrdersCard (mounted for real
// below, so "orders reaching the cards" can be asserted against actual
// rendered output) reads useOrderFormatters from this same barrel, and
// OrderDetailDialog is imported by the view itself (for the lazy order
// dialog), so both have to stay real, only getOrders is swapped.
vi.mock('@/features/orders', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/orders')>()
  return { ...actual, getOrders: (...args: unknown[]) => getOrdersMock(...args) }
})

const getProjectsMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/projects/api/getProjects', () => ({
  getProjects: (...args: unknown[]) => getProjectsMock(...args),
}))

const printDocumentsMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/print-labels/api/printDocuments', () => ({
  printDocuments: (...args: unknown[]) => printDocumentsMock(...args),
}))

let hasPermissionMock = () => true
vi.mock('@/core/composables/usePermissions', () => ({
  usePermissions: () => ({ hasPermission: (...args: unknown[]) => hasPermissionMock(...(args as [])) }),
}))

const writeTextMock = vi.fn<(value: string) => Promise<void>>()
Object.assign(navigator, { clipboard: { writeText: writeTextMock } })

import BoughtItemDetailView from '../BoughtItemDetailView.vue'
import { BoughtItemDetailFields } from '@/features/bought-items'

vi.stubGlobal(
  'ResizeObserver',
  class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  },
)

function makeItem(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    public_id: 'aaaaaaaa-0000-0000-0000-000000000001',
    part_number: 'PN-1',
    status: 'active',
    created: '2026-01-01',
    changed: null,
    deleted: false,
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
    manufacturer_id: 1,
    manufacturer_name: 'ACME',
    ...overrides,
  }
}

function makeDemand(overrides: Record<string, unknown> = {}) {
  return {
    id: 10,
    public_id: 'd',
    status: 'open',
    created: '2026-01-01',
    changed: null,
    quantity: 5,
    unit: 'PCS',
    items_per_unit: 1,
    high_priority: false,
    notify_on_delivery: false,
    note: null,
    desired_delivery_date: null,
    creator_id: 1,
    creator: { id: 1, public_id: 'u', username: 'jd', full_name: 'Jane Doe', email: 'j@x.com', has_avatar: false },
    item_id: 1,
    item_order_code_1: 'OC-1',
    item_article_name: 'Hex Bolt',
    project_id: 100,
    project_number: 'P-100',
    project_customer: 'ACME',
    project_description: 'Widget line',
    project_status: 'active',
    bucket_id: null,
    ...overrides,
  }
}

function makeOrder(id: number, items: unknown[], overrides: Record<string, unknown> = {}) {
  return {
    id,
    public_id: `order-${id}`,
    order_number: `ORD-${id}`,
    status: 'ordered',
    created: '2026-01-01T00:00:00Z',
    changed: null,
    total: null,
    note: null,
    ordered_date: null,
    expected_delivery_date: null,
    delivery_date: null,
    storage_place: null,
    creator_id: 1,
    creator: null,
    supplier_id: 1,
    supplier_name: 'Supplier Co',
    supplier_vat_id: '',
    items,
    ...overrides,
  }
}

function makeOrderItem(overrides: Record<string, unknown> = {}) {
  return {
    id: 20,
    public_id: 'oi',
    status: 'delivered',
    created: '2026-01-01T00:00:00Z',
    changed: null,
    position: 1,
    quantity: 3,
    quantity_delivered: 3,
    unit: 'PCS',
    items_per_unit: 1,
    price: null,
    note: null,
    ordered_date: null,
    expected_delivery_date: null,
    delivery_date: null,
    storage_place: null,
    expected_pickup_date: null,
    ready_for_pickup_date: null,
    creator_id: 1,
    creator: null,
    orderer_id: null,
    orderer: null,
    receiver_id: null,
    receiver: null,
    bought_item_id: 1,
    source_item_id: null,
    virtual_name: null,
    item_order_code_1: 'OC-1',
    item_order_code_2: null,
    item_specification: '',
    item_article_name: 'Hex Bolt',
    item_part_number: 'PN-1',
    item_material: null,
    item_dimension: null,
    item_type_name: null,
    item_revision: null,
    item_base_size: null,
    item_mass: null,
    item_manufacturer: null,
    made_item_id: null,
    order_id: 1,
    supplier_id: 1,
    supplier_name: 'Supplier Co',
    project_id: 100,
    project_number: 'P-100',
    project_customer: 'ACME',
    project_description: 'Widget line',
    project_status: 'active',
    line_type: 'bought',
    lot_position_id: null,
    lot_id: null,
    lot_number: '',
    fabrication_method: '',
    ...overrides,
  }
}

function makeRouter() {
  return makeTestRouter([
    {
      path: '/catalogue/bought-items/:id(\\d+)',
      name: 'BoughtItemDetail',
      component: BoughtItemDetailView,
    },
    { path: '/catalogue/bought-items', component: RouteStub },
  ])
}

const mounted: VueWrapper[] = []

async function mountView(id = '1', { storageEnabled = false } = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useHostStore().storageEnabled = storageEnabled

  const router = makeRouter()
  await router.push(`/catalogue/bought-items/${id}`)
  await router.isReady()

  const wrapper = mountWithApp(BoughtItemDetailView, {
    pinia,
    global: {
      plugins: [router, ConfirmationService],
      directives: { tooltip: Tooltip },
      stubs: {
        BoughtItemDetailDialog: true,
        BoughtItemDemandCreateForm: true,
        BoughtItemAddToOrderDialog: true,
        BoughtItemDemandDetailDialog: true,
        OrderDetailDialog: true,
      },
    },
  })
  mounted.push(wrapper)
  await flushPromises()
  await flushPromises()
  return { wrapper, router }
}

function defaultMocks(): void {
  getBoughtItemsMock.mockResolvedValue({ items: [makeItem()], total: 1 })
  getDemandsMock.mockResolvedValue({ items: [], total: 0 })
  getBoughtItemChangelogMock.mockResolvedValue([])
  getOrdersMock.mockResolvedValue({ items: [], total: 0 })
  getProjectsMock.mockResolvedValue({ items: [], total: 0 })
  printDocumentsMock.mockResolvedValue([{ status: 'sent', error_message: null }])
}

describe('BoughtItemDetailView', () => {
  beforeEach(() => {
    getBoughtItemsMock.mockReset()
    getDemandsMock.mockReset()
    getBoughtItemChangelogMock.mockReset()
    getOrdersMock.mockReset()
    getProjectsMock.mockReset()
    printDocumentsMock.mockReset()
    writeTextMock.mockReset().mockResolvedValue(undefined)
    hasPermissionMock = () => true
    defaultMocks()
  })

  afterEach(() => {
    mounted.splice(0).forEach((wrapper) => wrapper.unmount())
  })

  it('shows the info bar with part number, status, and article name', async () => {
    getBoughtItemsMock.mockResolvedValue({
      items: [makeItem({ part_number: 'PN-42', article_name: 'Steel Washer', status: 'active' })],
      total: 1,
    })

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('PN-42')
    expect(wrapper.text()).toContain('Steel Washer')
    expect(wrapper.text()).toContain('Active')
  })

  it('falls back to order_code_1 in the info bar when part_number is unset', async () => {
    getBoughtItemsMock.mockResolvedValue({
      items: [makeItem({ part_number: null, order_code_1: 'OC-FALLBACK' })],
      total: 1,
    })

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('OC-FALLBACK')
  })

  it('shows the not-found screen when the item list comes back empty', async () => {
    getBoughtItemsMock.mockResolvedValue({ items: [], total: 0 })

    const { wrapper } = await mountView('999')

    expect(wrapper.text()).toContain('This item does not exist or has been deleted.')
  })

  it('navigates back to the catalogue list', async () => {
    const { wrapper, router } = await mountView()

    const back = wrapper.findAll('button').find((b) => b.text() === 'Back to Bought Items')
    expect(back).toBeTruthy()
    await back!.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/catalogue/bought-items')
  })

  it('disables the Edit item button without WRITE_BOUGHT_ITEMS', async () => {
    hasPermissionMock = () => false
    const { wrapper } = await mountView()

    const editButton = wrapper.findAll('button').find((b) => b.text() === 'Edit item')
    expect(editButton?.attributes('disabled')).toBeDefined()
  })

  it('opens the edit dialog with editOnOpen when Edit item is clicked', async () => {
    const { wrapper } = await mountView()

    const editButton = wrapper.findAll('button').find((b) => b.text() === 'Edit item')
    expect(editButton?.attributes('disabled')).toBeUndefined()
    await editButton!.trigger('click')

    const dialog = wrapper.findComponent({ name: 'BoughtItemDetailDialog' })
    expect(dialog.exists()).toBe(true)
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('editOnOpen')).toBe(true)
  })

  it('prints a label through printDocuments with the bought-item root and classifier', async () => {
    const { wrapper } = await mountView()

    const menu = wrapper.findComponent({ name: 'Menu' })
    const items = menu.props('model') as { label: string; command: () => void }[]
    const labelItem = items.find((i) => i.label === 'Label')
    expect(labelItem).toBeDefined()

    labelItem!.command()
    await flushPromises()

    expect(printDocumentsMock).toHaveBeenCalledWith({
      root_type: 'bought_item',
      root_id: 1,
      items: [{ classifier: 'bought_item_label' }],
    })
  })

  it('prints a docket through printDocuments with the bought-item docket classifier', async () => {
    const { wrapper } = await mountView()

    const menu = wrapper.findComponent({ name: 'Menu' })
    const items = menu.props('model') as { label: string; command: () => void }[]
    const docketItem = items.find((i) => i.label === 'Docket')
    expect(docketItem).toBeDefined()

    docketItem!.command()
    await flushPromises()

    expect(printDocumentsMock).toHaveBeenCalledWith({
      root_type: 'bought_item',
      root_id: 1,
      items: [{ classifier: 'bought_item_docket' }],
    })
  })

  it('copies the item UUID to the clipboard', async () => {
    getBoughtItemsMock.mockResolvedValue({
      items: [makeItem({ public_id: 'copy-me-uuid' })],
      total: 1,
    })
    const { wrapper } = await mountView()

    const copyButton = wrapper.findAll('button').find((b) => b.text() === 'Copy UUID')
    expect(copyButton).toBeTruthy()
    await copyButton!.trigger('click')

    expect(writeTextMock).toHaveBeenCalledWith('copy-me-uuid')
  })

  it('passes the fetched demand and order rows through to the cards', async () => {
    getDemandsMock.mockResolvedValue({
      items: [makeDemand({ id: 77, project_number: 'P-777' })],
      total: 1,
    })
    getOrdersMock.mockResolvedValue({
      items: [makeOrder(5, [makeOrderItem({ id: 88, bought_item_id: 1 })])],
      total: 1,
    })

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('#77')
    expect(wrapper.text()).toContain('P-777')
    expect(wrapper.text()).toContain('ORD-5')
  })

  it('suppresses the Item card status tag - the info bar already shows it', async () => {
    const { wrapper } = await mountView()

    const fields = wrapper.findComponent(BoughtItemDetailFields)
    expect(fields.exists()).toBe(true)
    expect(fields.props('showStatus')).toBe(false)
  })

  it('shows the Files card with only pdf files', async () => {
    const { wrapper } = await mountView('1', { storageEnabled: true })

    const text = wrapper.text()
    expect(text).toContain('spec.pdf')
  })

  it('refetches on sync', async () => {
    const { wrapper } = await mountView()

    getBoughtItemsMock.mockClear()
    const syncButton = wrapper.findAll('button').find((b) => b.text() === 'Sync')
    expect(syncButton).toBeTruthy()
    await syncButton!.trigger('click')
    await flushPromises()

    expect(getBoughtItemsMock).toHaveBeenCalledTimes(1)
  })
})
