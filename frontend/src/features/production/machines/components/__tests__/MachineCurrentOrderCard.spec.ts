import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { flushPromises, RouterLinkStub } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeLotResponse, makeProductionOrderResponse } from '@/test-utils/factories'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { useHostStore } from '@/core/host/stores/hostStore'
import { makePosition } from '../../../lots/__tests__/fixtures'

import type { ProductionOrderResponse } from '../../../types/productionOrdersResponse'
import type { LotResponse } from '../../../types/productionLotsResponse'
import type { MadeItemFile, MadeItemResponse } from '@/features/made-items'
import type {
  SourceItemDemandResponse,
  SourceItemDemandSummaryResponse,
  SourceItemFile,
  SourceItemResponse,
} from '@/features/source-items'
import type { PublicUser } from '@/core/types/userResponse'

// Fixtures the axios mock below serves, hoisted alongside it since a
// vi.mock factory only sees hoisted bindings.
const { madeItemFilesFixture, sourceItemFilesFixture } = vi.hoisted(() => {
  const madeItemFilesFixture: MadeItemFile[] = [
    {
      id: 2,
      public_id: 'aaaaaaaa-0000-0000-0000-000000000002',
      made_item_id: 900,
      file_name: 'drawing.pdf',
      stored_name: 'drawing.pdf',
      mime_type: 'application/pdf',
      size_bytes: 20,
      storage_path: '',
      sha256: '',
      category: 'drawing',
      created: '2026-07-01',
      uploaded_by_user_id: 1,
      url: null,
      from_pdm: false,
    },
  ]

  const sourceItemFilesFixture: SourceItemFile[] = [
    {
      id: 11,
      public_id: 'bbbbbbbb-0000-0000-0000-000000000011',
      source_item_id: 501,
      file_name: 'certificate.pdf',
      stored_name: 'certificate.pdf',
      mime_type: 'application/pdf',
      size_bytes: 30,
      storage_path: '',
      sha256: '',
      category: 'pdf',
      created: '2026-07-01',
      uploaded_by_user_id: 1,
      url: null,
    },
  ]

  return { madeItemFilesFixture, sourceItemFilesFixture }
})

// Mocked at the axios boundary, same idiom as MachineDetailContent.spec.ts:
// the files stores/blob fetchers/source-item lookup/demand+summary lookup
// all end up calling the same underlying instance.
const getMock =
  vi.fn<(url: string, config?: { params?: Record<string, unknown> }) => Promise<{ data: unknown }>>()
const postMock = vi.fn<(url: string, body?: unknown) => Promise<{ data: unknown }>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string, config?: { params?: Record<string, unknown> }) => getMock(url, config),
    post: (url: string, body?: unknown) => postMock(url, body),
  },
}))

import MachineCurrentOrderCard from '../MachineCurrentOrderCard.vue'

function makeOrder(
  overrides: Partial<ProductionOrderResponse> & { id: number },
): ProductionOrderResponse {
  return makeProductionOrderResponse({
    public_id: `33333333-3333-3333-3333-${String(overrides.id).padStart(12, '0')}`,
    production_order_number: `PO-${overrides.id}`,
    status: 'in_progress',
    queue_sequence: overrides.id,
    quantity_completed: 4,
    started_operator_id: null,
    started_operator: null,
    lot_id: overrides.id,
    lot_number: `LOT-${overrides.id}`,
    made_item_id: 900,
    ...overrides,
  })
}

function makeLot(overrides: Partial<LotResponse> & { id: number }): LotResponse {
  return makeLotResponse({
    public_id: `44444444-0000-0000-0000-${String(overrides.id).padStart(12, '0')}`,
    lot_number: `LOT-${overrides.id}`,
    made_item_id: 900,
    project_id: 1,
    project_number: 'PRJ-1',
    ...overrides,
  })
}

