import { describe, it, expect, vi, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import CatalogueItemMedia from '../CatalogueItemMedia.vue'

function makeBlob(content = 'x'): Blob {
  return new Blob([content], { type: 'application/octet-stream' })
}

function fetchBlobMock(): ReturnType<typeof vi.fn<(fileId: number) => Promise<Blob>>> {
  return vi.fn<(fileId: number) => Promise<Blob>>()
}

// `clientX`/`clientY` are getter-only on a real MouseEvent/PointerEvent
// instance, and VTU's `trigger(type, { clientX, clientY })` tries to assign
// them post-construction and throws. Building and dispatching the event
// directly sets them the only way the platform allows: as constructor init
// options.
function pointerEventAt(type: string, x: number, y: number): PointerEvent {
  return new PointerEvent(type, { bubbles: true, cancelable: true, clientX: x, clientY: y })
}

// MeshViewer does real three.js/WebGL work on mount that jsdom can't
// support (see LotRecordItem.spec.ts, which sidesteps the problem entirely
// by never giving its mesh tile a blob to render). This spec needs to
// exercise the mesh-tile branch itself, so every mount stubs MeshViewer via
// VTU's own component-resolution stubbing instead of `vi.mock`-ing the
// module, because `global.stubs` intercepts the async component before it's ever
// resolved, for *every* place it's referenced (this component's own
// `.media-tile` and FilePreviewDialog's internal mesh branch alike), so
// FilePreviewDialog itself can stay real everywhere, same as
// LotRecordItem.spec.ts's own `findComponent({ name: 'FilePreviewDialog' })`
// assertions.
function mountMedia(
  props: InstanceType<typeof CatalogueItemMedia>['$props'],
  slots: Record<string, string> = {},
) {
  return mountWithApp(CatalogueItemMedia, {
    props,
    slots,
    global: { stubs: { MeshViewer: true } },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('CatalogueItemMedia', () => {
  it('renders the default slot inside the thumbnail box', () => {
    const wrapper = mountMedia(
      { picture: null, meshFile: null, fetchBlob: fetchBlobMock() },
      { default: '<div class="thumb-stub">Thumb</div>' },
    )

    expect(wrapper.find('.thumb-box .thumb-stub').exists()).toBe(true)
  })

  it('shows no mesh tile when there is no mesh file and no placeholder', async () => {
    const wrapper = mountMedia({ picture: null, meshFile: null, fetchBlob: fetchBlobMock() })
    await flushPromises()

    expect(wrapper.find('.media-tile').exists()).toBe(false)
  })

  it('fetches and shows the mesh tile through fetchBlob once an on-record mesh file is given', async () => {
    const fetchBlob = fetchBlobMock().mockResolvedValue(makeBlob())
    const wrapper = mountMedia({ picture: null, meshFile: { id: 9, file_name: 'part.stl' }, fetchBlob })
    await flushPromises()
    await flushPromises()

    expect(fetchBlob).toHaveBeenCalledWith(9)
    expect(wrapper.find('.media-tile').exists()).toBe(true)
  })

  it('fetches and shows the mesh tile from meshPlaceholderUrl via a plain fetch, when there is no on-record mesh', async () => {
    const blob = makeBlob()
    const fetchMock = vi
      .fn<(url: string) => Promise<{ blob: () => Promise<Blob> }>>()
      .mockResolvedValue({ blob: () => Promise.resolve(blob) })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mountMedia({
      picture: null,
      meshFile: null,
      fetchBlob: fetchBlobMock(),
      meshPlaceholderUrl: 'https://example.test/default-mesh.stl',
    })
    await flushPromises()
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith('https://example.test/default-mesh.stl')
    expect(wrapper.find('.media-tile').exists()).toBe(true)
  })

  it('prefers the on-record mesh file over the placeholder when both are given', async () => {
    const fetchBlob = fetchBlobMock().mockResolvedValue(makeBlob())
    const fetchMock = vi.fn<(url: string) => Promise<{ blob: () => Promise<Blob> }>>()
    vi.stubGlobal('fetch', fetchMock)

    mountMedia({
      picture: null,
      meshFile: { id: 9, file_name: 'part.stl' },
      fetchBlob,
      meshPlaceholderUrl: 'https://example.test/default-mesh.stl',
    })
    await flushPromises()
    await flushPromises()

    expect(fetchBlob).toHaveBeenCalledWith(9)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('opens the preview dialog with the picture shown when the thumbnail is clicked', async () => {
    const fetchImage = vi.fn<() => Promise<Blob>>().mockResolvedValue(makeBlob())
    const wrapper = mountMedia(
      { picture: { id: 3, name: 'Photo', fetchImage }, meshFile: null, fetchBlob: fetchBlobMock() },
      { default: '<div class="thumb-stub">Thumb</div>' },
    )

    await wrapper.find('.thumb-box').trigger('click')
    await flushPromises()

    const dialog = wrapper.findComponent({ name: 'FilePreviewDialog' })
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('filename')).toBe('Photo')
    // A picture carries no mime type, so 'image/*' is the documented
    // stand-in that still routes FilePreviewDialog to its image branch
    // (`mimeType.startsWith('image/')`).
    expect(dialog.props('mimeType')).toBe('image/*')
    expect(fetchImage).toHaveBeenCalled()
  })

  it('does not open a preview when the thumbnail is clicked without a picture', async () => {
    const wrapper = mountMedia(
      { picture: null, meshFile: null, fetchBlob: fetchBlobMock() },
      { default: '<div class="thumb-stub">Thumb</div>' },
    )

    await wrapper.find('.thumb-box').trigger('click')
    await flushPromises()

    expect(wrapper.findComponent({ name: 'FilePreviewDialog' }).exists()).toBe(false)
  })

  it('opens the preview dialog with the mesh file on a plain click (no drag)', async () => {
    const fetchBlob = fetchBlobMock().mockResolvedValue(makeBlob())
    const wrapper = mountMedia({ picture: null, meshFile: { id: 9, file_name: 'part.stl' }, fetchBlob })
    await flushPromises()
    await flushPromises()

    const tile = wrapper.find('.media-tile')
    tile.element.dispatchEvent(pointerEventAt('pointerdown', 10, 10))
    tile.element.dispatchEvent(pointerEventAt('click', 10, 10))
    await flushPromises()

    const dialog = wrapper.findComponent({ name: 'FilePreviewDialog' })
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('filename')).toBe('part.stl')
  })

  it('does not open the preview when a drag ends inside the mesh tile', async () => {
    const fetchBlob = fetchBlobMock().mockResolvedValue(makeBlob())
    const wrapper = mountMedia({ picture: null, meshFile: { id: 9, file_name: 'part.stl' }, fetchBlob })
    await flushPromises()
    await flushPromises()

    const tile = wrapper.find('.media-tile')
    tile.element.dispatchEvent(pointerEventAt('pointerdown', 10, 10))
    tile.element.dispatchEvent(pointerEventAt('click', 60, 60))
    await flushPromises()

    expect(wrapper.findComponent({ name: 'FilePreviewDialog' }).exists()).toBe(false)
  })

  it('opens the placeholder mesh preview from the already-fetched blob, without a second fetch', async () => {
    const blob = makeBlob()
    const fetchMock = vi
      .fn<(url: string) => Promise<{ blob: () => Promise<Blob> }>>()
      .mockResolvedValue({ blob: () => Promise.resolve(blob) })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mountMedia({
      picture: null,
      meshFile: null,
      fetchBlob: fetchBlobMock(),
      meshPlaceholderUrl: 'https://example.test/default-mesh.stl',
    })
    await flushPromises()
    await flushPromises()

    const tile = wrapper.find('.media-tile')
    await tile.trigger('click')
    await flushPromises()

    const dialog = wrapper.findComponent({ name: 'FilePreviewDialog' })
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('filename')).toBe('default-mesh.stl')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('shows no drawing tile when there is no drawing file', async () => {
    const wrapper = mountMedia({ picture: null, meshFile: null, fetchBlob: fetchBlobMock() })
    await flushPromises()

    expect(wrapper.find('.media-tile--drawing').exists()).toBe(false)
  })

  it('fetches and shows the drawing tile as an object-URL iframe when a drawing file is given', async () => {
    const fetchBlob = fetchBlobMock().mockResolvedValue(
      new Blob(['%PDF-1.4'], { type: 'application/pdf' }),
    )
    const wrapper = mountMedia({
      picture: null,
      meshFile: null,
      fetchBlob,
      drawingFile: { id: 11, file_name: 'drawing.pdf' },
    })
    await flushPromises()
    await flushPromises()

    expect(fetchBlob).toHaveBeenCalledWith(11)
    const tile = wrapper.find('.media-tile--drawing')
    expect(tile.exists()).toBe(true)
    const iframe = tile.find('iframe')
    expect(iframe.exists()).toBe(true)
    expect(iframe.attributes('src')).toContain('blob:')
  })

  it('opens the preview dialog with the drawing file when its tile is clicked', async () => {
    const fetchBlob = fetchBlobMock().mockResolvedValue(
      new Blob(['%PDF-1.4'], { type: 'application/pdf' }),
    )
    const wrapper = mountMedia({
      picture: null,
      meshFile: null,
      fetchBlob,
      drawingFile: { id: 11, file_name: 'drawing.pdf' },
    })
    await flushPromises()
    await flushPromises()

    await wrapper.find('.media-tile--drawing').trigger('click')
    await flushPromises()

    const dialog = wrapper.findComponent({ name: 'FilePreviewDialog' })
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('filename')).toBe('drawing.pdf')
    expect(dialog.props('mimeType')).toBe('application/pdf')
  })
})
