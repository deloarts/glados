/**
 * Made-item counterpart of the bought-item and source-item
 * manageOrderFilter specs. The Manage Lots panel narrows the demand list to
 * rows that still need lots (`not_fully_allocated`).
 *
 * The last test here guards against a status-based preselect (`statuses:
 * ['open', 'allocated']`) reappearing: 'allocated' is set by *any* coverage,
 * so a status-based preselect would keep fully covered demands in the list.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import OpenVue from 'openvue/config'
import ToastService from 'openvue/toastservice'
import ConfirmationService from 'openvue/confirmationservice'
import Aura from '@openvue/themes/aura'

import { i18n } from '@/core/i18n'

const get =
  vi.fn<(url: string, config?: { params?: Record<string, unknown> }) => Promise<unknown>>()
const post = vi.fn<() => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string, config?: { params?: Record<string, unknown> }) => get(url, config),
    post: () => post(),
    put: vi.fn<() => Promise<unknown>>(),
    patch: vi.fn<() => Promise<unknown>>(),
    delete: vi.fn<() => Promise<unknown>>(),
  },
}))

import MadeItemsDemandsTable from '../MadeItemsDemandsTable.vue'
import { useMadeItemsDemandsFiltersStore } from '../../stores/madeItemsDemandsFiltersStore'

function demandRequestParams(): Record<string, unknown>[] {
  return get.mock.calls
    .filter(([url]) => url === '/made-items-demands')
    .map(([, config]) => config?.params ?? {})
}

function mountTable() {
  return mount(MadeItemsDemandsTable, {
    global: {
      plugins: [[OpenVue, { theme: { preset: Aura } }], ToastService, ConfirmationService, i18n],
    },
  })
}

describe('MadeItemsDemandsTable manage-lots filter', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    get.mockReset()
    post.mockReset()
    get.mockResolvedValue({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    post.mockResolvedValue({ data: {} })
  })

  it('does not narrow the list while the panel is closed', async () => {
    mountTable()
    await flushPromises()

    const params = demandRequestParams()
    expect(params.length).toBeGreaterThan(0)
    expect(params.every((p) => p.not_fully_allocated === undefined)).toBe(true)
  })

  it('requests only not-fully-allocated demands once the panel opens', async () => {
    mountTable()
    await flushPromises()

    const filtersStore = useMadeItemsDemandsFiltersStore()
    const before = demandRequestParams().length
    filtersStore.toggleManageLotsPanel()
    await flushPromises()

    const params = demandRequestParams()
    expect(params.length).toBeGreaterThan(before)
    expect(params.at(-1)).toMatchObject({ not_fully_allocated: true })
  })

  it('restores the full list when the panel closes again', async () => {
    mountTable()
    await flushPromises()

    const filtersStore = useMadeItemsDemandsFiltersStore()
    filtersStore.toggleManageLotsPanel()
    await flushPromises()
    filtersStore.toggleManageLotsPanel()
    await flushPromises()

    expect(demandRequestParams().at(-1)?.not_fully_allocated).toBeUndefined()
  })

  it('counts as an active filter so Clear is not left greyed out', async () => {
    mountTable()
    await flushPromises()

    const filtersStore = useMadeItemsDemandsFiltersStore()
    expect(filtersStore.hasActiveFilters).toBe(false)

    filtersStore.toggleManageLotsPanel()
    await flushPromises()

    expect(filtersStore.hasActiveFilters).toBe(true)
  })

  it('Clear widens the list again without closing the panel', async () => {
    mountTable()
    await flushPromises()

    const filtersStore = useMadeItemsDemandsFiltersStore()
    filtersStore.toggleManageLotsPanel()
    await flushPromises()
    filtersStore.clearAll()
    await flushPromises()

    expect(demandRequestParams().at(-1)?.not_fully_allocated).toBeUndefined()
    expect(filtersStore.showManageLotsPanel).toBe(true)
    expect(filtersStore.hasActiveFilters).toBe(false)
  })

  it('no longer preselects statuses, which kept fully covered demands listed', async () => {
    mountTable()
    await flushPromises()

    const filtersStore = useMadeItemsDemandsFiltersStore()
    filtersStore.toggleManageLotsPanel()
    await flushPromises()

    expect(filtersStore.statuses).toEqual([])
    expect(demandRequestParams().at(-1)?.statuses).toBeUndefined()
  })
})
