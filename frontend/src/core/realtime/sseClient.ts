import { createSseParser } from './sseParser'
import type { SseFrame } from './sseParser'

export class SseHttpError extends Error {
  constructor(public readonly status: number) {
    super(`SSE stream request failed with status ${status}`)
  }
}

export interface SseClientOptions {
  url: string
  headers: () => Record<string, string>
  onOpen: () => void
  onFrame: (frame: SseFrame) => void
  // Defaults to 'GET'. Lets a caller open a POST-body stream (e.g.
  // auto-plan/stream) through the same fetch-based client; liveStore.ts
  // never sets these.
  method?: 'GET' | 'POST'
  body?: string
}

/**
 * Opens one SSE connection via fetch + ReadableStream and resolves once the
 * stream ends (server closed it, the network dropped, or `signal` aborted).
 * Reconnection/backoff is the caller's concern (see liveStore.ts); this is
 * a single attempt.
 *
 * Hand-rolled rather than a library: native EventSource can't send an
 * Authorization header, and @microsoft/fetch-event-source (the other usual
 * choice) is unmaintained and mainly adds Last-Event-ID replay, which this
 * feature doesn't want: a signal is a cache-invalidation hint, not
 * something to persist and replay; recovery after a reconnect is a full
 * refetch (see useLiveRows' reconnectCount watch), not resuming a log.
 */
export async function streamSse(options: SseClientOptions, signal: AbortSignal): Promise<void> {
  const response = await fetch(options.url, {
    method: options.method ?? 'GET',
    headers: options.headers(),
    body: options.body,
    // The session lives in an httponly cookie, and fetch's default
    // credentials mode ('same-origin') would drop it on the cross-port
    // dev setup (frontend :5173, backend :3000); 'include' always sends
    // it, matching the axios instance's withCredentials.
    credentials: 'include',
    signal,
  })

  if (!response.ok) {
    throw new SseHttpError(response.status)
  }
  if (!response.body) {
    throw new Error('SSE response has no body')
  }

  options.onOpen()

  const parser = createSseParser(options.onFrame)
  const reader = response.body.getReader()
  const decoder = new TextDecoder()

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) return
      parser.push(decoder.decode(value, { stream: true }))
    }
  } finally {
    reader.releaseLock()
  }
}
