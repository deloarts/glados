import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { DOMWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { Permission } from '@/core/auth/permissions'
import { useHostStore } from '@/core/host/stores/hostStore'
import type { OrderItemResponse, OrderResponse } from '@/features/orders'

let hasPermissionMock = (_permission: string) => true
vi.mock('@/core/composables/usePermissions', () => ({
  usePermissions: () => ({ hasPermission: (permission: string) => hasPermissionMock(permission) }),
}))

// One file per category so the Files-card-categories test (pdf only, see
// CatalogueItemFilesCard.vue and SourceItemDetailView.vue's own
// FILES_CARD_CATEGORIES comment) can assert both what shows and what's
// excluded. Fetched through useSourceItemFilesStore, the same store
// CatalogueItemMedia and CatalogueItemFilesCard both read. `vi.hoisted` is
// used because the `@/core/api` mock factory below needs it and vi.mock
// factories are hoisted above normal module-scope consts. No 'mesh' category
// file in the default fixture on purpose: MeshViewer does real
// three.js/WebGL work on mount that jsdom can't support, same reasoning as
// BoughtItemDetailView.spec.ts/MadeItemDetailView.spec.ts's own fixtures;
// the one test that needs a mesh file on record stubs CatalogueItemMedia
// instead of exercising the real mesh-tile branch.
// `sourceItemFilesRef` is a mutable holder (not a plain const) so the one
// test that needs a mesh file on record (checking that CatalogueItemMedia's
// `meshPlaceholderUrl` prop turns off once a real mesh file exists) can swap
// in a different fixture list for that test only, then the next test's
// `beforeEach` below resets it back to the no-mesh default.
const { SOURCE_ITEM_FILES, sourceItemFilesRef, makeSourceItemFile } = vi.hoisted(() => {
  function file(overrides: Record<string, unknown>) {
    return {
      id: 0,
      public_id: 'ffffffff-0000-0000-0000-000000000000',
      source_item_id: 5,
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
  const SOURCE_ITEM_FILES = [
    file({ id: 303, file_name: 'spec.pdf', mime_type: 'application/pdf', category: 'pdf' }),
  ]
  return { SOURCE_ITEM_FILES, sourceItemFilesRef: { current: SOURCE_ITEM_FILES }, makeSourceItemFile: file }
})

// Generic fallback for anything not mocked below. Mirrors
// BoughtItemDetailView.spec.ts/MadeItemDetailView.spec.ts. `/source-items-
// files` (useSourceItemFilesStore's batched fetch, see createFilesStore.ts)
// gets real fixture files instead of the empty-page fallback so the
// Files-card-categories test below has something to filter.
vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<(url: string) => Promise<{ data: unknown }>>(async (url) => {
      if (url === '/source-items-files') return { data: sourceItemFilesRef.current }
      if (url.includes('/pictures')) return { data: [] }
      return { data: { items: [], total: 0 } }
    }),
  },
}))

const listMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/source-items/api/sourceItemsApi', () => ({
  sourceItemsApi: { list: (...args: unknown[]) => listMock(...args) },
}))

const getSourceItemDemandsMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/source-items/api/sourceItemDemandsApi', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/features/source-items/api/sourceItemDemandsApi')>()),
  getSourceItemDemands: (...args: unknown[]) => getSourceItemDemandsMock(...args),
}))

const getSourceItemChangelogMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/source-items/api/getSourceItemChangelog', () => ({
  getSourceItemChangelog: (...args: unknown[]) => getSourceItemChangelogMock(...args),
}))

// `@/features/orders` is partially mocked: only `getOrders` (the one
// network call this page's composable makes through it) is replaced. Every
// other export (OrderDetailDialog, useOrderFormatters, ...) has to stay real:
// OrderDetailDialog is used directly by this view (stubbed below instead,
// which needs the *real* component reference to match against), and
// CatalogueItemOrdersCard pulls useOrderFormatters from this same barrel.
const getOrdersMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
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

import SourceItemDetailView from '../SourceItemDetailView.vue'
import CatalogueItemMedia from '../../components/CatalogueItemMedia.vue'
import { makeSourceItemDemandResponse, makeTestRouter } from '@/test-utils/factories'
import {
  SourceItemDetailFields,
  SourceItemThumbnailCell,
  sourceItemPlaceholder,
} from '@/features/source-items'
import type { SourceItemDemandResponse, SourceItemResponse } from '@/features/source-items'

vi.stubGlobal(
  'ResizeObserver',
  class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  },
)

