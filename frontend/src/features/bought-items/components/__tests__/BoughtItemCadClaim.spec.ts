import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { answerCadClaim, cadClaimOpen, cadClaimText } from '@/test-utils/cadClaim'
import { i18n } from '@/core/i18n'

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

const updateBoughtItemMock = vi.fn<(id: number, payload: unknown) => Promise<unknown>>()
vi.mock('../../api/updateBoughtItem', () => ({
  updateBoughtItem: (id: number, payload: unknown) => updateBoughtItemMock(id, payload),
}))

import BoughtItemDetailDialog from '../BoughtItemDetailDialog.vue'
import BoughtItemsCatalogueEdit from '../BoughtItemsCatalogueEdit.vue'
import { useBoughtItemsCatalogueEditStore } from '../../stores/boughtItemsCatalogueEditStore'
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

function buttonLabelled(label: string): HTMLButtonElement | undefined {
  return Array.from(document.querySelectorAll<HTMLButtonElement>('button')).find(
    (button) => button.textContent?.trim() === label,
  )
}

async function clickSave(): Promise<void> {
  buttonLabelled(i18n.global.t('common.save'))?.click()
  await flushPromises()
  await flushPromises()
}

const mounted: VueWrapper[] = []
let pinia: ReturnType<typeof createPinia>

beforeEach(() => {
  pinia = createPinia()
  setActivePinia(pinia)
  getBoughtItemsMock.mockReset()
  updateBoughtItemMock.mockReset()
  updateBoughtItemMock.mockImplementation(async (id) => makeItem({ id }))
})

afterEach(() => {
  mounted.splice(0).forEach((wrapper) => wrapper.unmount())
})

async function openDialog(item: BoughtItemResponse) {
  const wrapper = mountWithApp(BoughtItemDetailDialog, {
    pinia,
    attachTo: document.body,
    props: { visible: false, item, editOnOpen: true },
  })
  mounted.push(wrapper)
  await wrapper.setProps({ visible: true })
  await flushPromises()
  await flushPromises()
  return wrapper
}

function formOpen(): boolean {
  return document.querySelector('#bid-article-name') !== null
}

describe('CAD claim warning in the bought item detail dialog', () => {
  it('asks before the form opens on a CAD item and opens nothing on Cancel', async () => {
    await openDialog(makeItem({ data_source: 'CAD' }))

    expect(cadClaimOpen()).toBe(true)
    expect(cadClaimText()).toContain(i18n.global.t('catalogue.cadClaim.claimed'))
    expect(formOpen()).toBe(false)

    await answerCadClaim(false)

    expect(cadClaimOpen()).toBe(false)
    expect(formOpen()).toBe(false)
  })

  it('opens the form on Continue and saves without asking again', async () => {
    getBoughtItemsMock.mockResolvedValue({ items: [makeItem({ data_source: 'CAD' })], total: 1 })
    await openDialog(makeItem({ data_source: 'CAD' }))

    await answerCadClaim(true)
    expect(formOpen()).toBe(true)

    await clickSave()

    expect(cadClaimOpen()).toBe(false)
    expect(updateBoughtItemMock).toHaveBeenCalledTimes(1)
  })

  it('opens a WEB item without asking and saves after a fresh read that is still WEB', async () => {
    getBoughtItemsMock.mockResolvedValue({ items: [makeItem({ data_source: 'WEB' })], total: 1 })
    await openDialog(makeItem({ data_source: 'WEB' }))

    expect(cadClaimOpen()).toBe(false)
    expect(formOpen()).toBe(true)

    await clickSave()

    expect(getBoughtItemsMock).toHaveBeenCalledWith({ id: 1, limit: 1 })
    expect(cadClaimOpen()).toBe(false)
    expect(updateBoughtItemMock).toHaveBeenCalledTimes(1)
  })

  it('asks at save when the fresh read shows the item claimed meanwhile, and keeps the form on Cancel', async () => {
    getBoughtItemsMock.mockResolvedValue({ items: [makeItem({ data_source: 'CAD' })], total: 1 })
    await openDialog(makeItem({ data_source: 'WEB' }))

    await clickSave()

    expect(cadClaimOpen()).toBe(true)
    expect(cadClaimText()).toContain(i18n.global.t('catalogue.cadClaim.claimedMeanwhile'))
    expect(updateBoughtItemMock).not.toHaveBeenCalled()

    await answerCadClaim(false)

    expect(updateBoughtItemMock).not.toHaveBeenCalled()
    expect(formOpen()).toBe(true)
  })

  it('saves after Continue when the item was claimed meanwhile', async () => {
    getBoughtItemsMock.mockResolvedValue({ items: [makeItem({ data_source: 'CAD' })], total: 1 })
    await openDialog(makeItem({ data_source: 'WEB' }))

    await clickSave()
    await answerCadClaim(true)

    expect(updateBoughtItemMock).toHaveBeenCalledTimes(1)
  })

  it('asks when a live update shows the item claimed while editing, and ends the edit on Cancel', async () => {
    const wrapper = await openDialog(makeItem({ data_source: 'WEB' }))
    expect(formOpen()).toBe(true)

    await wrapper.setProps({ item: makeItem({ data_source: 'CAD' }) })
    await flushPromises()

    expect(cadClaimOpen()).toBe(true)
    expect(cadClaimText()).toContain(i18n.global.t('catalogue.cadClaim.claimedMeanwhile'))

    await answerCadClaim(false)

    expect(formOpen()).toBe(false)
  })
})

describe('CAD claim warning in the bought items edit panel', () => {
  function mountPanel(items: BoughtItemResponse[]) {
    const editStore = useBoughtItemsCatalogueEditStore()
    editStore.editMode = true
    editStore.setSelectedItems(items)
    const wrapper = mountWithApp(BoughtItemsCatalogueEdit, { pinia, attachTo: document.body })
    mounted.push(wrapper)
    return editStore
  }

  it('asks about the claimed items of a selection and deselects them on Cancel', async () => {
    const editStore = mountPanel([
      makeItem({ id: 1, data_source: 'WEB' }),
      makeItem({ id: 2, data_source: 'CAD' }),
    ])
    await flushPromises()

    expect(cadClaimOpen()).toBe(true)

    await answerCadClaim(false)

    expect(editStore.selectedItems.map((item) => item.id)).toEqual([1])
  })

  it('keeps the claimed items selected on Continue', async () => {
    const editStore = mountPanel([
      makeItem({ id: 1, data_source: 'WEB' }),
      makeItem({ id: 2, data_source: 'CAD' }),
    ])
    await flushPromises()

    await answerCadClaim(true)

    expect(editStore.selectedItems.map((item) => item.id)).toEqual([1, 2])
    expect(cadClaimOpen()).toBe(false)
  })

  it('asks at save when a selected item was claimed meanwhile and saves nothing on Cancel', async () => {
    getBoughtItemsMock.mockImplementation(async (params) => {
      const { id } = params as { id: number }
      return { items: [makeItem({ id, data_source: id === 2 ? 'CAD' : 'WEB' })], total: 1 }
    })
    mountPanel([makeItem({ id: 1, data_source: 'WEB' }), makeItem({ id: 2, data_source: 'WEB' })])
    await flushPromises()
    expect(cadClaimOpen()).toBe(false)

    await clickSave()

    expect(cadClaimOpen()).toBe(true)
    expect(cadClaimText()).toContain(i18n.global.t('catalogue.cadClaim.claimedMeanwhile'))

    await answerCadClaim(false)

    expect(updateBoughtItemMock).not.toHaveBeenCalled()
  })
})
