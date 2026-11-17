import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { computed, ref } from 'vue'
import { flushPromises } from '@vue/test-utils'

import { useImagePreviewCache } from '../useImagePreviewCache'

// The image-preview cache FilesSection.vue uses beside its mesh preview.

interface TestFile {
  id: number
  category: string
}

describe('useImagePreviewCache', () => {
  const originalCreate = URL.createObjectURL
  const originalRevoke = URL.revokeObjectURL

  beforeEach(() => {
    let n = 0
    URL.createObjectURL = vi.fn<(obj: Blob | MediaSource) => string>(() => `blob:mock-${n++}`)
    URL.revokeObjectURL = vi.fn<(url: string) => void>()
  })

  afterEach(() => {
    URL.createObjectURL = originalCreate
    URL.revokeObjectURL = originalRevoke
  })

  it('loads a URL only for files in an image category', async () => {
    const files = ref<TestFile[]>([
      { id: 1, category: 'image' },
      { id: 2, category: 'document' },
    ])
    const imageCats = computed(() => new Set(['image']))
    const fetchBlob = vi.fn<(file: TestFile) => Promise<Blob>>().mockResolvedValue(new Blob(['x']))

    const { urls } = useImagePreviewCache(files, imageCats, fetchBlob)
    await flushPromises()

    expect(fetchBlob).toHaveBeenCalledTimes(1)
    expect(fetchBlob).toHaveBeenCalledWith({ id: 1, category: 'image' })
    expect(urls.value.get(1)).toBe('blob:mock-0')
    expect(urls.value.has(2)).toBe(false)
  })

  it('does not refetch a file already in the cache', async () => {
    const files = ref<TestFile[]>([{ id: 1, category: 'image' }])
    const imageCats = computed(() => new Set(['image']))
    const fetchBlob = vi.fn<(file: TestFile) => Promise<Blob>>().mockResolvedValue(new Blob(['x']))

    useImagePreviewCache(files, imageCats, fetchBlob)
    await flushPromises()
    expect(fetchBlob).toHaveBeenCalledTimes(1)

    // Same list re-emitted (e.g. an unrelated store mutation). The file id
    // is already cached, so no second fetch.
    files.value = [{ id: 1, category: 'image' }]
    await flushPromises()

    expect(fetchBlob).toHaveBeenCalledTimes(1)
  })

  it('fetches newly added files without re-fetching existing ones', async () => {
    const files = ref<TestFile[]>([{ id: 1, category: 'image' }])
    const imageCats = computed(() => new Set(['image']))
    const fetchBlob = vi.fn<(file: TestFile) => Promise<Blob>>().mockResolvedValue(new Blob(['x']))

    const { urls } = useImagePreviewCache(files, imageCats, fetchBlob)
    await flushPromises()

    files.value = [...files.value, { id: 2, category: 'image' }]
    await flushPromises()

    expect(fetchBlob).toHaveBeenCalledTimes(2)
    expect(urls.value.get(1)).toBe('blob:mock-0')
    expect(urls.value.get(2)).toBe('blob:mock-1')
  })

  it('leaves the cache untouched when the fetch rejects', async () => {
    const files = ref<TestFile[]>([{ id: 1, category: 'image' }])
    const imageCats = computed(() => new Set(['image']))
    const fetchBlob = vi.fn<(file: TestFile) => Promise<Blob>>().mockRejectedValue(new Error('boom'))

    const { urls } = useImagePreviewCache(files, imageCats, fetchBlob)
    await flushPromises()

    expect(urls.value.has(1)).toBe(false)
  })

  it('revokeAll() revokes every cached URL', async () => {
    const files = ref<TestFile[]>([
      { id: 1, category: 'image' },
      { id: 2, category: 'image' },
    ])
    const imageCats = computed(() => new Set(['image']))
    const fetchBlob = vi.fn<(file: TestFile) => Promise<Blob>>().mockResolvedValue(new Blob(['x']))

    const { revokeAll } = useImagePreviewCache(files, imageCats, fetchBlob)
    await flushPromises()

    revokeAll()

    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-0')
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-1')
    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(2)
  })
})
