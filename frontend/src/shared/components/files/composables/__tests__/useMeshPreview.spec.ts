import { describe, it, expect, vi } from 'vitest'
import { computed, ref } from 'vue'
import { flushPromises } from '@vue/test-utils'

import { useMeshPreview } from '../useMeshPreview'

// The mesh-preview watcher FilesSection.vue uses (id-dedupe + loading flag +
// blob fetch), beside its image-preview cache.

interface TestFile {
  id: number
}

describe('useMeshPreview', () => {
  it('starts with no blob and not loading when there is no mesh file', () => {
    const meshFile = computed<TestFile | undefined>(() => undefined)
    const fetchBlob = vi.fn<(file: TestFile) => Promise<Blob>>()

    const { meshBlob, meshLoading } = useMeshPreview(meshFile, fetchBlob)

    expect(meshBlob.value).toBeNull()
    expect(meshLoading.value).toBe(false)
    expect(fetchBlob).not.toHaveBeenCalled()
  })

  it('fetches and stores the blob when a mesh file appears', async () => {
    const file = ref<TestFile | undefined>(undefined)
    const meshFile = computed(() => file.value)
    const blob = new Blob(['mesh'])
    const fetchBlob = vi.fn<(file: TestFile) => Promise<Blob>>().mockResolvedValue(blob)

    const { meshBlob, meshLoading } = useMeshPreview(meshFile, fetchBlob)
    file.value = { id: 1 }
    await flushPromises()

    expect(fetchBlob).toHaveBeenCalledWith({ id: 1 })
    expect(meshBlob.value).toBe(blob)
    expect(meshLoading.value).toBe(false)
  })

  it('does not refetch when the file id is unchanged', async () => {
    const file = ref<TestFile | undefined>({ id: 1 })
    const meshFile = computed(() => file.value)
    const fetchBlob = vi.fn<(file: TestFile) => Promise<Blob>>().mockResolvedValue(new Blob(['a']))

    useMeshPreview(meshFile, fetchBlob)
    await flushPromises()
    expect(fetchBlob).toHaveBeenCalledTimes(1)

    // Same id, new object identity: a common case when the parent's list
    // re-renders without the underlying file actually changing.
    file.value = { id: 1 }
    await flushPromises()

    expect(fetchBlob).toHaveBeenCalledTimes(1)
  })

  it('refetches when the file id changes', async () => {
    const file = ref<TestFile | undefined>({ id: 1 })
    const meshFile = computed(() => file.value)
    const fetchBlob = vi.fn<(file: TestFile) => Promise<Blob>>().mockResolvedValue(new Blob(['a']))

    useMeshPreview(meshFile, fetchBlob)
    await flushPromises()

    file.value = { id: 2 }
    await flushPromises()

    expect(fetchBlob).toHaveBeenCalledTimes(2)
    expect(fetchBlob).toHaveBeenLastCalledWith({ id: 2 })
  })

  it('clears the blob and re-arms when the file disappears then comes back', async () => {
    const file = ref<TestFile | undefined>({ id: 1 })
    const meshFile = computed(() => file.value)
    const fetchBlob = vi.fn<(file: TestFile) => Promise<Blob>>().mockResolvedValue(new Blob(['a']))

    const { meshBlob } = useMeshPreview(meshFile, fetchBlob)
    await flushPromises()
    expect(meshBlob.value).not.toBeNull()

    file.value = undefined
    await flushPromises()
    expect(meshBlob.value).toBeNull()

    file.value = { id: 1 }
    await flushPromises()

    expect(fetchBlob).toHaveBeenCalledTimes(2)
  })

  it('clears the blob and stops loading when the fetch rejects', async () => {
    const file = ref<TestFile | undefined>(undefined)
    const meshFile = computed(() => file.value)
    const fetchBlob = vi.fn<(file: TestFile) => Promise<Blob>>().mockRejectedValue(new Error('network error'))

    const { meshBlob, meshLoading } = useMeshPreview(meshFile, fetchBlob)
    file.value = { id: 1 }
    await flushPromises()

    expect(meshBlob.value).toBeNull()
    expect(meshLoading.value).toBe(false)
  })
})
