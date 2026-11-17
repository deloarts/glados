import { describe, it, expect, vi, afterEach } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { SEARCH_DEBOUNCE_MS } from '@/core/constants/table'

import type { OrderFilterParams } from '../../types/ordersRequest'
import type { OrderResponse } from '../../types/ordersResponse'

const getOrdersMock = vi.fn<(params: OrderFilterParams) => Promise<unknown>>()
vi.mock('../../api/getOrders', () => ({
  getOrders: (params: OrderFilterParams) => getOrdersMock(params),
}))

import OrderSelect from '../OrderSelect.vue'

function makeOrder(id: number): OrderResponse {
  return {
    id,
    order_number: `O-${id}`,
    supplier_name: 'Acme',
    status: 'ordered',
  } as OrderResponse
}

const mounted: VueWrapper[] = []

async function mountSelect(props: Record<string, unknown> = {}) {
  const wrapper = mountWithApp(OrderSelect, { props: { modelValue: null, ...props } })
  mounted.push(wrapper)
  await flushPromises()
  return wrapper
}

function options(wrapper: VueWrapper): OrderResponse[] {
  return wrapper.findComponent({ name: 'Select' }).props('options') as OrderResponse[]
}

describe('OrderSelect', () => {
  afterEach(() => {
    mounted.splice(0).forEach((wrapper) => wrapper.unmount())
    getOrdersMock.mockReset()
    vi.useRealTimers()
  })

  it('loads one page of the newest open orders instead of every order', async () => {
    getOrdersMock.mockResolvedValue({ items: [makeOrder(1), makeOrder(2)], total: 900 })

    const wrapper = await mountSelect()

    expect(getOrdersMock).toHaveBeenCalledTimes(1)
    expect(getOrdersMock).toHaveBeenCalledWith({
      status: ['draft', 'requested', 'partially_ordered', 'ordered', 'partially_delivered'],
      search: undefined,
      limit: 50,
    })
    expect(options(wrapper).map((o) => o.id)).toEqual([1, 2])
  })

  it('searches on the server once the user stops typing', async () => {
    getOrdersMock.mockResolvedValue({ items: [makeOrder(1)], total: 1 })
    const wrapper = await mountSelect()
    vi.useFakeTimers()

    getOrdersMock.mockResolvedValue({ items: [makeOrder(7)], total: 1 })
    wrapper.findComponent({ name: 'Select' }).vm.$emit('filter', { value: 'acme' })
    await vi.advanceTimersByTimeAsync(SEARCH_DEBOUNCE_MS)
    await flushPromises()

    expect(getOrdersMock).toHaveBeenLastCalledWith(expect.objectContaining({ search: 'acme' }))
    expect(options(wrapper).map((o) => o.id)).toEqual([7])
  })

  it('keeps the chosen order as an option when the page does not hold it', async () => {
    getOrdersMock.mockResolvedValue({ items: [makeOrder(1)], total: 1 })

    const wrapper = await mountSelect({ modelValue: makeOrder(42) })

    expect(options(wrapper).map((o) => o.id)).toEqual([42, 1])
  })

  it('leaves out the excluded order', async () => {
    getOrdersMock.mockResolvedValue({ items: [makeOrder(1), makeOrder(2)], total: 2 })

    const wrapper = await mountSelect({ exclude: 1 })

    expect(options(wrapper).map((o) => o.id)).toEqual([2])
  })
})
