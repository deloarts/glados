import { describe, it, expect, vi, afterEach } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'

import FilePreviewDialog from '../FilePreviewDialog.vue'

const mounted: VueWrapper[] = []

function mountDialog(
  fetchBlob = vi.fn<() => Promise<Blob>>().mockResolvedValue(new Blob(['x'], { type: 'image/png' })),
) {
  const wrapper = mountWithApp(FilePreviewDialog, {
    attachTo: document.body,
    props: {
      visible: true,
      filename: 'photo.png',
      mimeType: 'image/png',
      fetchBlob,
    },
  })
  mounted.push(wrapper)
  return wrapper
}

// Dialog teleports its actual markup out to document.body (openvue/dialog's
// own <Portal :appendTo="appendTo">, defaulting to 'body'); the inline
// style this component binds lands on that teleported role="dialog" element via
// OpenVue's own attrs-merging (ptmi), not as a readable Vue prop on the
// Dialog component instance itself, so assertions read the real DOM style
// attribute rather than `dialog.props('style')`.
function dialogStyleAttr(): string {
  return document.querySelector('[role="dialog"]')?.getAttribute('style') ?? ''
}

describe('FilePreviewDialog', () => {
  afterEach(() => {
    for (const wrapper of mounted) wrapper.unmount()
    mounted.length = 0
  })

  it('is maximizable, and starts with the default width/height style', async () => {
    mountDialog()
    await flushPromises()

    const style = dialogStyleAttr()
    expect(style).toContain('width: var(--dialog-width-full)')
    expect(style).toContain('max-width: 1200px')
    expect(style).toContain('height: 92vh')
  })

  // OpenVue's own `.p-dialog-maximized` CSS rule sets width and height to
  // 100vw/100vh with `!important`, strong enough to beat an inline style,
  // but only for the properties it declares. It says nothing about
  // max-width, so an inline maxWidth would stay in effect uncontested and
  // cap the maximized width even though the un-competed !important height
  // rule expands freely. Dropping every dimension from
  // the inline style while maximized (not just max-width) leaves nothing
  // left to fight the CSS rule, in either direction.
  it('drops the inline width/maxWidth/height style entirely once maximized, so the CSS rule expands both dimensions unopposed', async () => {
    const wrapper = mountDialog()
    await flushPromises()

    const dialog = wrapper.findComponent({ name: 'Dialog' })
    await dialog.vm.$emit('maximize')
    await flushPromises()

    expect(dialogStyleAttr()).not.toContain('width')
    expect(dialogStyleAttr()).not.toContain('height')
  })

  it('restores the default style on unmaximize', async () => {
    const wrapper = mountDialog()
    await flushPromises()

    const dialog = wrapper.findComponent({ name: 'Dialog' })
    await dialog.vm.$emit('maximize')
    await flushPromises()
    expect(dialogStyleAttr()).not.toContain('width')

    await dialog.vm.$emit('unmaximize')
    await flushPromises()
    const style = dialogStyleAttr()
    expect(style).toContain('width: var(--dialog-width-full)')
    expect(style).toContain('max-width: 1200px')
    expect(style).toContain('height: 92vh')
  })

  it('resets out of the maximized state when the dialog closes, so the next open starts un-maximized', async () => {
    const wrapper = mountDialog()
    await flushPromises()

    const dialog = wrapper.findComponent({ name: 'Dialog' })
    await dialog.vm.$emit('maximize')
    await flushPromises()
    expect(dialogStyleAttr()).not.toContain('width')

    await dialog.vm.$emit('hide')
    await flushPromises()
    const style = dialogStyleAttr()
    expect(style).toContain('width: var(--dialog-width-full)')
    expect(style).toContain('max-width: 1200px')
    expect(style).toContain('height: 92vh')
  })
})
