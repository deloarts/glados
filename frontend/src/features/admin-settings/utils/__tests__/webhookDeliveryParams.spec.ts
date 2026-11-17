import { describe, it, expect } from 'vitest'

import { buildWebhookDeliveryParams, type WebhookDeliveryFilterValues } from '../webhookDeliveryParams'

const EMPTY: WebhookDeliveryFilterValues = {
  outcome: null,
  eventType: null,
  attemptedFrom: null,
  attemptedTo: null,
}

describe('buildWebhookDeliveryParams', () => {
  it('sends only the page while no filter is set', () => {
    expect(buildWebhookDeliveryParams({ skip: 10, limit: 10 }, EMPTY)).toEqual({ skip: 10, limit: 10 })
  })

  it('maps the outcome to the success flag, both ways', () => {
    expect(buildWebhookDeliveryParams({ skip: 0, limit: 10 }, { ...EMPTY, outcome: 'success' })).toEqual({
      skip: 0,
      limit: 10,
      success: true,
    })
    expect(buildWebhookDeliveryParams({ skip: 0, limit: 10 }, { ...EMPTY, outcome: 'failed' })).toEqual({
      skip: 0,
      limit: 10,
      success: false,
    })
  })

  it('maps the event type and the attempted day range', () => {
    const params = buildWebhookDeliveryParams(
      { skip: 0, limit: 10 },
      {
        ...EMPTY,
        eventType: 'lot.created',
        attemptedFrom: new Date(2026, 8, 1),
        attemptedTo: new Date(2026, 8, 2),
      },
    )

    expect(params).toEqual({
      skip: 0,
      limit: 10,
      event_type: 'lot.created',
      attempted_from: '2026-09-01',
      attempted_to: '2026-09-02',
    })
  })
})