function makeMadeItem(overrides: Partial<MadeItemResponse> = {}): MadeItemResponse {
  return {
    id: 900,
    public_id: 'bbbbbbbb-0000-0000-0000-000000000900',
    part_number: 'PN-900',
    status: 'active',
    created: '2026-02-01',
    changed: '2026-02-01T00:00:00Z',
    archived: false,
    revision: 'A',
    revision_date: null,
    revision_note: null,
    article_name: 'Bracket 900',
    article_groups: [],
    data_source: 'WEB',
    material: '1.0037',
    mass: 1.25,
    base_size: '100x50',
    note: null,
    weblink: null,
    successor_item_id: null,
    creator_id: 1,
    creator: null,
    bought_item_id: null,
    bought_item: null,
    source_item_id: null,
    source_item: null,
    source_label: '',
    source_sublabel: '',
    processes: [],
    ...overrides,
  } as MadeItemResponse
}

function makeSourceItem(overrides: Partial<SourceItemResponse> & { id: number }): SourceItemResponse {
  return {
    edit_version: 0,
    over_delivery_tolerance_percent: null,
    under_delivery_tolerance_percent: null,
    public_id: `cccccccc-0000-0000-0000-${String(overrides.id).padStart(12, '0')}`,
    status: 'active',
    created: '2026-01-01',
    changed: '2026-01-01T00:00:00Z',
    changed_by_id: null,
    changed_by: null,
    archived: false,
    type_id: 1,
    type_name: { enGB: 'Round Bar' },
    dimension: 'Ø20',
    material: '1.4301',
    mass: 2.5,
    note: null,
    order_code_1: null,
    order_code_2: null,
    successor_item_id: null,
    creator_id: 1,
    creator: null,
    approver_id: null,
    manufacturer_id: null,
    manufacturer_name: '',
    ...overrides,
  }
}

function makeDemand(
  overrides: Partial<SourceItemDemandResponse> & { id: number },
): SourceItemDemandResponse {
  return {
    public_id: `dddddddd-0000-0000-0000-${String(overrides.id).padStart(12, '0')}`,
    status: 'ordered',
    created: '2026-01-01',
    changed: null,
    changed_by_id: null,
    changed_by: null,
    quantity: 10,
    unit: 'pcs',
    items_per_unit: 1,
    high_priority: false,
    notify_on_delivery: false,
    note: null,
    desired_delivery_date: null,
    creator_id: 1,
    creator: null,
    bought_item_id: null,
    bought_item: null,
    source_item_id: null,
    source_item: null,
    lot_id: 1,
    lot_number: 'LOT-1',
    project_id: 1,
    project_number: 'PRJ-1',
    project_customer: '',
    project_description: '',
    project_status: 'active',
    bucket_id: null,
    actions: [],
    canceled_at: null,
    fulfilled_manually_at: null,
    ...overrides,
  }
}

function makeSummary(
  overrides: Partial<SourceItemDemandSummaryResponse> = {},
): SourceItemDemandSummaryResponse {
  return {
    demand_item_id: 1,
    unit: 'pcs',
    total: 10,
    allocated: 6,
    fulfilled_from_stock: 0,
    ordered: 6,
    delivered: 2,
    remaining: 4,
    unallocated: 4,
    pending: 0,
    in_transit: 4,
    is_fully_allocated: false,
    is_fully_delivered: false,
    unit_mismatch: false,
    order_ids: [],
    order_numbers: [],
    substitutions: [],
    ...overrides,
  }
}

const OPERATOR: PublicUser = {
  id: 5,
  public_id: 'eeeeeeee-0000-0000-0000-000000000005',
  username: 'jane',
  full_name: 'Jane Operator',
  has_avatar: false,
}

// ── Fixture-backed HTTP mock ─────────────────────────────────────────────
let sourceItemsFixture: SourceItemResponse[] = []
let sourceItemDemandFixture: SourceItemDemandResponse | null = null
let sourceItemDemandSummaryFixture: SourceItemDemandSummaryResponse | null = null
// Overrides madeItemFilesFixture for one test (a mesh file, an empty list, ...):
// null means "use the default fixture". A fixture variable rather than a
// one-off getMock.mockImplementation() override: this file's earlier
// mounted wrappers are never explicitly unmounted (same as every other spec
// here), so a raw override left a later test's own beforeEach-reset mock
// racing a still-settling promise from an earlier test's stale watcher.
let madeItemFilesOverride: MadeItemFile[] | null = null

