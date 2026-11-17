import { describe, expect, it } from 'vitest'

import { offeredManualStatuses } from '../demandStatus'
import {
  allHaveAction,
  anyHasAction,
  anyOffersAction,
  blockingPermission,
  hasAction,
  offersAction,
} from '../lifecycleActions'

describe('hasAction', () => {
  it('reads the actions the response offers', () => {
    expect(hasAction({ actions: ['cancel', 'deliver'] }, 'deliver')).toBe(true)
    expect(hasAction({ actions: ['cancel'] }, 'deliver')).toBe(false)
  })

  it('offers nothing for a missing response or a response without actions', () => {
    expect(hasAction(null, 'cancel')).toBe(false)
    expect(hasAction(undefined, 'cancel')).toBe(false)
    expect(hasAction({}, 'cancel')).toBe(false)
    expect(hasAction({ actions: null }, 'cancel')).toBe(false)
  })
})

describe('allHaveAction and anyHasAction', () => {
  const offered = { actions: ['fulfil'] }
  const refused = { actions: [] }

  it('needs the action on every response, and at least one response', () => {
    expect(allHaveAction([offered, offered], 'fulfil')).toBe(true)
    expect(allHaveAction([offered, refused], 'fulfil')).toBe(false)
    expect(allHaveAction([], 'fulfil')).toBe(false)
  })

  it('needs the action on one response', () => {
    expect(anyHasAction([refused, offered], 'fulfil')).toBe(true)
    expect(anyHasAction([refused], 'fulfil')).toBe(false)
  })
})

describe('blocked actions', () => {
  const blocked = { actions: ['deliver'], blocked_actions: { cancel: 'manage:orders' } }

  it('names the permission a blocked action lacks', () => {
    expect(blockingPermission(blocked, 'cancel')).toBe('manage:orders')
    expect(blockingPermission(blocked, 'deliver')).toBeNull()
    expect(blockingPermission({ actions: ['cancel'] }, 'cancel')).toBeNull()
    expect(blockingPermission(null, 'cancel')).toBeNull()
  })

  it('offers an action that is allowed or blocked, but not one the state refuses', () => {
    expect(offersAction(blocked, 'cancel')).toBe(true)
    expect(offersAction(blocked, 'deliver')).toBe(true)
    expect(offersAction(blocked, 'close_short')).toBe(false)
    expect(hasAction(blocked, 'cancel')).toBe(false)
    expect(anyOffersAction([{ actions: [] }, blocked], 'cancel')).toBe(true)
    expect(anyOffersAction([{ actions: [] }], 'cancel')).toBe(false)
  })
})

describe('offeredManualStatuses', () => {
  it('offers the manual statuses whose action the demand offers', () => {
    expect(offeredManualStatuses({ actions: ['cancel', 'fulfil', 'allocate'] })).toEqual([
      'fulfilled',
      'canceled',
    ])
    expect(offeredManualStatuses({ actions: ['remove'] })).toEqual([])
  })
})
