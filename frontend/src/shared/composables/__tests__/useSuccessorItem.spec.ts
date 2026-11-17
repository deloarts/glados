import { describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { useSuccessorItem } from '../useSuccessorItem'
import type { SuccessorItemQuery } from '../useSuccessorItem'

interface Item {
  id: number
  name: string
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

function setup(cache: Item[] = []) {
  const list = vi.fn<(params: SuccessorItemQuery) => Promise<{ items: Item[] }>>()
  const getById = vi.fn<(id: number) => Item | undefined>((id) => cache.find((i) => i.id === id))
  return { list, getById, successor: useSuccessorItem<Item>({ getById, list }) }
}

describe('useSuccessorItem', () => {
  it('resolves from the store cache without a fetch', () => {
    const { list, successor } = setup([{ id: 3, name: 'cached' }])

    successor.resolveSuccessorItem(3)

    expect(successor.successorItem.value).toEqual({ id: 3, name: 'cached' })
    expect(list).not.toHaveBeenCalled()
  })

  it('fetches an uncached id and clears for null', async () => {
    const { list, successor } = setup()
    list.mockResolvedValue({ items: [{ id: 5, name: 'fetched' }] })

    successor.resolveSuccessorItem(5)
    expect(successor.successorItem.value).toBeNull()
    await flushPromises()

    expect(list).toHaveBeenCalledWith({ id: 5, limit: 1 })
    expect(successor.successorItem.value).toEqual({ id: 5, name: 'fetched' })

    successor.resolveSuccessorItem(null)
    expect(successor.successorItem.value).toBeNull()
  })

  it('keeps the newer item when an earlier fetch resolves late', async () => {
    const { list, successor } = setup([{ id: 2, name: 'cached' }])
    const slow = deferred<{ items: Item[] }>()
    list.mockReturnValueOnce(slow.promise)

    successor.resolveSuccessorItem(9)
    successor.resolveSuccessorItem(2)
    slow.resolve({ items: [{ id: 9, name: 'stale' }] })
    await flushPromises()

    expect(successor.successorItem.value).toEqual({ id: 2, name: 'cached' })
  })

  it('leaves no item when the fetch by id fails', async () => {
    const { list, successor } = setup()
    list.mockRejectedValue(new Error('network'))

    successor.resolveSuccessorItem(5)
    await flushPromises()

    expect(successor.successorItem.value).toBeNull()
  })

  it('loads suggestions for a query, and none when the search fails', async () => {
    const { list, successor } = setup()
    list.mockResolvedValueOnce({ items: [{ id: 1, name: 'a' }] })

    await successor.searchSuccessorItems({ query: 'a' })
    expect(list).toHaveBeenCalledWith({ search: 'a', limit: 20 })
    expect(successor.successorSuggestions.value).toEqual([{ id: 1, name: 'a' }])

    list.mockRejectedValueOnce(new Error('network'))
    await successor.searchSuccessorItems({ query: 'b' })
    expect(successor.successorSuggestions.value).toEqual([])
  })
})