function setupApiMock(): void {
  getMock.mockReset()
  postMock.mockReset()

  getMock.mockImplementation((url, config) => {
    if (url === '/made-items-files') {
      return Promise.resolve({ data: madeItemFilesOverride ?? madeItemFilesFixture })
    }
    if (url.includes('pictures')) return Promise.resolve({ data: [] })
    if (/^\/made-items\/\d+\/files\/\d+$/.test(url)) {
      return Promise.resolve({ data: new Blob(['x'], { type: 'image/png' }) })
    }
    if (url === '/source-items') {
      const id = config?.params?.id as number | undefined
      const item = sourceItemsFixture.find((i) => i.id === id) ?? null
      return Promise.resolve({
        data: { items: item ? [item] : [], total: item ? 1 : 0, limit: 1, skip: 0 },
      })
    }
    if (url === '/source-items-files') {
      return Promise.resolve({ data: sourceItemFilesFixture })
    }
    if (/^\/source-items\/\d+\/files\/\d+$/.test(url)) {
      return Promise.resolve({ data: new Blob(['x'], { type: 'application/pdf' }) })
    }
    if (/^\/source-item-demands\/\d+$/.test(url)) {
      return sourceItemDemandFixture
        ? Promise.resolve({ data: sourceItemDemandFixture })
        : Promise.reject(new Error('not found'))
    }
    return Promise.resolve({ data: {} })
  })

  postMock.mockImplementation((url, body) => {
    if (url === '/source-item-allocations/demands/summary-batch') {
      const ids = body as number[]
      const record: Record<number, SourceItemDemandSummaryResponse> = {}
      for (const id of ids) {
        if (sourceItemDemandSummaryFixture) record[id] = sourceItemDemandSummaryFixture
      }
      return Promise.resolve({ data: record })
    }
    return Promise.resolve({ data: {} })
  })
}

function mountCard(props: {
  orders: ProductionOrderResponse[]
  madeItem?: MadeItemResponse | null
  itemLoading?: boolean
  processMethod?: string | null
  lot?: LotResponse | null
}) {
  // A fresh Pinia per mount (same instance handed to hostStore below and to
  // mountWithApp) rather than mountWithApp's own default: the card's file
  // fetches (made-item and source-item alike) are gated behind
  // hostStore.storageEnabled, same guard LotRecordItem.vue uses.
  const pinia = createPinia()
  setActivePinia(pinia)
  useHostStore().storageEnabled = true

  return mountWithApp(MachineCurrentOrderCard, {
    pinia,
    props: {
      orders: props.orders,
      madeItem: props.madeItem ?? null,
      itemLoading: props.itemLoading ?? false,
      processMethod: props.processMethod ?? null,
      lot: props.lot ?? null,
    },
    global: {
      directives: { tooltip: Tooltip },
      // MeshViewer stubbed the same way MachineFileStrip.spec.ts stubs it:
      // jsdom has no WebGL context, so the real three.js-backed component
      // throws (an unhandled rejection, not a test failure, but noisy and
      // the async component may not even resolve in time either way).
      stubs: { RouterLink: RouterLinkStub, MeshViewer: true },
    },
  })
}

