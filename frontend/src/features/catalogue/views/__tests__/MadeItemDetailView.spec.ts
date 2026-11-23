import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { useHostStore } from '@/core/host/stores/hostStore'
import { RouteStub, makeTestRouter } from '@/test-utils/factories'

// One file per category so the Files-card-categories test (dxf/step/pdf
// only; mesh/drawing moved to the Item card's CatalogueItemMedia) can
// assert both what shows and what's excluded.
// Fetched through useMadeItemFilesStore, same store CatalogueItemMedia and
// CatalogueItemFilesCard both read. Uses `vi.hoisted` because the
// `@/core/api` mock factory below needs it and vi.mock factories are
// hoisted above normal module-scope consts.
const { MADE_ITEM_FILES } = vi.hoisted(() => {
  function file(overrides: Record<string, unknown>) {
    return {
      id: 0,
      public_id: 'ffffffff-0000-0000-0000-000000000000',
      made_item_id: 1,
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
  // No 'mesh' category file here on purpose: MeshViewer does real
  // three.js/WebGL work on mount that jsdom can't support, same reasoning
  // as LotRecordItem.spec.ts's own fixtures. CatalogueItemMedia.spec.ts
  // already covers the mesh-tile branch at the unit level.
  const MADE_ITEM_FILES = [
    file({ id: 104, file_name: 'drawing.pdf', mime_type: 'application/pdf', category: 'drawing' }),
    file({ id: 105, file_name: 'part.dxf', category: 'dxf' }),
    file({ id: 106, file_name: 'part.step', category: 'step' }),
    file({ id: 107, file_name: 'spec.pdf', mime_type: 'application/pdf', category: 'pdf' }),
  ]
  return { MADE_ITEM_FILES }
})

// Generic fallback for anything not mocked below (e.g. store refreshes
// triggered by a stubbed dialog's props). Mirrors BoughtItemDetailView.spec.ts
// / ProjectDetailView.spec.ts. `/made-items-files` (useMadeItemFilesStore's
// batched fetch, see createFilesStore.ts) gets real fixture files instead of
// the empty-page fallback so the Files-card-categories test below has
// something to filter.
vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<(url: string) => Promise<{ data: unknown }>>(async (url) => {
      if (url === '/made-items-files') return { data: MADE_ITEM_FILES }
      if (url.includes('/pictures')) return { data: [] }
      return { data: { items: [], total: 0 } }
    }),
  },
}))

const getMadeItemsMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/made-items/api/getMadeItems', () => ({
  getMadeItems: (...args: unknown[]) => getMadeItemsMock(...args),
}))

const getMadeItemDemandsMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/made-items/api/madeItemDemandsApi', () => ({
  getMadeItemDemands: (...args: unknown[]) => getMadeItemDemandsMock(...args),
}))

const getMadeItemChangelogMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/made-items/api/getMadeItemChangelog', () => ({
  getMadeItemChangelog: (...args: unknown[]) => getMadeItemChangelogMock(...args),
}))

const getMadeItemRevisionsMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/made-items/api/getMadeItemRevisions', () => ({
  getMadeItemRevisions: (...args: unknown[]) => getMadeItemRevisionsMock(...args),
}))

const getOrdersMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
// Partial mock (importOriginal): CatalogueItemOrdersCard (mounted for real
// below, so "orders reaching the cards" can be asserted against actual
// rendered output) reads useOrderFormatters from this same barrel, and
// OrderDetailDialog is imported by the view itself (stubbed via
// global.stubs, not this mock). Only getOrders is swapped.
vi.mock('@/features/orders', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/orders')>()
  return { ...actual, getOrders: (...args: unknown[]) => getOrdersMock(...args) }
})

const getLotsMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
// Partial mock, same reasoning as @/features/orders above: CatalogueItemLotsCard
// reads lotStatusSeverity from this barrel and the view itself reads
// useLotDetail. Only getLots is swapped.
vi.mock('@/features/production', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/production')>()
  return { ...actual, getLots: (...args: unknown[]) => getLotsMock(...args) }
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
  usePermissions: () => ({
    hasPermission: (...args: unknown[]) => hasPermissionMock(...(args as [])),
  }),
}))

const writeTextMock = vi.fn<(value: string) => Promise<void>>()
Object.assign(navigator, { clipboard: { writeText: writeTextMock } })

