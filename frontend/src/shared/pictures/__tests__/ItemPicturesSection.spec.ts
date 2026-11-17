import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import Tooltip from 'openvue/tooltip'

import ItemPicturesSection from '../ItemPicturesSection.vue'
import type { ItemPicture } from '../api'
import type { ItemPicturesStoreInstance } from '../createItemPicturesStore'
import { mountWithApp } from '@/test-utils/mountWithApp'
import { answerConfirmations } from '@/test-utils/confirmations'

function picture(overrides: Partial<ItemPicture>): ItemPicture {
  return {
    id: 1,
    public_id: '00000000-0000-0000-0000-000000000001',
    item_id: 5,
    source: 'picture',
    file_name: 'photo.jpg',
    has_image: true,
    has_thumbnail: true,
    created: '2026-10-29T00:00:00Z',
    uploaded_by_user_id: 1,
    in_use: false,
    ...overrides,
  }
}

function makeStore(pictures: ItemPicture[]) {
  return {
    getShown: vi.fn<ItemPicturesStoreInstance['getShown']>(),
    fetchShown: vi.fn<(itemId: number) => Promise<void>>(),
    getPictures: vi.fn<(itemId: number) => ItemPicture[]>(() => pictures),
    isLoadingPictures: vi.fn<(itemId: number) => boolean>(() => false),
    fetchPictures: vi.fn<(itemId: number) => Promise<void>>().mockResolvedValue(undefined),
    getBlob: vi.fn<ItemPicturesStoreInstance['getBlob']>().mockResolvedValue(new Blob(['x'])),
    upload: vi.fn<ItemPicturesStoreInstance['upload']>(),
    removePhoto: vi.fn<(itemId: number) => Promise<void>>().mockResolvedValue(undefined),
  }
}

function mountSection(store: ReturnType<typeof makeStore>, props: Record<string, unknown> = {}) {
  return mountWithApp(ItemPicturesSection, {
    props: { itemId: 5, store, canEdit: true, ...props },
    global: { directives: { tooltip: Tooltip } },
  })
}

describe('ItemPicturesSection', () => {
  const originalCreate = URL.createObjectURL
  const originalRevoke = URL.revokeObjectURL

  beforeEach(() => {
    URL.createObjectURL = vi.fn<(obj: Blob | MediaSource) => string>(() => 'blob:picture')
    URL.revokeObjectURL = vi.fn<(url: string) => void>()
  })

  afterEach(() => {
    URL.createObjectURL = originalCreate
    URL.revokeObjectURL = originalRevoke
  })

  it('shows one slot per stored source and marks the picture shown', async () => {
    const store = makeStore([
      picture({ id: 2, source: 'data_portal', in_use: true }),
      picture({ id: 3, source: 'cad_rendering' }),
    ])
    const wrapper = mountSection(store)
    await flushPromises()

    const slots = wrapper.findAll('.picture-slot')
    // The empty photo slot to upload into, then the two stored pictures.
    expect(slots.map((s) => s.find('.slot-header').text())).toEqual([
      'Photo',
      'Data PortalShown',
      'CAD Rendering',
    ])
    expect(store.getBlob).toHaveBeenCalledWith(5, 'data_portal', 'thumbnail')
  })

  it('hides the empty photo slot when read-only', async () => {
    const store = makeStore([picture({ id: 3, source: 'cad_rendering', in_use: true })])
    const wrapper = mountSection(store, { readonly: true })
    await flushPromises()

    expect(wrapper.findAll('.picture-slot')).toHaveLength(1)
  })

  it('keeps the upload visible but disabled without the permission', async () => {
    const wrapper = mountSection(makeStore([]), { canEdit: false })
    await flushPromises()

    const upload = wrapper.findAll('button').find((b) => b.text() === 'Upload Photo')
    expect(upload?.attributes('disabled')).toBeDefined()
  })

  it('deletes the photo through the store once the user confirms', async () => {
    const confirmations = answerConfirmations('accept')
    const store = makeStore([picture({ id: 1, source: 'picture', in_use: true })])
    const wrapper = mountSection(store)
    await flushPromises()

    await wrapper.find('button[aria-label="Delete Photo"]').trigger('click')
    await flushPromises()
    confirmations.stop()

    expect(confirmations.asked).toHaveLength(1)
    expect(store.removePhoto).toHaveBeenCalledWith(5)
  })

  it('keeps the photo when the user cancels the confirmation', async () => {
    const confirmations = answerConfirmations('reject')
    const store = makeStore([picture({ id: 1, source: 'picture', in_use: true })])
    const wrapper = mountSection(store)
    await flushPromises()

    await wrapper.find('button[aria-label="Delete Photo"]').trigger('click')
    await flushPromises()
    confirmations.stop()

    expect(store.removePhoto).not.toHaveBeenCalled()
  })
})
