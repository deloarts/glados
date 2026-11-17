import { describe, expect, it } from 'vitest'

import { apiErrorStatus } from '../errors'

describe('apiErrorStatus', () => {
  it('returns the status of an axios error response', () => {
    expect(apiErrorStatus({ isAxiosError: true, response: { status: 404, data: {} } })).toBe(404)
  })

  it('returns null for an axios error without a response', () => {
    expect(apiErrorStatus({ isAxiosError: true })).toBeNull()
  })

  it('returns null for anything that is not an axios error', () => {
    expect(apiErrorStatus(new Error('boom'))).toBeNull()
    expect(apiErrorStatus({ response: { status: 404 } })).toBeNull()
    expect(apiErrorStatus(null)).toBeNull()
  })
})
