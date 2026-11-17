import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import ShareButton from '../ShareButton.vue'

const PUBLIC_ID = '11111111-1111-1111-1111-111111111114'

function mountButton(publicId: string | null) {
  return mountWithApp(ShareButton, { props: { publicId }, global: { directives: { tooltip: Tooltip } } })
}

afterEach(() => vi.unstubAllGlobals())

describe('ShareButton', () => {
  it("copies the lasting link through the record's public id", async () => {
    const writeText = vi.fn<(value: string) => Promise<void>>(async () => {})
    vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText } })
    const wrapper = mountButton(PUBLIC_ID)

    await wrapper.find('[data-testid="share-button"]').trigger('click')
    await flushPromises()

    expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/resolve/${PUBLIC_ID}`)
  })

  it('stays hidden until the record is loaded', () => {
    expect(mountButton(null).find('[data-testid="share-button"]').exists()).toBe(false)
  })
})
