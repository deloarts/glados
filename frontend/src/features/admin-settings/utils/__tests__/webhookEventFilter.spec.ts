import { describe, it, expect } from 'vitest'
import { FilterService } from '@openvue/core/api'

import { matchesWebhookEvent, WEBHOOK_EVENT_MATCH_MODE } from '../webhookEventFilter'

describe('matchesWebhookEvent', () => {
  it('keeps every row while no event is picked', () => {
    expect(matchesWebhookEvent(['lot.created'], null)).toBe(true)
    expect(matchesWebhookEvent(['lot.created'], '')).toBe(true)
  })

  it('keeps a subscription that lists the picked event and drops one that does not', () => {
    expect(matchesWebhookEvent(['lot.created', 'order.updated'], 'order.updated')).toBe(true)
    expect(matchesWebhookEvent(['lot.created'], 'order.updated')).toBe(false)
  })

  it('keeps a catch-all subscription for any picked event', () => {
    expect(matchesWebhookEvent(['*'], 'order.updated')).toBe(true)
  })

  it('does not treat a partial event name as a match', () => {
    expect(matchesWebhookEvent(['lot.created'], 'lot')).toBe(false)
  })

  it('is registered with the OpenVue FilterService', () => {
    const registry = (FilterService as unknown as { filters: Record<string, unknown> }).filters
    expect(registry[WEBHOOK_EVENT_MATCH_MODE]).toBe(matchesWebhookEvent)
  })
})
