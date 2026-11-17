import { describe, it, expect, vi } from 'vitest'
import { AxiosError, AxiosHeaders } from 'axios'

import { IDEMPOTENCY_HEADER, newIdempotencyKey, sendIdempotent } from '../idempotency'
import type { WebRequestConfig } from '../webRequest'

function keyOf(config: WebRequestConfig): unknown {
  return (config.headers as Record<string, unknown>)[IDEMPOTENCY_HEADER]
}

function answered(status: number, code?: string): AxiosError {
  const config = { headers: new AxiosHeaders() }
  return new AxiosError('failed', undefined, config, undefined, {
    status,
    statusText: '',
    data: code ? { code } : {},
    headers: {},
    config,
  })
}

describe('newIdempotencyKey', () => {
  it('makes a version 4 UUID, a new one each time', () => {
    const key = newIdempotencyKey()
    expect(key).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
    expect(newIdempotencyKey()).not.toBe(key)
  })
})

describe('sendIdempotent', () => {
  it('sends again with the same key when the answer is lost', async () => {
    vi.useFakeTimers()
    const send = vi
      .fn<(config: WebRequestConfig) => Promise<string>>()
      .mockRejectedValueOnce(new AxiosError('Network Error'))
      .mockResolvedValueOnce('booked')

    const sent = sendIdempotent(send)
    await vi.runAllTimersAsync()

    await expect(sent).resolves.toBe('booked')
    expect(send).toHaveBeenCalledTimes(2)
    expect(keyOf(send.mock.calls[1]![0])).toBe(keyOf(send.mock.calls[0]![0]))
    vi.useRealTimers()
  })

  it('does not send again when the server answered the request', async () => {
    const send = vi
      .fn<(config: WebRequestConfig) => Promise<string>>()
      .mockRejectedValue(answered(422))

    await expect(sendIdempotent(send)).rejects.toBeInstanceOf(AxiosError)
    expect(send).toHaveBeenCalledTimes(1)
  })

  it('does not send again into maintenance mode', async () => {
    const send = vi
      .fn<(config: WebRequestConfig) => Promise<string>>()
      .mockRejectedValue(answered(503, 'MaintenanceModeError'))

    await expect(sendIdempotent(send)).rejects.toBeInstanceOf(AxiosError)
    expect(send).toHaveBeenCalledTimes(1)
  })
})
