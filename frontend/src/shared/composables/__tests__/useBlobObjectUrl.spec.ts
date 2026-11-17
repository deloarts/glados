import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'

import { useBlobObjectUrl } from '../useBlobObjectUrl'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function mountLoader(...args: Parameters<typeof useBlobObjectUrl<number>>) {
  let loader!: ReturnType<typeof useBlobObjectUrl<number>>
  const wrapper = mount(
    defineComponent({
      setup() {
        loader = useBlobObjectUrl<number>(...args)
        return () => h('div')
      },
    }),
  )
  return { loader, wrapper }
}

describe('useBlobObjectUrl', () => {
  const originalCreate = URL.createObjectURL
  const originalRevoke = URL.revokeObjectURL
  let created: Blob[]
  let createObjectURL: ReturnType<typeof vi.fn<(obj: Blob | MediaSource) => string>>
  let revokeObjectURL: ReturnType<typeof vi.fn<(url: string) => void>>

  beforeEach(() => {
    created = []
    createObjectURL = vi.fn<(obj: Blob | MediaSource) => string>((obj) => {
      created.push(obj as Blob)
      return `blob:mock-${created.length}`
    })
    revokeObjectURL = vi.fn<(url: string) => void>()
    URL.createObjectURL = createObjectURL
    URL.revokeObjectURL = revokeObjectURL
  })

  afterEach(() => {
    URL.createObjectURL = originalCreate
    URL.revokeObjectURL = originalRevoke
  })

  it('loads the blob for the current key and types an untyped blob with the fallback', async () => {
    const fetch = vi.fn<(id: number) => Promise<Blob>>().mockResolvedValue(new Blob(['%PDF']))
    const { loader } = mountLoader(() => 7, fetch)

    expect(loader.loading.value).toBe(true)
    await flushPromises()

    expect(fetch).toHaveBeenCalledWith(7)
    expect(loader.url.value).toBe('blob:mock-1')
    expect(loader.loading.value).toBe(false)
    expect(created[0]?.type).toBe('application/pdf')
  })

  it('does not fetch for a null key', async () => {
    const fetch = vi.fn<(id: number) => Promise<Blob>>()
    const { loader } = mountLoader(() => null, fetch)
    await flushPromises()

    expect(fetch).not.toHaveBeenCalled()
    expect(loader.url.value).toBeNull()
    expect(loader.loading.value).toBe(false)
  })

  it('leaves the url empty when fetch returns null', async () => {
    const fetch = vi.fn<(id: number) => Promise<Blob> | null>().mockReturnValue(null)
    const { loader } = mountLoader(() => 1, fetch)
    await flushPromises()

    expect(loader.url.value).toBeNull()
    expect(loader.loading.value).toBe(false)
  })

  it('revokes the previous url when the key changes and ignores a stale response', async () => {
    const key = ref<number | null>(1)
    const first = deferred<Blob>()
    const second = deferred<Blob>()
    const fetch = vi.fn<(id: number) => Promise<Blob>>()
    fetch.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    const { loader } = mountLoader(key, fetch)

    key.value = 2
    await flushPromises()
    second.resolve(new Blob(['b'], { type: 'application/pdf' }))
    await flushPromises()
    expect(loader.url.value).toBe('blob:mock-1')

    first.resolve(new Blob(['a'], { type: 'application/pdf' }))
    await flushPromises()
    expect(loader.url.value).toBe('blob:mock-1')
    expect(createObjectURL).toHaveBeenCalledTimes(1)
    expect(loader.loading.value).toBe(false)

    key.value = null
    await flushPromises()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock-1')
    expect(loader.url.value).toBeNull()
  })

  it('revokes the url on unmount and drops a response that lands afterwards', async () => {
    const key = ref<number | null>(1)
    const pending = deferred<Blob>()
    const fetch = vi.fn<(id: number) => Promise<Blob>>()
    fetch.mockResolvedValueOnce(new Blob(['a'], { type: 'application/pdf' }))
    fetch.mockReturnValueOnce(pending.promise)
    const { loader, wrapper } = mountLoader(key, fetch)
    await flushPromises()
    expect(loader.url.value).toBe('blob:mock-1')

    key.value = 2
    await flushPromises()
    wrapper.unmount()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock-1')

    pending.resolve(new Blob(['b']))
    await flushPromises()
    expect(createObjectURL).toHaveBeenCalledTimes(1)
  })
})
