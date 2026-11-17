import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import api from '@/core/api'
import { MadeItemSelect } from '@/features/made-items'
import { makeMadeItemDemandResponse, makeMadeItemResponse } from '@/test-utils/factories'
import { i18n } from '@/core/i18n'
import type { MadeItemDemandResponse } from '@/features/made-items'

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: { items: [], total: 0, limit: 1000, skip: 0 },
    }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import LotCreateDialog from '../LotCreateDialog.vue'

function makeDemand(overrides: Partial<MadeItemDemandResponse> = {}): MadeItemDemandResponse {
  return makeMadeItemDemandResponse({
    id: 3,
    made_item_id: 42,
    item_part_number: 'PN-42',
    project_id: 7,
    project_number: 'P-007',
    ...overrides,
  })
}

function mountWithDemand(presetDemand: MadeItemDemandResponse) {
  return mountWithApp(LotCreateDialog, {
    attachTo: document.body,
    props: { visible: true, presetDemand },
  })
}

describe('LotCreateDialog', () => {
  it('renders without errors when opened', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountWithApp(LotCreateDialog, {
      attachTo: document.body,
      props: { visible: true },
    })

    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(wrapper.exists()).toBe(true)
    expect(logs).toEqual([])

    wrapper.unmount()
  })

  it('locks the made item while a demand is preset, since a lot builds that item only', async () => {
    const wrapper = mountWithDemand(makeDemand())
    await flushPromises()

    expect(wrapper.findComponent(MadeItemSelect).vm.$attrs.disabled).toBe(true)

    wrapper.unmount()
  })

  it('creates the lot for the made item of the preset demand even without its item', async () => {
    vi.mocked(api.post).mockClear()
    const wrapper = mountWithDemand(makeDemand({ item: null }))
    await flushPromises()

    document.querySelector('form.create-form')!.dispatchEvent(new Event('submit'))
    await flushPromises()

    expect(api.post).toHaveBeenCalledWith(
      '/production-lots/',
      expect.objectContaining({
        made_item_id: 42,
        project_id: 7,
        demand_allocations: [{ demand_item_id: 3, quantity: 5 }],
      }),
    )

    wrapper.unmount()
  })

  it.each([
    [{ bought_item_id: null, source_item_id: null }, true],
    [{ bought_item_id: null, source_item_id: 6 }, false],
    [{ bought_item_id: 5, source_item_id: null }, false],
  ])('hints that a made item without material source is not planned (%o)', async (source, shown) => {
    const wrapper = mountWithApp(LotCreateDialog, {
      attachTo: document.body,
      props: { visible: true, presetItem: makeMadeItemResponse({ id: 42, ...source }) },
    })
    await flushPromises()

    const hint = i18n.global.t('production.lots.create.noSourceHint')
    expect(document.body.textContent?.includes(hint)).toBe(shown)

    wrapper.unmount()
  })
})
