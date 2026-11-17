import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

let shownById: Record<number, { item_id: number; picture_id: number; source: string } | null>
let fetchBlobMock: ReturnType<
  typeof vi.fn<(itemId: number, source: string, variant: string) => Promise<Blob>>
>

vi.mock('../../stores/sourceItemPicturesStore', () => ({
  useSourceItemPicturesStore: () => ({
    getShown: (id: number) => shownById[id] ?? null,
    fetchShown: vi.fn<(itemId: number) => Promise<void>>(),
    getBlob: (itemId: number, source: string, variant: string) =>
      fetchBlobMock(itemId, source, variant),
  }),
}))

import SourceItemThumbnailCell from '../SourceItemThumbnailCell.vue'

describe('SourceItemThumbnailCell', () => {
  const originalCreate = URL.createObjectURL
  const originalRevoke = URL.revokeObjectURL

  beforeEach(() => {
    setActivePinia(createPinia())
    shownById = {}
    fetchBlobMock = vi
      .fn<(itemId: number, source: string, variant: string) => Promise<Blob>>()
      .mockResolvedValue(new Blob(['x']))
    URL.createObjectURL = vi.fn<(obj: Blob | MediaSource) => string>(() => 'blob:mock-thumbnail')
    URL.revokeObjectURL = vi.fn<(url: string) => void>()
  })

  afterEach(() => {
    URL.createObjectURL = originalCreate
    URL.revokeObjectURL = originalRevoke
  })

  it('shows the shape placeholder image when the item has no picture', async () => {
    const wrapper = mount(SourceItemThumbnailCell, {
      props: { itemId: 1, dimension: '100 × 200 × 20' },
    })
    await flushPromises()

    const img = wrapper.find('img')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toContain('block')
    expect(fetchBlobMock).not.toHaveBeenCalled()
  })

  it('prefers a real picture over the shape placeholder', async () => {
    shownById[2] = { item_id: 2, picture_id: 5, source: 'picture' }
    const wrapper = mount(SourceItemThumbnailCell, {
      props: { itemId: 2, dimension: '100 × 200 × 20' },
    })
    await flushPromises()

    const img = wrapper.find('img')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toBe('blob:mock-thumbnail')
  })

  it('renders the empty no-image state for a custom dimension with no picture', async () => {
    const wrapper = mount(SourceItemThumbnailCell, {
      props: { itemId: 3, dimension: 'custom shape' },
    })
    await flushPromises()

    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('.placeholder-icon').exists()).toBe(true)
  })

  it('renders the empty no-image state when no dimension is given at all', async () => {
    const wrapper = mount(SourceItemThumbnailCell, { props: { itemId: 4 } })
    await flushPromises()

    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('.placeholder-icon').exists()).toBe(true)
  })
})