function makeItem(overrides: Partial<SourceItemResponse> = {}): SourceItemResponse {
  return {
    edit_version: 0,
    over_delivery_tolerance_percent: null,
    under_delivery_tolerance_percent: null,
    id: 5,
    public_id: 'cccccccc-0000-0000-0000-000000000005',
    status: 'active',
    created: '2026-03-01',
    changed: '2026-03-01T00:00:00Z',
    changed_by_id: null,
    changed_by: null,
    archived: false,
    type_id: 1,
    type_name: { enGB: 'Rod' },
    dimension: 'D20x100',
    material: 'Steel S235',
    mass: 1,
    note: null,
    order_code_1: null,
    order_code_2: null,
    successor_item_id: null,
    creator_id: 1,
    creator: { id: 1, full_name: 'Jane Doe' } as SourceItemResponse['creator'],
    approver_id: null,
    manufacturer_id: null,
    manufacturer_name: '',
    ...overrides,
  }
}

function makeDemand(overrides: Partial<SourceItemDemandResponse> = {}): SourceItemDemandResponse {
  return makeSourceItemDemandResponse({
    id: 9,
    public_id: 'd9',
    created: '2026-03-01',
    quantity: 10,
    unit: 'pcs',
    creator: { id: 1, full_name: 'Jane Doe' } as SourceItemDemandResponse['creator'],
    source_item_id: 5,
    source_item: null,
    lot_number: 'L-2026-001',
    project_id: 100,
    project_number: 'P-100',
    project_customer: 'ACME',
    project_description: 'Widget',
    ...overrides,
  })
}

function makeOrder(id: number, items: Partial<OrderItemResponse>[]): OrderResponse {
  return {
    id,
    order_number: `ORD-${id}`,
    status: 'ordered',
    supplier_name: 'Supplier',
    items: items.map((i, index) => ({
      id: id * 100 + index,
      status: 'ordered',
      quantity: 1,
      unit: 'pcs',
      source_item_id: 5,
      project_id: 100,
      project_number: 'P-100',
      project_customer: 'ACME',
      project_description: 'Widget',
      project_status: 'active',
      ...i,
    })) as OrderItemResponse[],
  } as OrderResponse
}

/**
 * Mirrors the real route, constraint included, so the view reads its id the
 * same way it does in the app. See router/index.ts's `SourceItemDetail`.
 */
function makeRouter() {
  return makeTestRouter([
    {
      path: '/catalogue/source-items/:id(\\d+)',
      name: 'SourceItemDetail',
      component: SourceItemDetailView,
    },
  ])
}

async function mountView(
  id = 5,
  { storageEnabled = false, extraStubs = {} as Record<string, unknown> } = {},
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useHostStore().storageEnabled = storageEnabled

  const router = makeRouter()
  await router.push(`/catalogue/source-items/${id}`)
  await router.isReady()

  const wrapper = mountWithApp(SourceItemDetailView, {
    pinia,
    global: {
      plugins: [router, ConfirmationService],
      directives: { tooltip: Tooltip },
      // The dialogs a page can pop open drag in their own stores/APIs
      // (sourceItemsStore, suppliers, source-item-types, demand allocations,
      // OrderItemsTable, ...) that are irrelevant to what this spec covers,
      // stubbed the same way OrderDetailView.spec.ts stubs its own child
      // dialogs, so only the toolbar/info-bar/card wiring this page itself
      // owns is under test.
      stubs: {
        SourceItemDetailDialog: true,
        SourceItemDemandDetailDialog: true,
        OrderDetailDialog: true,
        ...extraStubs,
      },
    },
  })
  await flushPromises()
  return { wrapper, router }
}

/**
 * OpenVue's Tooltip directive stores the bound text as a plain property on
 * the target DOM element (`$_ptooltipValue`, set in `beforeMount`) rather
 * than an inspectable attribute. Reading it directly is simpler and more
 * reliable in jsdom than simulating a hover/show cycle.
 */
// A disabled button fires no mouse events, so its tooltip sits on the
// wrapping span.
function tooltipText(button: DOMWrapper<Element> | undefined): string | undefined {
  return (button?.element.parentElement as (Element & { $_ptooltipValue?: string }) | undefined)
    ?.$_ptooltipValue
}

