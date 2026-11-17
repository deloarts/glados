import { ref } from 'vue'
import { defineStore } from 'pinia'

import { idleHeaders } from '@/core/session/userActivity'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'

import { streamSse, SseHttpError } from './sseClient'
import { LIVE_RECONNECT_DELAYS_MS, LIVE_RECONNECT_JITTER_RATIO, LIVE_STREAM_URL } from './constants'

import type { LiveSignal } from './types'

export type LiveStatus = 'idle' | 'connecting' | 'open' | 'closed'

export const useLiveStore = defineStore('live', () => {
  const status = ref<LiveStatus>('idle')
  // Bumped on every successful reconnect (and on a server-requested
  // resync). Tables watch this to recover from whatever they missed while
  // disconnected; see useLiveRows.
  const reconnectCount = ref(0)

  // Plain closure state, not refs: subscriber callbacks must never become
  // reactive, and none of this needs to drive a template.
  const subscribers = new Map<string, Set<(signal: LiveSignal) => void>>()
  let controller: AbortController | null = null
  let retryTimeout: ReturnType<typeof setTimeout> | null = null
  let attempt = 0
  let hasConnectedBefore = false
  let stopped = true
  let runToken = 0

  // ── Subscription ────────────────────────────────────────────────────

  function on(resource: string, handler: (signal: LiveSignal) => void): () => void {
    let set = subscribers.get(resource)
    if (!set) {
      set = new Set()
      subscribers.set(resource, set)
    }
    set.add(handler)

    return () => {
      set.delete(handler)
      if (set.size === 0) subscribers.delete(resource)
    }
  }

  function dispatch(signal: LiveSignal): void {
    subscribers.get(signal.resource)?.forEach((handler) => handler(signal))
  }

  // ── Connection lifecycle ────────────────────────────────────────────

  function nextDelay(): number {
    const index = Math.min(attempt, LIVE_RECONNECT_DELAYS_MS.length - 1)
    const base = LIVE_RECONNECT_DELAYS_MS[index] ?? LIVE_RECONNECT_DELAYS_MS[0]!
    attempt++
    const jitter = base * LIVE_RECONNECT_JITTER_RATIO
    return base + (Math.random() * 2 - 1) * jitter
  }

  function scheduleRetry(token: number): void {
    const delay = nextDelay()
    retryTimeout = setTimeout(() => {
      retryTimeout = null
      if (token !== runToken) return
      void runOnce(token)
    }, delay)
  }

  async function runOnce(token: number): Promise<void> {
    if (stopped || token !== runToken) return

    status.value = 'connecting'
    controller = new AbortController()

    try {
      await streamSse(
        {
          url: LIVE_STREAM_URL,
          // No Authorization header: the session cookie
          // authenticates this GET, credentials: 'include' (see
          // sseClient.ts) is what makes the browser attach it. A
          // reconnect is no activity of the user's.
          headers: () => idleHeaders(),
          onOpen: () => {
            attempt = 0
            status.value = 'open'
            if (hasConnectedBefore) reconnectCount.value++
            hasConnectedBefore = true
          },
          onFrame: (frame) => {
            if (frame.event === 'signal') {
              try {
                const signals = JSON.parse(frame.data) as LiveSignal[]
                signals.forEach(dispatch)
              } catch {
                // Malformed frame, ignored; a reconnect/resync self-heals
                // any gap this leaves.
              }
            } else if (frame.event === 'resync') {
              reconnectCount.value++
            }
          },
        },
        controller.signal,
      )
    } catch (err) {
      if (err instanceof SseHttpError && err.status === 401) {
        stop()
        useCurrentUserStore().logout()
        return
      }
      // Network error, non-401 HTTP error, or our own abort() on stop():
      // all fall through to the retry path below (a no-op if stopped).
    }

    if (stopped || token !== runToken) return
    status.value = 'closed'
    scheduleRetry(token)
  }

  function start(): void {
    if (!stopped) return
    stopped = false
    runToken++
    void runOnce(runToken)
  }

  function stop(): void {
    stopped = true
    runToken++
    controller?.abort()
    controller = null
    if (retryTimeout) {
      clearTimeout(retryTimeout)
      retryTimeout = null
    }
    status.value = 'idle'
  }

  // Cancels a pending backoff wait and reconnects immediately. A no-op if
  // already connecting/open, there's nothing to retry. Used on
  // visibilitychange -> visible, so a tab that was backgrounded through
  // several backoff steps catches up right away instead of waiting out
  // whatever delay it was on.
  function retryNow(): void {
    if (stopped || !retryTimeout) return
    clearTimeout(retryTimeout)
    retryTimeout = null
    attempt = 0
    void runOnce(runToken)
  }

  function handleVisibilityChange(): void {
    if (document.visibilityState === 'visible') retryNow()
  }

  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', handleVisibilityChange)
  }

  return {
    status,
    reconnectCount,
    on,
    start,
    stop,
    retryNow,
  }
})
