import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import type { Ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'

import { SEARCH_DEBOUNCE_MS } from '@/core/constants/table'
import { useRemoteOptions } from '../useRemoteOptions'

interface Option {
  id: number
  label: string
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function mountOptions(
  fetch: (query: string) => Promise<Option[]>,
  keepSelected?: Ref<Option | null>,
) {
  let remote!: ReturnType<typeof useRemoteOptions<Option>>
  mount(
    defineComponent({
      setup() {
        remote = useRemoteOptions<Option>(fetch, { keepSelected })
        return () => h('div')
      },
    }),
  )
  return remote
}

describe('useRemoteOptions', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('loads the unfiltered page on mount', async () => {
    const fetch = vi.fn<(query: string) => Promise<Option[]>>().mockResolvedValue([{ id: 1, label: 'a' }])
    const remote = mountOptions(fetch)

    expect(remote.loading.value).toBe(true)
    await flushPromises()

    expect(fetch).toHaveBeenCalledWith('')
    expect(remote.items.value).toEqual([{ id: 1, label: 'a' }])
    expect(remote.loading.value).toBe(false)
  })

  it('debounces a typed query', async () => {
    const fetch = vi.fn<(query: string) => Promise<Option[]>>().mockResolvedValue([])
    const remote = mountOptions(fetch)
    await flushPromises()

    void remote.debouncedSearch('ab')
    expect(fetch).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(SEARCH_DEBOUNCE_MS)

    expect(fetch).toHaveBeenLastCalledWith('ab')
  })

  it('ignores an older answer that lands after a newer one', async () => {
    const slow = deferred<Option[]>()
    const fetch = vi.fn<(query: string) => Promise<Option[]>>()
    fetch.mockReturnValueOnce(slow.promise).mockResolvedValueOnce([{ id: 2, label: 'new' }])
    const remote = mountOptions(fetch)

    await remote.search('new')
    slow.resolve([{ id: 1, label: 'old' }])
    await flushPromises()

    expect(remote.items.value).toEqual([{ id: 2, label: 'new' }])
  })

  it('rethrows the latest failure and keeps the previous options', async () => {
    const failure = new Error('network')
    const fetch = vi.fn<(query: string) => Promise<Option[]>>()
    fetch.mockResolvedValueOnce([{ id: 1, label: 'a' }]).mockRejectedValueOnce(failure)
    const remote = mountOptions(fetch)
    await flushPromises()

    await expect(remote.search('x')).rejects.toBe(failure)

    expect(remote.items.value).toEqual([{ id: 1, label: 'a' }])
    expect(remote.loading.value).toBe(false)
  })

  it('drops a stale failure', async () => {
    const slow = deferred<Option[]>()
    const fetch = vi.fn<(query: string) => Promise<Option[]>>()
    fetch.mockReturnValueOnce(slow.promise).mockResolvedValueOnce([{ id: 2, label: 'new' }])
    const remote = mountOptions(fetch)

    await remote.search('new')
    slow.reject(new Error('stale'))
    await flushPromises()

    expect(remote.items.value).toEqual([{ id: 2, label: 'new' }])
  })

  it('adds a picked item the options do not contain when keepSelected is given', async () => {
    const model = ref<Option | null>(null)
    const fetch = vi.fn<(query: string) => Promise<Option[]>>().mockResolvedValue([{ id: 1, label: 'a' }])
    const remote = mountOptions(fetch, model)
    await flushPromises()

    model.value = { id: 1, label: 'a' }
    await flushPromises()
    expect(remote.items.value).toHaveLength(1)

    model.value = { id: 9, label: 'picked' }
    await flushPromises()
    expect(remote.items.value.map((o) => o.id)).toEqual([9, 1])
  })
})
