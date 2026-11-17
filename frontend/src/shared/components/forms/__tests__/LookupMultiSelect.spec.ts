import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { SEARCH_DEBOUNCE_MS } from '@/core/constants/table'
import LookupMultiSelect from '../LookupMultiSelect.vue'

import type { LookupFetch, LookupFetchByIds, LookupOption } from '../lookupMultiSelect'

const ALL: LookupOption[] = [
  { id: 1, label: 'PO-001', sublabel: 'Acme' },
  { id: 2, label: 'PO-002', sublabel: 'Bolt & Co' },
  { id: 3, label: 'PO-003' },
]

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((r) => {
    resolve = r
  })
  return { promise, resolve }
}

function mountSelect(
  fetch: LookupFetch,
  modelValue: number[] = [],
  fetchByIds?: LookupFetchByIds,
) {
  return mountWithApp(LookupMultiSelect, {
    props: { modelValue, fetch, fetchByIds, placeholder: 'Any' },
  })
}

describe('LookupMultiSelect', () => {
  beforeEach(() => {
    // Only the timer the debounce relies on is faked; flushPromises still
    // needs a real setImmediate to drain the microtask queue.
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('fetches with an empty query on mount and lists the results', async () => {
    const fetch = vi.fn<LookupFetch>().mockResolvedValue(ALL)
    const wrapper = mountSelect(fetch)
    await flushPromises()

    expect(fetch).toHaveBeenCalledTimes(1)
    expect(fetch).toHaveBeenCalledWith('')
    const multiSelect = wrapper.findComponent({ name: 'MultiSelect' })
    expect(multiSelect.props('options')).toEqual(ALL)
    expect(multiSelect.props('loading')).toBe(false)
    expect(multiSelect.props('placeholder')).toBe('Any')
  })

  it('refetches with the typed filter after the debounce, once per settled query', async () => {
    const fetch = vi.fn<LookupFetch>().mockResolvedValue(ALL)
    const wrapper = mountSelect(fetch)
    await flushPromises()
    fetch.mockClear()

    const multiSelect = wrapper.findComponent({ name: 'MultiSelect' })
    multiSelect.vm.$emit('filter', { originalEvent: new Event('input'), value: 'PO-0' })
    multiSelect.vm.$emit('filter', { originalEvent: new Event('input'), value: 'PO-00' })
    expect(fetch).not.toHaveBeenCalled()

    vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS)
    await flushPromises()

    expect(fetch).toHaveBeenCalledTimes(1)
    expect(fetch).toHaveBeenCalledWith('PO-00')
  })

  it('emits the new ids and keeps a selected option listed when a later search drops it', async () => {
    const fetch = vi.fn<LookupFetch>().mockResolvedValue(ALL)
    const wrapper = mountSelect(fetch)
    await flushPromises()

    const multiSelect = wrapper.findComponent({ name: 'MultiSelect' })
    multiSelect.vm.$emit('update:modelValue', [2])
    await flushPromises()
    expect(wrapper.emitted('update:modelValue')).toEqual([[[2]]])
    await wrapper.setProps({ modelValue: [2] })

    fetch.mockResolvedValue([ALL[0]!])
    multiSelect.vm.$emit('filter', { originalEvent: new Event('input'), value: 'PO-001' })
    vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS)
    await flushPromises()

    expect(multiSelect.props('options')).toEqual([ALL[1], ALL[0]])
  })

  it('ignores a response to a query that a newer one has already superseded', async () => {
    const first = deferred<LookupOption[]>()
    const second = deferred<LookupOption[]>()
    const fetch = vi.fn<LookupFetch>()
    fetch.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    const wrapper = mountSelect(fetch)
    const multiSelect = wrapper.findComponent({ name: 'MultiSelect' })

    multiSelect.vm.$emit('filter', { originalEvent: new Event('input'), value: 'PO-003' })
    vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS)
    await flushPromises()
    expect(fetch).toHaveBeenCalledTimes(2)
    expect(multiSelect.props('loading')).toBe(true)

    second.resolve([ALL[2]!])
    await flushPromises()
    expect(multiSelect.props('options')).toEqual([ALL[2]])
    expect(multiSelect.props('loading')).toBe(false)

    first.resolve(ALL)
    await flushPromises()
    expect(multiSelect.props('options')).toEqual([ALL[2]])
  })

  it('reloads the unfiltered page when the panel hides after a search', async () => {
    const fetch = vi.fn<LookupFetch>().mockResolvedValue(ALL)
    const wrapper = mountSelect(fetch)
    await flushPromises()
    const multiSelect = wrapper.findComponent({ name: 'MultiSelect' })

    multiSelect.vm.$emit('filter', { originalEvent: new Event('input'), value: 'PO-001' })
    vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS)
    await flushPromises()
    fetch.mockClear()

    multiSelect.vm.$emit('hide')
    await flushPromises()

    expect(fetch).toHaveBeenCalledTimes(1)
    expect(fetch).toHaveBeenCalledWith('')
  })

  it('labels a restored selection through fetchByIds and lists it ahead of the page', async () => {
    const fetch = vi.fn<LookupFetch>().mockResolvedValue([ALL[0]!])
    const fetchByIds = vi
      .fn<LookupFetchByIds>()
      .mockResolvedValue([{ id: 99, label: 'PO-099', sublabel: 'Restored' }])
    const wrapper = mountSelect(fetch, [99], fetchByIds)
    await flushPromises()

    expect(fetchByIds).toHaveBeenCalledTimes(1)
    expect(fetchByIds).toHaveBeenCalledWith([99])
    const multiSelect = wrapper.findComponent({ name: 'MultiSelect' })
    expect(multiSelect.props('options')).toEqual([
      { id: 99, label: 'PO-099', sublabel: 'Restored' },
      ALL[0],
    ])

    // An id the component already knows is not looked up again.
    await wrapper.setProps({ modelValue: [99, 1] })
    await flushPromises()
    expect(fetchByIds).toHaveBeenCalledTimes(1)
  })

  it('does not look ids up when no fetchByIds is given', async () => {
    const fetch = vi.fn<LookupFetch>().mockResolvedValue(ALL)
    const wrapper = mountSelect(fetch, [99])
    await flushPromises()

    const multiSelect = wrapper.findComponent({ name: 'MultiSelect' })
    expect(multiSelect.props('options')).toEqual(ALL)
  })

  it('renders the sublabel under the label in the option row', async () => {
    const fetch = vi.fn<LookupFetch>().mockResolvedValue(ALL)
    const wrapper = mountSelect(fetch)
    await flushPromises()

    const multiSelect = wrapper.findComponent({ name: 'MultiSelect' })
    await multiSelect.vm.show()
    await flushPromises()

    const rows = document.body.querySelectorAll('.lookup-option')
    expect(rows).toHaveLength(3)
    expect(rows[0]!.querySelector('.lookup-label')!.textContent).toBe('PO-001')
    expect(rows[0]!.querySelector('.lookup-sublabel')!.textContent).toBe('Acme')
    expect(rows[2]!.querySelector('.lookup-sublabel')).toBeNull()

    wrapper.unmount()
  })

  it('is small as a table filter and takes the form size when it is not compact', async () => {
    const fetch = vi.fn<LookupFetch>().mockResolvedValue(ALL)
    const filter = mountSelect(fetch)
    const field = mountWithApp(LookupMultiSelect, {
      props: { modelValue: [], fetch, compact: false },
    })
    await flushPromises()

    expect(filter.findComponent({ name: 'MultiSelect' }).props('size')).toBe('small')
    expect(field.findComponent({ name: 'MultiSelect' }).props('size')).not.toBe('small')

    filter.unmount()
    field.unmount()
  })
})
