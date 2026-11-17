import { describe, it, expect, vi, beforeEach } from 'vitest'

import type { SseFrame } from '@/core/realtime/sseParser'

interface FakeStreamOptions {
  headers: () => Record<string, string>
  onOpen: () => void
  onFrame: (frame: SseFrame) => void
}

const streamSseMock = vi.fn<(options: FakeStreamOptions, signal: AbortSignal) => Promise<void>>()

vi.mock('@/core/realtime/sseClient', () => ({
  streamSse: (options: FakeStreamOptions, signal: AbortSignal) => streamSseMock(options, signal),
}))

import { streamAutoPlanSchedule, AutoPlanConnectionLostError } from '../autoPlanScheduleStream'
import type { AutoPlanProgressEvent, AutoPlanRequest } from '../../types/scheduleBoardResponse'

const payload = {} as AutoPlanRequest

describe('streamAutoPlanSchedule', () => {
  beforeEach(() => {
    streamSseMock.mockReset()
  })

  it('invokes onProgress for each progress frame in order and resolves with the parsed result frame', async () => {
    streamSseMock.mockImplementation(async (options) => {
      options.onFrame({ event: 'progress', data: '{"stage":"preparing","current":null,"total":null,"order":null}' })
      options.onFrame({ event: 'progress', data: '{"stage":"placing","current":1,"total":2,"order":null}' })
      options.onFrame({ event: 'result', data: '{"proposals":[]}' })
    })
    const onProgress = vi.fn<(ev: AutoPlanProgressEvent) => void>()

    const result = await streamAutoPlanSchedule(payload, onProgress, new AbortController().signal)

    expect(onProgress).toHaveBeenNthCalledWith(1, {
      stage: 'preparing',
      current: null,
      total: null,
      order: null,
    })
    expect(onProgress).toHaveBeenNthCalledWith(2, { stage: 'placing', current: 1, total: 2, order: null })
    expect(result).toEqual({ proposals: [] })
  })

  it('rejects with an Error whose message is the detail on an error frame', async () => {
    streamSseMock.mockImplementation(async (options) => {
      options.onFrame({ event: 'error', data: '{"detail":"boom"}' })
    })

    await expect(
      streamAutoPlanSchedule(payload, vi.fn<(ev: AutoPlanProgressEvent) => void>(), new AbortController().signal),
    ).rejects.toThrow('boom')
  })

  it('rejects with AutoPlanConnectionLostError when the stream ends with no terminal frame', async () => {
    streamSseMock.mockImplementation(async () => {
      // Stream closes cleanly (server or network) without a result/error frame.
    })

    await expect(
      streamAutoPlanSchedule(payload, vi.fn<(ev: AutoPlanProgressEvent) => void>(), new AbortController().signal),
    ).rejects.toBeInstanceOf(AutoPlanConnectionLostError)
  })

  it('sends the CSRF header and no Authorization header - the session cookie authenticates the request', async () => {
    let capturedHeaders: Record<string, string> = {}
    streamSseMock.mockImplementation(async (options) => {
      capturedHeaders = options.headers()
      options.onFrame({ event: 'result', data: '{"proposals":[]}' })
    })

    await streamAutoPlanSchedule(payload, vi.fn<(ev: AutoPlanProgressEvent) => void>(), new AbortController().signal)

    expect(capturedHeaders['X-Requested-With']).toBe('glados')
    expect(capturedHeaders.Authorization).toBeUndefined()
  })

  it('skips a malformed progress frame silently, without rejecting or calling onProgress', async () => {
    streamSseMock.mockImplementation(async (options) => {
      options.onFrame({ event: 'progress', data: 'not json' })
      options.onFrame({ event: 'result', data: '{"proposals":[]}' })
    })
    const onProgress = vi.fn<(ev: AutoPlanProgressEvent) => void>()

    const result = await streamAutoPlanSchedule(payload, onProgress, new AbortController().signal)

    expect(onProgress).not.toHaveBeenCalled()
    expect(result).toEqual({ proposals: [] })
  })
})
