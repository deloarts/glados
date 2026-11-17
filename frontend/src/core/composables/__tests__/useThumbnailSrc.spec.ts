import { describe, it, expect, vi, beforeEach } from 'vitest'
import { defineComponent, h, reactive } from 'vue'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useThumbnailSrc } from '../useThumbnailSrc'

interface ThumbnailFile {
  id: number
  category: string
}

function mountComposable(initialItemId: number) {
  const filesByItem = reactive<Record<number, ThumbnailFile[]>>({})
  const fetchFilesMock = vi.fn<(itemId: number) => void>()
  const fetchBlobMock = vi.fn<(itemId: number, fileId: number) => Promise<Blob>>()

  let imgSrc!: ReturnType<typeof useThumbnailSrc>

  const wrapper = mountWithApp(
    defineComponent({
      props: { itemId: { type: Number, required: true } },
      setup(props) {
        imgSrc = useThumbnailSrc({
          itemId: () => props.itemId,
          files: (id) => filesByItem[id] ?? [],
          fetchFiles: fetchFilesMock,
          fetchBlob: fetchBlobMock,
        })
        return () => h('div')
      },
    }),
    { props: { itemId: initialItemId } },
  )

  return { wrapper, filesByItem, fetchFilesMock, fetchBlobMock, src: () => imgSrc.value }
}

describe('useThumbnailSrc', () => {
  let counter = 0

  beforeEach(() => {
    counter = 0
    // jsdom does not implement these. Assign stubs directly rather than
    // vi.spyOn, which requires the method to exist first.
    URL.createObjectURL = vi
      .fn<(blob: Blob) => string>()
      .mockImplementation(() => `blob:fake-${++counter}`)
    URL.revokeObjectURL = vi.fn<(url: string) => void>()
  })

  it('fetches files for the initial item immediately and stays null with no thumbnail file', async () => {
    const { fetchFilesMock, src } = mountComposable(1)
    await flushPromises()

    expect(fetchFilesMock).toHaveBeenCalledWith(1)
    expect(src()).toBeNull()
  })

  it('ignores a file whose category is not "thumbnail"', async () => {
    const { filesByItem, fetchBlobMock, src } = mountComposable(1)
    filesByItem[1] = [{ id: 5, category: 'drawing' }]
    await flushPromises()

    expect(fetchBlobMock).not.toHaveBeenCalled()
    expect(src()).toBeNull()
  })

  it('resolves the thumbnail blob into an object URL once the thumbnail file appears', async () => {
    const { filesByItem, fetchBlobMock, src } = mountComposable(1)
    fetchBlobMock.mockResolvedValue(new Blob(['x']))

    filesByItem[1] = [{ id: 10, category: 'thumbnail' }]
    await flushPromises()

    expect(fetchBlobMock).toHaveBeenCalledWith(1, 10)
    expect(src()).toBe('blob:fake-1')
  })

  it('falls back to null without throwing when fetchBlob rejects', async () => {
    const { filesByItem, fetchBlobMock, src } = mountComposable(1)
    fetchBlobMock.mockRejectedValue(new Error('network error'))

    filesByItem[1] = [{ id: 10, category: 'thumbnail' }]
    await flushPromises()

    expect(src()).toBeNull()
  })

  it('revokes the previous object URL when the thumbnail file changes for the same item', async () => {
    const { filesByItem, fetchBlobMock, src } = mountComposable(1)
    fetchBlobMock.mockResolvedValue(new Blob(['x']))
    filesByItem[1] = [{ id: 10, category: 'thumbnail' }]
    await flushPromises()
    expect(src()).toBe('blob:fake-1')

    filesByItem[1] = [{ id: 11, category: 'thumbnail' }]
    await flushPromises()

    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:fake-1')
    expect(src()).toBe('blob:fake-2')
  })

  it('keeps the shown picture when a reload hands over the same thumbnail file', async () => {
    const { filesByItem, fetchBlobMock, src } = mountComposable(1)
    fetchBlobMock.mockResolvedValue(new Blob(['x']))
    filesByItem[1] = [{ id: 10, category: 'thumbnail' }]
    await flushPromises()

    filesByItem[1] = [{ id: 10, category: 'thumbnail' }]
    await flushPromises()

    expect(fetchBlobMock).toHaveBeenCalledTimes(1)
    expect(URL.revokeObjectURL).not.toHaveBeenCalled()
    expect(src()).toBe('blob:fake-1')
  })

  it('re-fetches files and re-resolves the thumbnail when itemId changes', async () => {
    const { wrapper, filesByItem, fetchFilesMock, fetchBlobMock, src } = mountComposable(1)
    fetchBlobMock.mockResolvedValue(new Blob(['x']))
    filesByItem[1] = [{ id: 10, category: 'thumbnail' }]
    await flushPromises()
    expect(src()).toBe('blob:fake-1')

    filesByItem[2] = []
    await wrapper.setProps({ itemId: 2 })
    await flushPromises()

    expect(fetchFilesMock).toHaveBeenCalledWith(2)
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:fake-1')
    expect(src()).toBeNull()
  })

  it('revokes the owned object URL on unmount', async () => {
    const { wrapper, filesByItem, fetchBlobMock } = mountComposable(1)
    fetchBlobMock.mockResolvedValue(new Blob(['x']))
    filesByItem[1] = [{ id: 10, category: 'thumbnail' }]
    await flushPromises()

    wrapper.unmount()

    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:fake-1')
  })
})
