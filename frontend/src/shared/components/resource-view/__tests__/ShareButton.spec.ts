import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import ShareButton from '../ShareButton.vue'

const PUBLIC_ID = '11111111-1111-1111-1111-111111111114'

function mountButton(publicId: string | null) {
  return mountWithApp(ShareButton, {
    props: { publicId },
    attachTo: document.body,
    global: { directives: { tooltip: Tooltip } },
  })
}

function stubClipboard() {
  const writeText = vi.fn<(value: string) => Promise<void>>(async () => {})
  vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText } })
  return writeText
}

// The menu is a popup, so its entries render outside the component.
async function pick(wrapper: ReturnType<typeof mountButton>, entry: 'link' | 'uuid') {
  await wrapper.find('[data-testid="share-button"]').trigger('click')
  await flushPromises()
  const item = document.body.querySelector(`[data-testid="share-copy-${entry}"]`)
  expect(item).toBeTruthy()
  item!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
  await flushPromises()
}

afterEach(() => vi.unstubAllGlobals())

describe('ShareButton', () => {
  it("copies the lasting link through the record's public id from Copy Link", async () => {
    const writeText = stubClipboard()
    const wrapper = mountButton(PUBLIC_ID)

    await pick(wrapper, 'link')

    expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/resolve/${PUBLIC_ID}`)
    wrapper.unmount()
  })

  it('copies the public id as plain text from Copy UUID', async () => {
    const writeText = stubClipboard()
    const wrapper = mountButton(PUBLIC_ID)

    await pick(wrapper, 'uuid')

    expect(writeText).toHaveBeenCalledWith(PUBLIC_ID)
    wrapper.unmount()
  })

  it('copies nothing on the button itself, which only opens the menu', async () => {
    const writeText = stubClipboard()
    const wrapper = mountButton(PUBLIC_ID)

    await wrapper.find('[data-testid="share-button"]').trigger('click')
    await flushPromises()

    expect(writeText).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('stays hidden until the record is loaded', () => {
    expect(mountButton(null).find('[data-testid="share-button"]').exists()).toBe(false)
  })
})