import MadeItemDetailView from '../MadeItemDetailView.vue'

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
    revision: 'A',
    article_name: 'Bracket',
    article_groups: [],
    data_source: 'WEB',
    material: null,
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
    source_item: null,
    processes: [],
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
    creator: {
      id: 1,
      public_id: 'u',
      username: 'jd',
      full_name: 'Jane Doe',
      email: 'j@x.com',
      has_avatar: false,
    },
    made_item_id: 1,
    item_part_number: 'PN-1',
    item_article_name: 'Bracket',
    project_id: 100,
    project_number: 'P-100',
    project_customer: 'ACME',
    project_description: 'Widget line',
    project_status: 'active',
    is_alteration: false,
    alteration_of_made_item_part_number: '',
    bucket_id: null,
    ...overrides,
  }
}

function makeOrder(id: number, items: unknown[]) {
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
    bought_item_id: null,
    source_item_id: null,
    virtual_name: null,
    item_order_code_1: '',
    item_order_code_2: null,
    item_specification: '',
    item_article_name: 'Bracket',
    item_part_number: 'PN-1',
    item_material: null,
    item_dimension: null,
    item_type_name: null,
    item_revision: null,
    item_base_size: null,
    item_mass: null,
    item_manufacturer: null,
    made_item_id: 1,
    order_id: 1,
    supplier_id: 1,
    supplier_name: 'Supplier Co',
    project_id: 100,
    project_number: 'P-100',
    project_customer: 'ACME',
    project_description: 'Widget line',
    project_status: 'active',
    line_type: 'made',
    lot_position_id: 1,
    lot_id: 1,
    lot_number: 'L-1',
    fabrication_method: '',
    ...overrides,
  }
}

function makeLot(overrides: Record<string, unknown> = {}) {
  return {
    id: 30,
    lot_number: 'L-2026-001',
    status: 'in_progress',
    quantity: 10,
    quantity_completed: 4,
    project_number: 'P-100',
    required_delivery_date: '2026-04-01',
    created: '2026-03-01',
    ...overrides,
  }
}

function makeRouter() {
  return makeTestRouter([
    {
      path: '/catalogue/made-items/:id(\\d+)',
      name: 'MadeItemDetail',
      component: MadeItemDetailView,
    },
    { path: '/catalogue/made-items', component: RouteStub },
  ])
}

const mounted: VueWrapper[] = []

