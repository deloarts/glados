import { describe, it, expect, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'

import { useServerTable } from '../useServerTable'
import { TABLE_DEFAULT_ROWS } from '@/core/constants/table'

// useServerTable calls onMounted(), which needs a real component instance
// (not just an active effect scope) to attach to.
function mountTable(...args: Parameters<typeof useServerTable>) {
  let table!: ReturnType<typeof useServerTable>
  const wrapper = mount(
    defineComponent({
      setup() {
        table = useServerTable(...args)
        return () => h('div')
      },
    }),
  )
  return { table, wrapper }
}

describe('useServerTable', () => {
  it('fetches once on mount with the initial page state', () => {
    const fetch = vi.fn<(params: unknown) => void>()
    mountTable({ fetchParams: (page) => page, fetch })

    expect(fetch).toHaveBeenCalledTimes(1)
    expect(fetch).toHaveBeenCalledWith({ first: 0, rows: TABLE_DEFAULT_ROWS })
  })

  it('onPage updates first/rows and fetches immediately with the new page', () => {
    const fetch = vi.fn<(params: unknown) => void>()
    const { table } = mountTable({ fetchParams: (page) => page, fetch })
    fetch.mockClear()

    table.onPage({ first: 50, rows: 25 } as never)

    expect(table.first.value).toBe(50)
    expect(table.rows.value).toBe(25)
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(fetch).toHaveBeenCalledWith({ first: 50, rows: 25 })
  })

  it('resetAndFetch resets first to 0 and fetches immediately', () => {
    const fetch = vi.fn<(params: unknown) => void>()
    const { table } = mountTable({ fetchParams: (page) => page, fetch })
    table.first.value = 50
    fetch.mockClear()

    table.resetAndFetch()

    expect(table.first.value).toBe(0)
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('resetAndFetchDebounced (and onFilter, its alias) waits for the debounce window', async () => {
    vi.useFakeTimers()
    try {
      const fetch = vi.fn<(params: unknown) => void>()
      const { table } = mountTable({ fetchParams: (page) => page, fetch, debounceMs: 100 })
      table.first.value = 50
      fetch.mockClear()

      table.onFilter()
      expect(table.first.value).toBe(0)
      expect(fetch).not.toHaveBeenCalled()

      await vi.advanceTimersByTimeAsync(100)
      expect(fetch).toHaveBeenCalledTimes(1)
    } finally {
      vi.useRealTimers()
    }
  })
})