describe('SourceItemDetailView', () => {
  beforeEach(() => {
    hasPermissionMock = () => true
    listMock.mockReset().mockResolvedValue({ items: [makeItem()], total: 1, limit: 1, skip: 0 })
    getSourceItemDemandsMock.mockReset().mockResolvedValue({ items: [], total: 0, limit: 200, skip: 0 })
    getSourceItemChangelogMock.mockReset().mockResolvedValue([])
    getOrdersMock.mockReset().mockResolvedValue({ items: [], total: 0 })
    getProjectsMock.mockReset().mockResolvedValue({ items: [], total: 0, limit: 200, skip: 0 })
    printDocumentsMock.mockReset()
    sourceItemFilesRef.current = SOURCE_ITEM_FILES
  })

  it('shows the dimension, status tag, and material | type in the info bar', async () => {
    listMock.mockResolvedValue({
      items: [makeItem({ dimension: 'D20x100', status: 'active', material: 'Steel S235', type_name: { enGB: 'Rod' } })],
      total: 1,
      limit: 1,
      skip: 0,
    })

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('D20x100')
    expect(wrapper.text()).toContain('Active')
    expect(wrapper.text()).toContain('Steel S235 | Rod')
  })

  it('falls back to #<id> in the info bar when the item has no dimension', async () => {
    listMock.mockResolvedValue({
      items: [makeItem({ id: 77, dimension: null })],
      total: 1,
      limit: 1,
      skip: 0,
    })

    const { wrapper } = await mountView(77)

    expect(wrapper.text()).toContain('#77')
  })

  it('shows the not-found screen when the item list comes back empty', async () => {
    listMock.mockResolvedValue({ items: [], total: 0, limit: 1, skip: 0 })

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('does not exist')
  })

  it('the back button navigates to the source items catalogue tab', async () => {
    const { wrapper, router } = await mountView()

    const backButton = wrapper.findAll('button').find((b) => b.text() === 'Back to Source Items')
    expect(backButton).toBeTruthy()
    await backButton!.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/catalogue/source-items')
  })

  it('disables Edit item without WRITE_SOURCE_ITEMS', async () => {
    hasPermissionMock = (permission) => permission !== Permission.WRITE_SOURCE_ITEMS

    const { wrapper } = await mountView()

    const editButton = wrapper.findAll('button').find((b) => b.text() === 'Edit item')
    expect(editButton?.attributes('disabled')).toBeDefined()
  })

  it('opens the edit dialog with editOnOpen when Edit item is clicked', async () => {
    const { wrapper } = await mountView()

    const editButton = wrapper.findAll('button').find((b) => b.text() === 'Edit item')
    await editButton!.trigger('click')

    const dialog = wrapper.findComponent({ name: 'SourceItemDetailDialog' })
    expect(dialog.exists()).toBe(true)
    expect(dialog.props('editOnOpen')).toBe(true)
    expect(dialog.props('visible')).toBe(true)
  })

  it('always disables Create demand and Add to order, with their explanatory tooltips', async () => {
    const { wrapper } = await mountView()

    const createDemandButton = wrapper.findAll('button').find((b) => b.text() === 'Create demand')
    expect(createDemandButton?.attributes('disabled')).toBeDefined()
    expect(tooltipText(createDemandButton)).toBe(
      "Source-item demands are created from a lot's material source.",
    )

    const addToOrderButton = wrapper.findAll('button').find((b) => b.text() === 'Add to order')
    expect(addToOrderButton?.attributes('disabled')).toBeDefined()
    expect(tooltipText(addToOrderButton)).toBe('Source items are ordered from their demands.')
  })

  it('prints a label through printDocuments with the source_item root and classifier', async () => {
    printDocumentsMock.mockResolvedValue([{ status: 'sent' }])

    const { wrapper } = await mountView()

    const printButton = wrapper.findAll('button').find((b) => b.text() === 'Print')
    expect(printButton).toBeTruthy()
    await printButton!.trigger('click')
    await flushPromises()

    const menu = wrapper.findComponent({ ref: 'printMenu' })
    const items = menu.props('model') as { label: string; command: () => void }[]
    const labelItem = items.find((i) => i.label === 'Label')
    expect(labelItem).toBeTruthy()

    labelItem!.command()
    await flushPromises()

    expect(printDocumentsMock).toHaveBeenCalledWith({
      root_type: 'source_item',
      root_id: 5,
      items: [{ classifier: 'source_item_label' }],
    })
  })

  it('prints a docket through printDocuments with the source_item_docket classifier', async () => {
    printDocumentsMock.mockResolvedValue([{ status: 'sent' }])

    const { wrapper } = await mountView()

    const printButton = wrapper.findAll('button').find((b) => b.text() === 'Print')
    await printButton!.trigger('click')
    await flushPromises()

    const menu = wrapper.findComponent({ ref: 'printMenu' })
    const items = menu.props('model') as { label: string; command: () => void }[]
    const docketItem = items.find((i) => i.label === 'Docket')
    expect(docketItem).toBeTruthy()

    docketItem!.command()
    await flushPromises()

    expect(printDocumentsMock).toHaveBeenCalledWith({
      root_type: 'source_item',
      root_id: 5,
      items: [{ classifier: 'source_item_docket' }],
    })
  })

  it('passes demand rows through to the demands card, with the lot number in the extra column', async () => {
    getSourceItemDemandsMock.mockResolvedValue({
      items: [makeDemand({ id: 9, lot_number: 'L-2026-001' })],
      total: 1,
      limit: 200,
      skip: 0,
    })

    const { wrapper } = await mountView()

    const text = wrapper.text()
    expect(text).toContain('#9')
    expect(text).toContain('L-2026-001')
  })

  it('passes order rows through to the orders card', async () => {
    getOrdersMock.mockResolvedValue({
      items: [makeOrder(11, [{ id: 1101, source_item_id: 5, quantity: 3, unit: 'pcs' }])],
      total: 1,
    })

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('ORD-11')
  })

  it('suppresses the Item card status tag - the info bar already shows it', async () => {
    const { wrapper } = await mountView()

    const fields = wrapper.findComponent(SourceItemDetailFields)
    expect(fields.exists()).toBe(true)
    expect(fields.props('showStatus')).toBe(false)
  })

  it('shows the Item card media and a pdf-only Files card when storage is enabled', async () => {
    listMock.mockResolvedValue({
      items: [makeItem({ dimension: 'D20x100', material: 'Steel S235', type_name: { enGB: 'Rod' } })],
      total: 1,
      limit: 1,
      skip: 0,
    })

    const { wrapper } = await mountView(5, { storageEnabled: true })

    const media = wrapper.findComponent(CatalogueItemMedia)
    expect(media.exists()).toBe(true)

    // The thumbnail cell in the media's default slot gets the same
    // dimension the placeholder-detection logic reads and the same summary
    // text the info bar shows (SourceItemDetailView's own `subLabel`).
    const thumb = wrapper.findComponent(SourceItemThumbnailCell)
    expect(thumb.exists()).toBe(true)
    expect(thumb.props('itemId')).toBe(5)
    expect(thumb.props('dimension')).toBe('D20x100')
    expect(thumb.props('itemName')).toBe('Steel S235 | Rod')

    // Files card: only pdf is listed (source items have no drawing/dxf/step
    // slots, and pictures are not files).
    const text = wrapper.text()
    expect(text).toContain('spec.pdf')
  })

  it('hides the media and Files card when storage is disabled', async () => {
    const { wrapper } = await mountView(5, { storageEnabled: false })

    expect(wrapper.findComponent(CatalogueItemMedia).exists()).toBe(false)
    expect(wrapper.text()).not.toContain('spec.pdf')
  })

  it('passes a shape-appropriate mesh placeholder to the media when no mesh file is on record', async () => {
    listMock.mockResolvedValue({
      items: [makeItem({ dimension: 'Ø20 × 100' })],
      total: 1,
      limit: 1,
      skip: 0,
    })

    const { wrapper } = await mountView(5, { storageEnabled: true })

    const media = wrapper.findComponent(CatalogueItemMedia)
    expect(media.exists()).toBe(true)
    expect(media.props('meshFile')).toBeNull()
    expect(media.props('meshPlaceholderUrl')).toBe(sourceItemPlaceholder('Ø20 × 100')?.mesh)
  })

  it('passes no mesh placeholder once a real mesh file is on record', async () => {
    sourceItemFilesRef.current = [
      ...SOURCE_ITEM_FILES,
      makeSourceItemFile({ id: 304, file_name: 'part.3mf', category: 'mesh' }),
    ]
    listMock.mockResolvedValue({
      items: [makeItem({ dimension: 'Ø20 × 100' })],
      total: 1,
      limit: 1,
      skip: 0,
    })

    // CatalogueItemMedia is stubbed for this one test only: with a real mesh
    // file on record it would fetch the file's bytes through MeshViewer's
    // real three.js/WebGL machinery, which jsdom can't support (same
    // reasoning as BoughtItemDetailView.spec.ts/MadeItemDetailView.spec.ts's
    // own fixtures never including a mesh file); the prop this test cares
    // about is set before any of that fetching happens either way.
    const { wrapper } = await mountView(5, {
      storageEnabled: true,
      extraStubs: { CatalogueItemMedia: true },
    })

    const media = wrapper.findComponent(CatalogueItemMedia)
    expect(media.exists()).toBe(true)
    expect(media.props('meshFile')).toMatchObject({ id: 304, file_name: 'part.3mf' })
    expect(media.props('meshPlaceholderUrl')).toBeNull()
  })

  it('sync refetches the item and every section', async () => {
    const { wrapper } = await mountView()
    listMock.mockClear()
    getSourceItemDemandsMock.mockClear()
    getOrdersMock.mockClear()
    getSourceItemChangelogMock.mockClear()

    const syncButton = wrapper.findAll('button').find((b) => b.text() === 'Sync')
    expect(syncButton).toBeTruthy()
    await syncButton!.trigger('click')
    await flushPromises()

    expect(listMock).toHaveBeenCalledTimes(1)
    expect(getSourceItemDemandsMock).toHaveBeenCalledTimes(1)
    expect(getOrdersMock).toHaveBeenCalledTimes(1)
    expect(getSourceItemChangelogMock).toHaveBeenCalledTimes(1)
  })
})