async function mountView(
  id = '1',
  { productionPlanningEnabled = true, storageEnabled = false } = {},
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useHostStore().productionPlanningEnabled = productionPlanningEnabled
  useHostStore().storageEnabled = storageEnabled

  const router = makeRouter()
  await router.push(`/catalogue/made-items/${id}`)
  await router.isReady()

  const wrapper = mountWithApp(MadeItemDetailView, {
    pinia,
    global: {
      plugins: [router, ConfirmationService],
      directives: { tooltip: Tooltip },
      stubs: {
        MadeItemDetailDialog: true,
        MadeItemDemandCreateForm: true,
        MadeItemDemandDetailDialog: true,
        MadeItemProcessGrouping: true,
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
  getMadeItemsMock.mockResolvedValue({ items: [makeItem()], total: 1 })
  getMadeItemDemandsMock.mockResolvedValue({ items: [], total: 0 })
  getMadeItemChangelogMock.mockResolvedValue([])
  getMadeItemRevisionsMock.mockResolvedValue({
    items: [],
    next_revision: null,
    next_revision_error: null,
    can_create: true,
    reason: null,
  })
  getOrdersMock.mockResolvedValue({ items: [], total: 0 })
  getLotsMock.mockResolvedValue({ items: [], total: 0 })
  getProjectsMock.mockResolvedValue({ items: [], total: 0 })
  printDocumentsMock.mockResolvedValue([{ status: 'sent', error_message: null }])
}

describe('MadeItemDetailView', () => {
  beforeEach(() => {
    getMadeItemsMock.mockReset()
    getMadeItemDemandsMock.mockReset()
    getMadeItemChangelogMock.mockReset()
    getMadeItemRevisionsMock.mockReset()
    getOrdersMock.mockReset()
    getLotsMock.mockReset()
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
    getMadeItemsMock.mockResolvedValue({
      items: [makeItem({ part_number: 'PN-42', article_name: 'Steel Bracket', status: 'active' })],
      total: 1,
    })

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('PN-42')
    expect(wrapper.text()).toContain('Steel Bracket')
    expect(wrapper.text()).toContain('Active')
  })

  it('falls back to the empty placeholder in the info bar when part_number is unset', async () => {
    getMadeItemsMock.mockResolvedValue({
      items: [makeItem({ part_number: null })],
      total: 1,
    })

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('-')
  })

  it('shows the not-found screen when the item list comes back empty', async () => {
    getMadeItemsMock.mockResolvedValue({ items: [], total: 0 })

    const { wrapper } = await mountView('999')

    expect(wrapper.text()).toContain('This item does not exist or has been deleted.')
  })

  it('navigates back to the catalogue list', async () => {
    const { wrapper, router } = await mountView()

    const back = wrapper.findAll('button').find((b) => b.text() === 'Back to Made Items')
    expect(back).toBeTruthy()
    await back!.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/catalogue/made-items')
  })

  it('disables the Edit item button without WRITE_MADE_ITEMS', async () => {
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

    const dialog = wrapper.findComponent({ name: 'MadeItemDetailDialog' })
    expect(dialog.exists()).toBe(true)
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('editOnOpen')).toBe(true)
  })

  it('disables the Create demand button without WRITE_DEMAND_ITEMS', async () => {
    hasPermissionMock = () => false
    const { wrapper } = await mountView()

    const createDemandButton = wrapper.findAll('button').find((b) => b.text() === 'Create demand')
    expect(createDemandButton?.attributes('disabled')).toBeDefined()
  })

  it('keeps Add to order always disabled, with a tooltip, regardless of permission', async () => {
    hasPermissionMock = () => true
    const { wrapper } = await mountView()

    const addToOrderButton = wrapper.findAll('button').find((b) => b.text() === 'Add to order')
    expect(addToOrderButton).toBeTruthy()
    expect(addToOrderButton?.attributes('disabled')).toBeDefined()
    // A disabled button fires no mouse events, so the tooltip sits on its
    // wrapping span. v-tooltip's OpenVue directive stamps this marker
    // attribute on the element it's bound to. The actual floating panel only
    // mounts on hover/focus, so this is the reliable way to assert a tooltip
    // is wired without simulating pointer events.
    expect(addToOrderButton?.element.parentElement?.getAttribute('data-pd-tooltip')).toBe('true')
  })

  it('prints a label through printDocuments with the made-item root and classifier', async () => {
    const { wrapper } = await mountView()

    const menu = wrapper.findComponent({ ref: 'printMenu' })
    const items = menu.props('model') as { label: string; command: () => void }[]
    const labelItem = items.find((i) => i.label === 'Label')
    expect(labelItem).toBeDefined()

    labelItem!.command()
    await flushPromises()

    expect(printDocumentsMock).toHaveBeenCalledWith({
      root_type: 'made_item',
      root_id: 1,
      items: [{ classifier: 'made_item_label' }],
    })
  })

  it('prints a docket through printDocuments with the made-item docket classifier', async () => {
    const { wrapper } = await mountView()

    const menu = wrapper.findComponent({ ref: 'printMenu' })
    const items = menu.props('model') as { label: string; command: () => void }[]
    const docketItem = items.find((i) => i.label === 'Docket')
    expect(docketItem).toBeDefined()

    docketItem!.command()
    await flushPromises()

    expect(printDocumentsMock).toHaveBeenCalledWith({
      root_type: 'made_item',
      root_id: 1,
      items: [{ classifier: 'made_item_docket' }],
    })
  })

  it('passes the fetched demand and order rows through to the cards', async () => {
    getMadeItemDemandsMock.mockResolvedValue({
      items: [makeDemand({ id: 77, project_number: 'P-777' })],
      total: 1,
    })
    getOrdersMock.mockResolvedValue({
      items: [makeOrder(5, [makeOrderItem({ id: 88, made_item_id: 1 })])],
      total: 1,
    })

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('#77')
    expect(wrapper.text()).toContain('P-777')
    expect(wrapper.text()).toContain('ORD-5')
  })

  it('shows the item fields with the status tag suppressed', async () => {
    const { wrapper } = await mountView()

    const fields = wrapper.findComponent({ name: 'MadeItemDetailFields' })
    expect(fields.exists()).toBe(true)
    expect(fields.props('showStatus')).toBe(false)
  })

  it('renders the linked-source card in its own #source area, next to the Item card', async () => {
    getMadeItemsMock.mockResolvedValue({
      items: [makeItem({ id: 1, bought_item_id: 3, bought_item: null })],
      total: 1,
    })

    const { wrapper } = await mountView()

    const card = wrapper.findComponent({ name: 'MadeItemLinkedSourceCard' })
    expect(card.exists()).toBe(true)
    expect(card.props('item')).toMatchObject({ id: 1, bought_item_id: 3 })
    expect(wrapper.find('.area-source').exists()).toBe(true)
    expect(wrapper.text()).toContain('Material Source')
  })

  it('renders only the readonly process grouping in the Processes card - no editor', async () => {
    const { wrapper } = await mountView()

    expect(wrapper.findComponent({ name: 'MadeItemProcessEditor' }).exists()).toBe(false)

    const grouping = wrapper.findComponent({ name: 'MadeItemProcessGrouping' })
    expect(grouping.exists()).toBe(true)
    expect(grouping.props('readonly')).toBe(true)
    expect(grouping.props('showTimes')).toBe(true)
    expect(grouping.props('hideHint')).toBe(true)
  })

  it('shows the lots card when production planning is enabled', async () => {
    getLotsMock.mockResolvedValue({ items: [makeLot({ lot_number: 'L-VISIBLE' })], total: 1 })

    const { wrapper } = await mountView('1', { productionPlanningEnabled: true })

    expect(getLotsMock).toHaveBeenCalled()
    expect(wrapper.text()).toContain('L-VISIBLE')
  })

  it('hides the lots card and skips the request when production planning is disabled', async () => {
    const { wrapper } = await mountView('1', { productionPlanningEnabled: false })

    expect(getLotsMock).not.toHaveBeenCalled()
    expect(wrapper.text()).not.toContain('catalogue.itemDetail.cards.lots')
  })

  it('shows the Files card with only dxf/step/pdf files, and shows the drawing as a media tile instead', async () => {
    const { wrapper } = await mountView('1', { storageEnabled: true })

    const text = wrapper.text()
    // Files card: only the files the Item card's media does not show.
    expect(text).toContain('part.dxf')
    expect(text).toContain('part.step')
    expect(text).toContain('spec.pdf')
    // Everything the Item card's media shows is absent from the Files
    // card's own rows.
    expect(text).not.toContain('drawing.pdf')

    // The drawing tile itself: CatalogueItemMedia renders it as an
    // object-URL iframe once its fetch (through the same made-item files
    // store) settles.
    expect(wrapper.find('.media-tile--drawing').exists()).toBe(true)
  })

  it('shows the revision Select only when there is more than one revision, and navigates on pick', async () => {
    getMadeItemRevisionsMock.mockResolvedValue({
      items: [
        {
          id: 1,
          public_id: 'aaaaaaaa-0000-0000-0000-000000000001',
          revision: 'B',
          revision_date: null,
          status: 'active',
          successor_item_id: null,
          created: '2026-02-01',
          is_newest: true,
        },
        {
          id: 2,
          public_id: 'aaaaaaaa-0000-0000-0000-000000000002',
          revision: 'A',
          revision_date: null,
          status: 'replaced',
          successor_item_id: 1,
          created: '2026-01-01',
          is_newest: false,
        },
      ],
      next_revision: 'C',
      next_revision_error: null,
      can_create: true,
      reason: null,
    })

    const { wrapper, router } = await mountView()

    const select = wrapper.findComponent({ name: 'Select' })
    expect(select.exists()).toBe(true)

    await select.vm.$emit('update:modelValue', 2)
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/catalogue/made-items/2')
  })

  it('hides the revision Select when the item has no sibling revisions', async () => {
    const { wrapper } = await mountView()

    expect(wrapper.findComponent({ name: 'Select' }).exists()).toBe(false)
  })

  // ── "Not newest" revision notice: shown on the page itself (not just the edit dialog) so it doesn't take a failed save to notice ──────────

  it('shows the not-newest notice with the newest revision label when this item is not the newest', async () => {
    getMadeItemRevisionsMock.mockResolvedValue({
      items: [
        {
          id: 1,
          public_id: 'aaaaaaaa-0000-0000-0000-000000000001',
          revision: 'A',
          revision_date: null,
          status: 'replaced',
          successor_item_id: 2,
          created: '2026-01-01',
          is_newest: false,
        },
        {
          id: 2,
          public_id: 'aaaaaaaa-0000-0000-0000-000000000002',
          revision: 'B',
          revision_date: null,
          status: 'active',
          successor_item_id: null,
          created: '2026-02-01',
          is_newest: true,
        },
      ],
      next_revision: 'C',
      next_revision_error: null,
      can_create: true,
      reason: null,
    })

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain(
      i18n.global.t('madeItems.edit.notNewestNotice', { revision: 'B' }),
    )
  })

  it('does not show the not-newest notice when this item is the newest', async () => {
    const { wrapper } = await mountView()

    expect(wrapper.findComponent({ name: 'Message' }).exists()).toBe(false)
  })

  it('refetches on sync', async () => {
    const { wrapper } = await mountView()

    getMadeItemsMock.mockClear()
    const syncButton = wrapper.findAll('button').find((b) => b.text() === 'Sync')
    expect(syncButton).toBeTruthy()
    await syncButton!.trigger('click')
    await flushPromises()

    expect(getMadeItemsMock).toHaveBeenCalledTimes(1)
  })
})
