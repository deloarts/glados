import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'

import type { WebhookSubscription } from '../../types/webhookTypes'

const getWebhookSubscriptionsMock = vi.fn<() => Promise<WebhookSubscription[]>>()

vi.mock('../../api/getWebhookSubscriptions', () => ({
  getWebhookSubscriptions: () => getWebhookSubscriptionsMock(),
}))
vi.mock('../../api/getWebhookEventTypes', () => ({
  getWebhookEventTypes: () => Promise.resolve(['*', 'lot.created', 'order.updated']),
}))

import WebhookSubscriptionsPanel from '../WebhookSubscriptionsPanel.vue'

function makeSubscription(overrides: Partial<WebhookSubscription>): WebhookSubscription {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    name: 'Hook',
    url: 'https://example.com/hook',
    event_types: ['*'],
    is_active: true,
    created: '2026-09-01T10:00:00Z',
    creator_id: 1,
    ...overrides,
  } as WebhookSubscription
}

async function mountPanel() {
  const wrapper = mountWithApp(WebhookSubscriptionsPanel, {
    props: { canWrite: true },
    global: { plugins: [ConfirmationService] },
  })
  await flushPromises()
  return wrapper
}

// What a Select emits when an option is picked: the model update, then the
// change event the cell's filterCallback listens to.
async function pick(select: VueWrapper, value: unknown) {
  select.vm.$emit('update:modelValue', value)
  select.vm.$emit('change', { originalEvent: new Event('change'), value })
  await flushPromises()
}

function rowNames(wrapper: Awaited<ReturnType<typeof mountPanel>>): string[] {
  return wrapper
    .findAll('tbody tr')
    .map((row) => row.findAll('td')[0]?.text() ?? '')
    .filter((name) => name !== '')
}

describe('WebhookSubscriptionsPanel row filters', () => {
  beforeEach(() => {
    getWebhookSubscriptionsMock.mockReset()
    getWebhookSubscriptionsMock.mockResolvedValue([
      makeSubscription({ id: 1, name: 'Lots', event_types: ['lot.created'] }),
      makeSubscription({ id: 2, name: 'Orders', event_types: ['order.updated'], is_active: false }),
      makeSubscription({ id: 3, name: 'Everything', event_types: ['*'] }),
    ])
  })

  it('narrows the rows by name in the browser', async () => {
    const wrapper = await mountPanel()
    expect(rowNames(wrapper)).toEqual(['Lots', 'Orders', 'Everything'])

    // A real input event, so the cell's filterCallback runs as it does when typing.
    await wrapper.findAllComponents({ name: 'InputText' })[0]!.find('input').setValue('ord')
    await flushPromises()

    expect(rowNames(wrapper)).toEqual(['Orders'])
  })

  it('keeps catch-all subscriptions when filtering by event', async () => {
    const wrapper = await mountPanel()

    const eventSelect = wrapper.findAllComponents({ name: 'Select' })[0]!
    expect(eventSelect.props('options')).toEqual(['lot.created', 'order.updated'])
    await pick(eventSelect, 'lot.created')

    expect(rowNames(wrapper)).toEqual(['Lots', 'Everything'])
  })

  it('narrows the rows by active status', async () => {
    const wrapper = await mountPanel()

    await pick(wrapper.findAllComponents({ name: 'Select' })[1]!, false)

    expect(rowNames(wrapper)).toEqual(['Orders'])
  })
})
