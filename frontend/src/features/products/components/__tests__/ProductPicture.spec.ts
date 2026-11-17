import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useHostStore } from '@/core/host/stores/hostStore'
import type { ProductFile } from '../../types/productResponse'

let files: ProductFile[] = []
const fetchFiles = vi.fn<(id: number) => Promise<void>>(async () => {})
vi.mock('../../stores/productFilesStore', () => ({
  useProductFilesStore: () => ({ getFiles: () => files, fetchFiles: (id: number) => fetchFiles(id) }),
}))

const getProductFileBlob = vi.fn<(productId: number, fileId: number) => Promise<Blob>>()
vi.mock('../../api/getProductFileBlob', () => ({
  getProductFileBlob: (productId: number, fileId: number) => getProductFileBlob(productId, fileId),
}))

import ProductPicture from '../ProductPicture.vue'
import FilePreviewDialog from '@/core/components/FilePreviewDialog.vue'

function file(id: number, category: ProductFile['category'], name = `${category}.png`): ProductFile {
  return {
    id,
    category,
    file_name: name,
    mime_type: 'image/png',
    product_id: 3,
  } as ProductFile
}

function mountPicture(storageEnabled = true) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useHostStore().storageEnabled = storageEnabled
  return mountWithApp(ProductPicture, {
    pinia,
    props: { productId: 3, productNumber: 'PN-3' },
    global: { directives: { tooltip: Tooltip }, stubs: { FilePreviewDialog: true } },
  })
}

describe('ProductPicture', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getProductFileBlob.mockResolvedValue(new Blob(['x'], { type: 'image/png' }))
    URL.createObjectURL = vi.fn<(blob: Blob) => string>(() => 'blob:picture')
    URL.revokeObjectURL = vi.fn<(url: string) => void>()
  })

  it('shows the image before the thumbnail and opens it in full size', async () => {
    files = [file(1, 'thumbnail'), file(2, 'image', 'press.png')]
    const wrapper = mountPicture()
    await flushPromises()

    expect(getProductFileBlob).toHaveBeenCalledWith(3, 2)
    expect(wrapper.get('[data-testid="product-picture"] img').attributes('src')).toBe('blob:picture')

    await wrapper.get('[data-testid="product-picture"]').trigger('click')
    const preview = wrapper.getComponent(FilePreviewDialog)
    expect(preview.props()).toMatchObject({ visible: true, filename: 'press.png', mimeType: 'image/png' })
  })

  it('falls back to the thumbnail without an image', async () => {
    files = [file(1, 'thumbnail')]
    mountPicture()
    await flushPromises()

    expect(getProductFileBlob).toHaveBeenCalledWith(3, 1)
  })

  it('renders nothing without a picture', async () => {
    files = [file(4, 'pdf', 'manual.pdf')]
    const wrapper = mountPicture()
    await flushPromises()

    expect(wrapper.find('[data-testid="product-picture"]').exists()).toBe(false)
    expect(getProductFileBlob).not.toHaveBeenCalled()
  })

  it('renders nothing and loads nothing without file storage', async () => {
    files = [file(2, 'image')]
    const wrapper = mountPicture(false)
    await flushPromises()

    expect(wrapper.find('[data-testid="product-picture"]').exists()).toBe(false)
    expect(fetchFiles).not.toHaveBeenCalled()
  })
})
