import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { SEARCH_DEBOUNCE_MS } from '@/core/constants/table'
import LookupSelect from '../LookupSelect.vue'

import type { LookupFetch, LookupFetchByIds, LookupOption } from '../lookupMultiSelect'

const ALL: LookupOption[] = [
  { id: 1, label: 'P-001', sublabel: 'Acme' },
  { id: 2, label: 'P-002' },
]

function mountSelect(fetch: LookupFetch, modelValue: number | null = null, fetchByIds?: LookupFetchByIds) {
  return mountWithApp(LookupSelect, {
    props: { modelValue, fetch, fetchByIds, placeholder: 'Any' },
  })
}

describe('LookupSelect', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('loads the first page on mount and narrows it on the server while typing', async () => {
    const fetch = vi.fn<LookupFetch>().mockResolvedValue(ALL)
    const wrapper = mountSelect(fetch)
    await flushPromises()

    const select = wrapper.findComponent({ name: 'Select' })
    expect(fetch).toHaveBeenCalledWith('')
    expect(select.props('options')).toEqual(ALL)

    fetch.mockClear()
    select.vm.$emit('filter', { originalEvent: new Event('input'), value: 'P-00' })
    vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS)
    await flushPromises()

    expect(fetch).toHaveBeenCalledWith('P-00')
  })

  it('emits the chosen id and keeps it listed when a later search drops it', async () => {
    const fetch = vi.fn<LookupFetch>().mockResolvedValue(ALL)
    const wrapper = mountSelect(fetch)
    await flushPromises()
    const select = wrapper.findComponent({ name: 'Select' })

    select.vm.$emit('update:modelValue', 1)
    await wrapper.setProps({ modelValue: 1 })
    fetch.mockResolvedValue([ALL[1]!])
    select.vm.$emit('filter', { originalEvent: new Event('input'), value: '002' })
    vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS)
    await flushPromises()

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([1])
    expect(select.props('options')).toEqual([ALL[0], ALL[1]])
  })

  it('labels a choice it did not make through fetchByIds', async () => {
    const fetch = vi.fn<LookupFetch>().mockResolvedValue([])
    const fetchByIds = vi.fn<LookupFetchByIds>().mockResolvedValue([ALL[1]!])
    const wrapper = mountSelect(fetch, 2, fetchByIds)
    await flushPromises()

    expect(fetchByIds).toHaveBeenCalledWith([2])
    expect(wrapper.findComponent({ name: 'Select' }).props('options')).toEqual([ALL[1]])
  })
})
