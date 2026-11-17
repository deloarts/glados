import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeMadeItemDemandResponse } from '@/test-utils/factories'


const getMock = vi.fn<(url: string, config?: { params?: Record<string, unknown> }) => Promise<unknown>>()
const postMock = vi.fn<(url: string, body?: unknown) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string, config?: { params?: Record<string, unknown> }) => getMock(url, config),
    post: (url: string, body?: unknown) => postMock(url, body),
  },
}))

import MadeItemDemandDetailDialog from '../MadeItemDemandDetailDialog.vue'
import { MadeItemSelect } from '@/features/made-items'
import type { MadeItemDemandResponse, MadeItemResponse } from '@/features/made-items'

function makeDemand(overrides: Partial<MadeItemDemandResponse> = {}): MadeItemDemandResponse {
  return makeMadeItemDemandResponse({ item: {} as MadeItemDemandResponse['item'], ...overrides })
}

function makeMadeItem(overrides: Partial<MadeItemResponse> = {}): MadeItemResponse {
  return {
    id: 2,
    public_id: '22222222-2222-2222-2222-222222222222',
    status: 'active',
    archived: false,
    created: '2026-01-01',
    changed: '2026-01-01T00:00:00Z',
    part_number: 'PN-2',
    revision: 'A',
    article_name: 'Base plate',
    material: 'Steel',
    successor_item_id: null,
    ...overrides,
  } as MadeItemResponse
}

function mountDialog(demand: MadeItemDemandResponse) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mountWithApp(MadeItemDemandDetailDialog, {
    pinia,
    attachTo: document.body,
    props: { visible: false, demand },
  })
  return wrapper
}

describe('MadeItemDemandDetailDialog', () => {
  beforeEach(() => {
    getMock.mockReset()
    postMock.mockReset()
    getMock.mockImplementation((url: string, config?: { params?: Record<string, unknown> }) => {
      if (url.startsWith('/made-items-allocations/demand/')) {
        return Promise.resolve({ data: [] })
      }
      if (url === '/made-items/') {
        const id = config?.params?.id
        const items = id ? [makeMadeItem({ id: id as number })] : []
        return Promise.resolve({ data: { items, total: items.length, limit: 1, skip: 0 } })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 0, skip: 0 } })
    })
    postMock.mockResolvedValue({ data: {} })
  })

  it('opens on a plain demand, populating the edit fields, without console errors', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountDialog(makeDemand({ quantity: 7, unit: 'KG' }))
    await wrapper.setProps({ visible: true })
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(logs).toEqual([])
    // The quantity field is the first InputNumber the edit-fields block
    // renders, ahead of the allocation section's own InputNumbers.
    const quantityField = wrapper.findAllComponents({ name: 'InputNumber' }).at(0)!
    expect(quantityField.props('modelValue')).toBe(7)

    wrapper.unmount()
  })

  it('opens on an alteration demand and loads the alteration target through onOpen', async () => {
    const wrapper = mountDialog(
      makeDemand({
        is_alteration: true,
        alteration_of_made_item_id: 2,
        alteration_of_made_item_part_number: 'PN-2',
        alteration_of_made_item_revision: 'A',
        alteration_of_made_item_article_name: 'Base plate',
      }),
    )
    await wrapper.setProps({ visible: true })
    await flushPromises()
    await flushPromises()

    // Proves the async onOpen -> loadAlterationItem path resolved and wrote
    // the fetched item into the edit form, not just into the static header
    // tag (which reads the prop fields directly, not the loaded object).
    const select = wrapper.findComponent(MadeItemSelect)
    expect(select.props('modelValue')).toMatchObject({ id: 2, article_name: 'Base plate' })

    wrapper.unmount()
  })
})