beforeEach(() => {
  sourceItemsFixture = []
  sourceItemDemandFixture = null
  sourceItemDemandSummaryFixture = null
  madeItemFilesOverride = null
  setupApiMock()
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('MachineCurrentOrderCard', () => {
  it('shows the idle empty state when there is no current order', () => {
    const wrapper = mountCard({ orders: [] })

    expect(wrapper.text()).toContain('No order running right now.')
    expect(wrapper.findComponent({ name: 'MadeItemDetailFields' }).exists()).toBe(false)
  })

  it("renders the made item label as the headline, the PO number in a meta row, and status/priority tags/quantity/process", async () => {
    const order = makeOrder({
      id: 10,
      status: 'in_progress',
      priority: 'high',
      quantity: 20,
      quantity_completed: 5,
      made_item_part_number: 'PN-10',
      made_item_revision: 'B',
    })

    const wrapper = mountCard({ orders: [order], processMethod: 'Milling' })
    await flushPromises()

    const headline = wrapper.find('.hero-headline').text()
    expect(headline).toContain('PN-10')
    expect(headline).toContain('B')
    expect(headline).not.toContain('PO-10')

    expect(wrapper.text()).toContain('PO-10')
    expect(wrapper.text()).toContain('Milling')

    // Quantity is a plain meta-row: no progress bar, no percent.
    const quantityRow = wrapper
      .findAll('.meta-row')
      .find((row) => row.find('.meta-label').text() === 'Quantity')
    expect(quantityRow?.find('.meta-value').text()).toBe('5 / 20')
    expect(wrapper.text()).not.toContain('25%')
    expect(wrapper.findComponent({ name: 'ProgressBar' }).exists()).toBe(false)

    const statusTags = wrapper.findAllComponents({ name: 'Tag' })
    expect(statusTags.some((tg) => tg.props('value') === 'In Progress')).toBe(true)
    expect(statusTags.some((tg) => tg.props('value') === 'High')).toBe(true)
  })

  it(
    'shows the estimated duration bracketed with the position setup total when one exists, ' +
      'and no bracket when the position has no setup time (or no position at all)',
    () => {
      const noPosition = mountCard({
        orders: [makeOrder({ id: 80, lot_id: 8000, lot_position_id: 1, estimated_duration_minutes: 90 })],
        lot: makeLot({ id: 8000, positions: [] }),
      })
      const noPositionRow = noPosition
        .findAll('.meta-row')
        .find((row) => row.find('.meta-label').text() === 'Estimated')
      expect(noPositionRow?.find('.meta-value').text()).toBe('1 h 30 min')

      const zeroSetupPosition = makePosition({ id: 1, lot_id: 8001 })
      const zeroSetup = mountCard({
        orders: [
          makeOrder({ id: 81, lot_id: 8001, lot_position_id: 1, estimated_duration_minutes: 90 }),
        ],
        lot: makeLot({ id: 8001, positions: [zeroSetupPosition] }),
      })
      const zeroSetupRow = zeroSetup
        .findAll('.meta-row')
        .find((row) => row.find('.meta-label').text() === 'Estimated')
      // The default fixture step's estimated_setup_minutes is null; summed
      // total is 0, so the bracket stays hidden rather than reading "+0 min".
      expect(zeroSetupRow?.find('.meta-value').text()).toBe('1 h 30 min')

      const setupPosition = makePosition({ id: 1, lot_id: 8002 })
      setupPosition.steps = [
        { ...setupPosition.steps![0]!, id: 1, estimated_setup_minutes: 20 },
        { ...setupPosition.steps![0]!, id: 2, estimated_setup_minutes: 25 },
      ]
      const withSetup = mountCard({
        orders: [
          makeOrder({ id: 82, lot_id: 8002, lot_position_id: 1, estimated_duration_minutes: 150 }),
        ],
        lot: makeLot({ id: 8002, positions: [setupPosition] }),
      })
      const withSetupRow = withSetup
        .findAll('.meta-row')
        .find((row) => row.find('.meta-label').text() === 'Estimated')
      // Summed across both of the position's steps (20 + 25), same as
      // buildTimeComparison's own estimatedSetup total, not just the one
      // step nearest the order.
      expect(withSetupRow?.find('.meta-value').text()).toBe('2 h 30 min (+45 min Setup)')
    },
  )

  it("shows who started the order, and a dash when no operator is recorded", () => {
    const started = mountCard({ orders: [makeOrder({ id: 15, started_operator: OPERATOR })] })
    const startedRow = started
      .findAll('.meta-row')
      .find((row) => row.find('.meta-label').text() === 'Started by')
    expect(startedRow?.find('.meta-value').text()).toBe('Jane Operator')

    const notStarted = mountCard({ orders: [makeOrder({ id: 16, started_operator: null })] })
    const notStartedRow = notStarted
      .findAll('.meta-row')
      .find((row) => row.find('.meta-label').text() === 'Started by')
    expect(notStartedRow?.find('.meta-value').text()).toBe(getEmptyPlaceholder())
  })

  it('links the project field to its workspace page and keeps the lot link/step number identity fields', () => {
    const order = makeOrder({
      id: 17,
      lot_id: 1700,
      lot_number: 'LOT-1700',
      lot_position_sequence: 2,
      lot_position_count: 3,
    })
    const lot = makeLot({ id: 1700, project_id: 88, project_number: 'PRJ-88' })

    const wrapper = mountCard({ orders: [order], lot })

    const projectLink = wrapper.findComponent(RouterLinkStub)
    expect(projectLink.props('to')).toBe('/workspace/projects/88')
    expect(projectLink.text()).toContain('PRJ-88')

    expect(wrapper.text()).toContain('LOT-1700')
    expect(wrapper.text()).toContain('#2 of 3')
  })

  it('shows a pinned indicator only when the primary order is pinned', () => {
    const pinned = mountCard({ orders: [makeOrder({ id: 11, pinned: true })] })
    expect(pinned.find('.hero-pin').exists()).toBe(true)

    const unpinned = mountCard({ orders: [makeOrder({ id: 12, pinned: false })] })
    expect(unpinned.find('.hero-pin').exists()).toBe(false)
  })

  it('shows the order note only when present', () => {
    const withNote = mountCard({ orders: [makeOrder({ id: 13, note: 'Handle with care' })] })
    expect(withNote.text()).toContain('Handle with care')

    const withoutNote = mountCard({ orders: [makeOrder({ id: 14, note: null })] })
    expect(withoutNote.text()).not.toContain('Handle with care')
  })

  it('renders additional current orders (beyond the primary) as compact one-line rows only', () => {
    const primary = makeOrder({ id: 20, status: 'in_progress', lot_number: 'LOT-20' })
    const extra = makeOrder({
      id: 21,
      status: 'paused',
      lot_number: 'LOT-21',
      quantity: 8,
      quantity_completed: 2,
    })

    const wrapper = mountCard({ orders: [primary, extra] })

    expect(wrapper.text()).toContain('PO-21')
    expect(wrapper.text()).toContain('2 / 8')
    // The compact row is number + status + qty only, no lot link for it.
    expect(wrapper.text()).not.toContain('LOT-21')
  })

  it('shows a skeleton while the item is loading, and MadeItemDetailFields once loaded', async () => {
    const order = makeOrder({ id: 30 })

    const loading = mountCard({ orders: [order], itemLoading: true, madeItem: null })
    expect(loading.findComponent({ name: 'Skeleton' }).exists()).toBe(true)
    expect(loading.findComponent({ name: 'MadeItemDetailFields' }).exists()).toBe(false)

    const item = makeMadeItem({ article_name: 'Bracket 900' })
    const loaded = mountCard({ orders: [order], itemLoading: false, madeItem: item })
    await flushPromises()

    expect(loaded.findComponent({ name: 'MadeItemDetailFields' }).exists()).toBe(true)
    expect(loaded.text()).toContain('Bracket 900')
  })

  it('the lot link opens the lot detail dialog via useLotDetail', async () => {
    const order = makeOrder({ id: 40, lot_id: 4040, lot_number: 'LOT-40' })
    const wrapper = mountCard({ orders: [order] })

    const { useLotDetail } = await import('@/shared/composables/useLotDetail')
    const { lotId, visible } = useLotDetail()

    await wrapper.find('.lot-link').trigger('click')

    expect(visible.value).toBe(true)
    expect(lotId.value).toBe(4040)
  })

  it("renders one box per made-item file, positioned above the item section, and opens the preview dialog on click", async () => {
    const order = makeOrder({ id: 50, made_item_id: 900 })
    const wrapper = mountCard({ orders: [order], lot: makeLot({ id: 50 }) })
    await flushPromises()
    await flushPromises()

    // The strip sits above the "Item" section label itself, as a sibling of
    // .item-section rather than inside it.
    const strip = wrapper.find('.item-file-strip')
    expect(strip.exists()).toBe(true)
    expect(wrapper.find('.item-section').find('.file-box').exists()).toBe(false)

    const html = wrapper.html()
    expect(html.indexOf('item-file-strip')).toBeLessThan(html.indexOf('item-section'))

    // The fixture carries a drawing (id 2), the one strip box. The picture
    // is not a file; the hero tile shows it.
    const boxes = strip.findAll('.file-box')
    expect(boxes).toHaveLength(1)

    await boxes[0]!.trigger('click')
    await flushPromises()

    const dialog = wrapper.findComponent({ name: 'FilePreviewDialog' })
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('filename')).toBe(madeItemFilesFixture[0]!.file_name)
    expect(dialog.props('mimeType')).toBe(madeItemFilesFixture[0]!.mime_type)
  })

  it('excludes the mesh file from the strip while the hero media tile is showing it', async () => {
    const meshFile: MadeItemFile = {
      id: 3,
      public_id: 'aaaaaaaa-0000-0000-0000-000000000003',
      made_item_id: 900,
      file_name: 'part.stl',
      stored_name: 'part.stl',
      mime_type: 'model/stl',
      size_bytes: 40,
      storage_path: '',
      sha256: '',
      category: 'mesh',
      created: '2026-07-01',
      uploaded_by_user_id: 1,
      url: null,
      from_pdm: false,
    }
    madeItemFilesOverride = [...madeItemFilesFixture, meshFile]

    // No `lot`, so the source-item side of the card never fetches anything;
    // only the made-item files above are exercised by this test.
    const order = makeOrder({ id: 51, made_item_id: 900 })
    const wrapper = mountCard({ orders: [order] })
    await flushPromises()
    await flushPromises()
    await flushPromises()

    // The hero shows the mesh viewer (not the picture fallback)...
    expect(wrapper.find('.hero-media-tile').findComponent({ name: 'MeshViewer' }).exists()).toBe(
      true,
    )
    // ...and the strip below does not carry the mesh file it would
    // duplicate, only the drawing.
    const boxes = wrapper.find('.item-file-strip').findAll('.file-box')
    expect(boxes).toHaveLength(1)

    // Unmounted explicitly (unlike every other test in this file): the mesh
    // watch chain is otherwise left mid-flight, and later tests' own
    // flushPromises() calls would settle it against whatever getMock/fixture
    // is current by then, not what this test set up.
    wrapper.unmount()
  })

  it('the hero media tile is clickable and opens the mesh file preview when a mesh is shown', async () => {
    const order = makeOrder({ id: 52, made_item_id: 900 })
    madeItemFilesOverride = [
      {
        ...madeItemFilesFixture[0]!,
        id: 4,
        category: 'mesh',
        file_name: 'part.stl',
        mime_type: 'model/stl',
      },
    ]

    const wrapper = mountCard({ orders: [order] })
    await flushPromises()
    await flushPromises()
    await flushPromises()

    const tile = wrapper.find('.hero-media-tile')
    expect(tile.attributes('role')).toBe('button')
    expect(tile.attributes('tabindex')).toBe('0')

    await tile.trigger('click')
    await flushPromises()

    const dialog = wrapper.findComponent({ name: 'FilePreviewDialog' })
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('filename')).toBe('part.stl')
    expect(dialog.props('mimeType')).toBe('model/stl')

    wrapper.unmount()
  })

  it('the hero media tile falls back to the picture when there is no mesh, and stays non-interactive without one', async () => {
    // No mesh and no picture at all; the tile must not be clickable.
    const order = makeOrder({ id: 53, made_item_id: 900 })
    madeItemFilesOverride = []

    const wrapper = mountCard({ orders: [order] })
    await flushPromises()
    await flushPromises()

    const tile = wrapper.find('.hero-media-tile')
    expect(tile.attributes('role')).toBeUndefined()
    expect(tile.attributes('tabindex')).toBeUndefined()
    expect(tile.findComponent({ name: 'MadeItemThumbnailCell' }).exists()).toBe(true)

    wrapper.unmount()
  })

  it('opens the made item detail dialog from the header button, disabled while there is no made item', async () => {
    const order = makeOrder({ id: 54, made_item_id: 900 })
    const item = makeMadeItem({ article_name: 'Bracket 900' })

    const noItem = mountCard({ orders: [order], madeItem: null })
    await flushPromises()
    const noItemButton = noItem.find('button[aria-label="View item details"]')
    expect(noItemButton.exists()).toBe(true)
    expect(noItemButton.attributes('disabled')).toBeDefined()

    const wrapper = mountCard({ orders: [order], madeItem: item })
    await flushPromises()

    const openButton = wrapper.find('button[aria-label="View item details"]')
    expect(openButton.exists()).toBe(true)
    expect(openButton.attributes('disabled')).toBeUndefined()

    await openButton.trigger('click')

    const dialog = wrapper.findComponent({ name: 'MadeItemDetailDialog' })
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('item')).toEqual(item)

    // Left open (visible=true) otherwise: MadeItemDetailDialog fetches its
    // own revisions list once open, and that pending request would settle
    // mid-flight during a later test's flushPromises() calls.
    noItem.unmount()
    wrapper.unmount()
  })

  it('renders no source section while the lot has not loaded yet', () => {
    const wrapper = mountCard({ orders: [makeOrder({ id: 55 })], lot: null })
    expect(wrapper.find('.source-section').exists()).toBe(false)
  })

  it(
    'resolves a stock source item into SourceItemDetailFields, its procurement state, ' +
      'the demand status tag, and the demand summary quantities',
    async () => {
      sourceItemsFixture = [makeSourceItem({ id: 501, type_name: { enGB: 'Round Bar' }, material: '1.4301' })]
      sourceItemDemandFixture = makeDemand({ id: 900, status: 'ordered', source_item_id: 501 })
      sourceItemDemandSummaryFixture = makeSummary({
        ordered: 6,
        in_transit: 4,
        delivered: 2,
        remaining: 4,
      })

      const order = makeOrder({ id: 60, lot_id: 6000 })
      const lot = makeLot({
        id: 6000,
        source_item_id: 501,
        source_order_id: 77,
        source_order_number: 'SO-77',
        input_demand_id: 900,
      })

      const wrapper = mountCard({ orders: [order], lot })
      await flushPromises()
      await flushPromises()
      await flushPromises()

      expect(wrapper.findComponent({ name: 'SourceItemDetailFields' }).exists()).toBe(true)
      expect(wrapper.text()).toContain('Round Bar')
      expect(wrapper.text()).toContain('SO-77')

      const tags = wrapper.findAllComponents({ name: 'Tag' })
      expect(tags.some((tg) => tg.props('value') === 'Ordered')).toBe(true)

      const summaryGrid = wrapper.find('.demand-summary-grid')
      expect(summaryGrid.exists()).toBe(true)
      expect(summaryGrid.text()).toContain('6')
      expect(summaryGrid.text()).toContain('4')
      expect(summaryGrid.text()).toContain('2')

      const sourceBoxes = wrapper.find('.source-section').findAll('.file-box')
      expect(sourceBoxes).toHaveLength(sourceItemFilesFixture.length)

      // The strip sits at the top of the source section, above
      // SourceItemDetailFields (whose "Round Bar" type name renders further
      // down the section).
      const html = wrapper.html()
      expect(html.indexOf('file-box')).toBeLessThan(html.indexOf('Round Bar'))
    },
  )

  it('falls back to the lot source label/sublabel line (no fields grid, no file strip) for a non-stock source', () => {
    const order = makeOrder({ id: 70, lot_id: 7000 })
    const lot = makeLot({
      id: 7000,
      source_item_id: null,
      source_bought_item_id: 55,
      source_label: 'Bolt M6x20',
      source_sublabel: 'DIN 912',
    })

    const wrapper = mountCard({ orders: [order], lot })

    expect(wrapper.findComponent({ name: 'SourceItemDetailFields' }).exists()).toBe(false)
    expect(wrapper.find('.source-fallback').text()).toContain('Bolt M6x20')
    expect(wrapper.find('.source-fallback').text()).toContain('DIN 912')
    expect(wrapper.find('.source-section').findAll('.file-box')).toHaveLength(0)
  })
})
