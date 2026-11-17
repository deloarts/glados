import { describe, it, expect } from 'vitest'

import { extractApiError, extractApiErrorCode } from '../errors'

function axiosError(data: unknown, status = 400) {
  return {
    isAxiosError: true,
    response: { status, data },
  }
}

describe('extractApiError', () => {
  it('returns a plain string detail unchanged', () => {
    expect(extractApiError(axiosError({ detail: 'Something went wrong' }))).toBe(
      'Something went wrong',
    )
  })

  it('formats a FastAPI 422 validation error into "field: message"', () => {
    const err = axiosError(
      {
        detail: [{ type: 'missing', loc: ['body', 'username'], msg: 'Field required' }],
      },
      422,
    )
    expect(extractApiError(err)).toBe('username: Field required')
  })

  it('joins a nested field path with dots', () => {
    const err = axiosError(
      {
        detail: [
          { type: 'int_parsing', loc: ['body', 'items', 0, 'quantity'], msg: 'Invalid integer' },
        ],
      },
      422,
    )
    expect(extractApiError(err)).toBe('items.0.quantity: Invalid integer')
  })

  it('uses the first error when there are several', () => {
    const err = axiosError(
      {
        detail: [
          { type: 'missing', loc: ['body', 'username'], msg: 'Field required' },
          { type: 'missing', loc: ['body', 'password'], msg: 'Field required' },
        ],
      },
      422,
    )
    expect(extractApiError(err)).toBe('username: Field required')
  })

  it('falls back to the message alone when loc has no field path', () => {
    const err = axiosError(
      { detail: [{ type: 'value_error', loc: ['body'], msg: 'Bad body' }] },
      422,
    )
    expect(extractApiError(err)).toBe('Bad body')
  })

  it('returns null for a non-axios error', () => {
    expect(extractApiError(new Error('boom'))).toBeNull()
  })

  it('returns null when there is no detail at all', () => {
    expect(extractApiError(axiosError({}))).toBeNull()
  })

  it('returns null for an empty validation error array', () => {
    expect(extractApiError(axiosError({ detail: [] }, 422))).toBeNull()
  })

  it('returns null when the array items are not validation-error shaped', () => {
    expect(extractApiError(axiosError({ detail: ['just a string'] }, 422))).toBeNull()
  })
})

describe('extractApiErrorCode', () => {
  it('returns the domain error code next to the detail', () => {
    expect(
      extractApiErrorCode(axiosError({ detail: 'Wait a moment.', code: 'TimeTrackingRateLimitedError' }, 429)),
    ).toBe('TimeTrackingRateLimitedError')
  })

  it('returns null without a string code or for a non-API error', () => {
    expect(extractApiErrorCode(axiosError({ detail: 'x' }))).toBeNull()
    expect(extractApiErrorCode(new Error('network'))).toBeNull()
  })
})
