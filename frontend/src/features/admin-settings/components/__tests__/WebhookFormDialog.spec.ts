import { describe, it, expect, vi } from 'vitest'
import { flushPromises, DOMWrapper } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'

const put = vi.fn<() => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    put: () => put(),
  },
}))

import WebhookFormDialog from '../WebhookFormDialog.vue'

const subscription = {
  id: 1,
  public_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  name: 'Existing hook',
  url: 'https://example.com/hook',
  event_types: ['order.created'],
  is_active: true,
  created: '2026-01-01',
  creator_id: 1,
}

function mountDialog() {
  return mountWithApp(WebhookFormDialog, {
    attachTo: document.body,
    props: {
      // Mount closed first, then open. The dialog only populates its form
      // from `watch(visible, ...)`, which fires on a false -> true
      // transition, not on an initial `visible: true` mount.
      visible: false,
      subscription,
      eventTypes: ['order.created'],
    },
  })
}

describe('WebhookFormDialog', () => {
  // A failed save shows the error inline via a <Message>, like every
  // sibling FormDialog (ArticleGroupFormDialog etc.), so it survives even
  // after a toast would have faded.
  it('shows an inline error Message instead of a toast when saving fails', async () => {
    put.mockRejectedValue(new Error('network down'))

    const wrapper = mountDialog()
    await flushPromises()
    await wrapper.setProps({ visible: true })
    await flushPromises()
    await flushPromises()

    expect(wrapper.findComponent({ name: 'Message' }).exists()).toBe(false)

    const saveButton = Array.from(document.body.querySelectorAll('.dialog-footer button')).find(
      (button) => button.textContent?.includes(i18n.global.t('common.save')),
    )
    expect(saveButton).toBeDefined()

    await new DOMWrapper(saveButton!).trigger('click')
    await flushPromises()

    const message = wrapper.findComponent({ name: 'Message' })
    expect(message.exists()).toBe(true)
    expect(message.text()).toBe(i18n.global.t('adminSettings.notifications.webhooks.saveFailed'))

    wrapper.unmount()
  })
})
