import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'

import MachineFileStrip from '../MachineFileStrip.vue'
import type { MachineStripFile } from '../../types/machineFileStrip'

function makeFile(overrides: Partial<MachineStripFile> & { id: number }): MachineStripFile {
  return {
    file_name: `file-${overrides.id}.bin`,
    mime_type: 'application/octet-stream',
    category: 'step',
    ...overrides,
  }
}

function mountStrip(files: MachineStripFile[], fetchBlob: (file: MachineStripFile) => Promise<Blob>) {
  return mountWithApp(MachineFileStrip, {
    props: { files, fetchBlob },
    global: {
      directives: { tooltip: Tooltip },
      stubs: { MeshViewer: true },
    },
  })
}

describe('MachineFileStrip', () => {
  let createObjectURL: ReturnType<
    typeof vi.fn<(obj: Blob | MediaSource) => string>
  >
  let revokeObjectURL: ReturnType<typeof vi.fn<(url: string) => void>>
  const originalCreate = URL.createObjectURL
  const originalRevoke = URL.revokeObjectURL

  beforeEach(() => {
    let n = 0
    createObjectURL = vi.fn<(obj: Blob | MediaSource) => string>(() => `blob:mock-${n++}`)
    revokeObjectURL = vi.fn<(url: string) => void>()
    URL.createObjectURL = createObjectURL
    URL.revokeObjectURL = revokeObjectURL
  })

  afterEach(() => {
    URL.createObjectURL = originalCreate
    URL.revokeObjectURL = originalRevoke
  })

  it('renders nothing when there are no files', () => {
    const wrapper = mountStrip([], vi.fn())
    expect(wrapper.find('.file-strip').exists()).toBe(false)
  })

  it('shows a loading spinner while the blob fetch is pending, then the image once it resolves', async () => {
    const file = makeFile({ id: 1, category: 'image', file_name: 'photo.png' })
    let resolveBlob: (blob: Blob) => void = () => {}
    const fetchBlob = vi.fn<(f: MachineStripFile) => Promise<Blob>>(
      () => new Promise((resolve) => (resolveBlob = resolve)),
    )

    const wrapper = mountStrip([file], fetchBlob)
    await flushPromises()

    expect(wrapper.find('[data-testid="file-strip-loading"]').exists()).toBe(true)
    expect(wrapper.find('img').exists()).toBe(false)

    resolveBlob(new Blob(['x'], { type: 'image/png' }))
    await flushPromises()
    await flushPromises()

    expect(fetchBlob).toHaveBeenCalledWith(file)
    expect(wrapper.find('[data-testid="file-strip-loading"]').exists()).toBe(false)
    const img = wrapper.find('img.file-box-image')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toBe('blob:mock-0')
  })

  it('renders both the thumbnail and image categories as content tiles', async () => {
    const files = [
      makeFile({ id: 1, category: 'thumbnail' }),
      makeFile({ id: 2, category: 'image' }),
    ]
    const fetchBlob = vi
      .fn<(f: MachineStripFile) => Promise<Blob>>()
      .mockResolvedValue(new Blob(['x'], { type: 'image/png' }))

    const wrapper = mountStrip(files, fetchBlob)
    await flushPromises()
    await flushPromises()

    expect(wrapper.findAll('img.file-box-image')).toHaveLength(2)
  })

  it('falls back to the category icon for step/dxf without ever fetching a blob', async () => {
    const files = [
      makeFile({ id: 1, category: 'step' }),
      makeFile({ id: 2, category: 'dxf' }),
    ]
    const fetchBlob = vi.fn<(f: MachineStripFile) => Promise<Blob>>()

    const wrapper = mountStrip(files, fetchBlob)
    await flushPromises()
    await flushPromises()

    expect(fetchBlob).not.toHaveBeenCalled()
    const icons = wrapper.findAll('.file-box-icon')
    expect(icons).toHaveLength(2)
    expect(icons[0]!.classes()).toContain('mdi-file-outline')
    expect(icons[1]!.classes()).toContain('mdi-vector-square')
  })

  it('falls back to the icon when the blob fetch fails', async () => {
    const file = makeFile({ id: 1, category: 'image' })
    const fetchBlob = vi
      .fn<(f: MachineStripFile) => Promise<Blob>>()
      .mockRejectedValue(new Error('network error'))

    const wrapper = mountStrip([file], fetchBlob)
    await flushPromises()
    await flushPromises()

    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('[data-testid="file-strip-loading"]').exists()).toBe(false)
    expect(wrapper.find('.file-box-icon.mdi-image-outline').exists()).toBe(true)
  })

  it('renders the mesh viewer with the fetched blob for the mesh category', async () => {
    const file = makeFile({ id: 1, category: 'mesh', file_name: 'part.stl' })
    const blob = new Blob(['x'], { type: 'model/stl' })
    const fetchBlob = vi.fn<(f: MachineStripFile) => Promise<Blob>>().mockResolvedValue(blob)

    const wrapper = mountStrip([file], fetchBlob)
    await flushPromises()
    await flushPromises()

    expect(fetchBlob).toHaveBeenCalledWith(file)
    expect(wrapper.findComponent({ name: 'MeshViewer' }).exists()).toBe(true)
    // Mesh hands MeshViewer the raw Blob directly, no object URL involved.
    expect(createObjectURL).not.toHaveBeenCalled()
  })

  it('embeds a non-interactive PDF preview for the drawing/pdf categories', async () => {
    const file = makeFile({ id: 1, category: 'drawing', file_name: 'drawing.pdf' })
    const fetchBlob = vi
      .fn<(f: MachineStripFile) => Promise<Blob>>()
      .mockResolvedValue(new Blob(['x'], { type: 'application/pdf' }))

    const wrapper = mountStrip([file], fetchBlob)
    await flushPromises()
    await flushPromises()

    const iframe = wrapper.find('iframe.file-box-pdf')
    expect(iframe.exists()).toBe(true)
    expect(iframe.attributes('src')).toBe('blob:mock-0#toolbar=0&navpanes=0&scrollbar=0&view=FitV')
    expect(iframe.attributes('tabindex')).toBe('-1')
  })

  it('coerces an untyped presigned blob to application/pdf so the embedded viewer renders it', async () => {
    const file = makeFile({ id: 1, category: 'pdf', file_name: 'cert.pdf' })
    // Simulates a presigned response with no MIME type on the blob.
    const fetchBlob = vi
      .fn<(f: MachineStripFile) => Promise<Blob>>()
      .mockResolvedValue(new Blob(['x']))

    mountStrip([file], fetchBlob)
    await flushPromises()
    await flushPromises()

    expect(createObjectURL).toHaveBeenCalledTimes(1)
    const typedBlob = createObjectURL.mock.calls[0]![0] as Blob
    expect(typedBlob.type).toBe('application/pdf')
  })

  it('opens the file preview dialog with the clicked file on click', async () => {
    const files = [
      makeFile({ id: 1, category: 'step', file_name: 'part.step', mime_type: 'application/step' }),
      makeFile({ id: 2, category: 'pdf', file_name: 'cert.pdf', mime_type: 'application/pdf' }),
    ]
    const fetchBlob = vi
      .fn<(f: MachineStripFile) => Promise<Blob>>()
      .mockResolvedValue(new Blob(['x'], { type: 'application/pdf' }))

    const wrapper = mountStrip(files, fetchBlob)
    await flushPromises()
    await flushPromises()

    const boxes = wrapper.findAll('.file-box')
    expect(boxes).toHaveLength(2)

    await boxes[0]!.trigger('click')
    await flushPromises()

    const dialog = wrapper.findComponent({ name: 'FilePreviewDialog' })
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('filename')).toBe('part.step')
    expect(dialog.props('mimeType')).toBe('application/step')
  })

  it('revokes a preview object URL once its file leaves the list, and revokes the rest on unmount', async () => {
    const files = [
      makeFile({ id: 1, category: 'image' }),
      makeFile({ id: 2, category: 'image' }),
    ]
    const fetchBlob = vi
      .fn<(f: MachineStripFile) => Promise<Blob>>()
      .mockResolvedValue(new Blob(['x'], { type: 'image/png' }))

    const wrapper = mountStrip(files, fetchBlob)
    await flushPromises()
    await flushPromises()

    expect(wrapper.findAll('img.file-box-image')).toHaveLength(2)

    await wrapper.setProps({ files: [files[1]!] })
    await flushPromises()
    await flushPromises()

    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock-0')
    expect(revokeObjectURL).not.toHaveBeenCalledWith('blob:mock-1')

    wrapper.unmount()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock-1')
  })
})
