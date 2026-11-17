import { describe, it, expect, vi, beforeEach } from 'vitest'

import { streamSse } from '../sseClient'
import type { SseFrame } from '../sseParser'

function bodyStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)))
      controller.close()
    },
  })
}

function fakeResponse(chunks: string[]): Response {
  return { ok: true, body: bodyStream(chunks) } as unknown as Response
}

describe('streamSse', () => {
  const fetchMock = vi.fn<typeof fetch>()

  beforeEach(() => {
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
  })

  it('defaults to a GET request with no body when method/body are not set (liveStore.ts usage unchanged)', async () => {
    fetchMock.mockResolvedValue(fakeResponse([]))
    const onOpen = vi.fn<() => void>()

    await streamSse(
      { url: '/x', headers: () => ({ Authorization: 'Bearer t' }), onOpen, onFrame: vi.fn<(frame: SseFrame) => void>() },
      new AbortController().signal,
    )

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const init = fetchMock.mock.calls[0]![1]!
    expect(init.method).toBe('GET')
    expect(init.body).toBeUndefined()
    expect(init.headers).toEqual({ Authorization: 'Bearer t' })
    expect(onOpen).toHaveBeenCalledTimes(1)
  })

  it('always sends credentials, so the httponly session cookie rides along', async () => {
    fetchMock.mockResolvedValue(fakeResponse([]))

    await streamSse(
      { url: '/x', headers: () => ({}), onOpen: () => {}, onFrame: vi.fn<(frame: SseFrame) => void>() },
      new AbortController().signal,
    )

    const init = fetchMock.mock.calls[0]![1]!
    expect(init.credentials).toBe('include')
  })

  it('passes method, body, and headers through for a POST stream', async () => {
    fetchMock.mockResolvedValue(fakeResponse([]))

    await streamSse(
      {
        url: '/y',
        method: 'POST',
        body: '{"a":1}',
        headers: () => ({ Authorization: 'Bearer t', 'Content-Type': 'application/json' }),
        onOpen: () => {},
        onFrame: vi.fn<(frame: SseFrame) => void>(),
      },
      new AbortController().signal,
    )

    const init = fetchMock.mock.calls[0]![1]!
    expect(init.method).toBe('POST')
    expect(init.body).toBe('{"a":1}')
    expect(init.headers).toEqual({ Authorization: 'Bearer t', 'Content-Type': 'application/json' })
  })

  it('delivers parsed frames to onFrame in order', async () => {
    fetchMock.mockResolvedValue(
      fakeResponse(['event: progress\ndata: {"a":1}\n\n', 'event: result\ndata: {"b":2}\n\n']),
    )
    const frames: SseFrame[] = []

    await streamSse(
      { url: '/z', headers: () => ({}), onOpen: () => {}, onFrame: (frame) => frames.push(frame) },
      new AbortController().signal,
    )

    expect(frames).toEqual([
      { event: 'progress', data: '{"a":1}' },
      { event: 'result', data: '{"b":2}' },
    ])
  })
})
