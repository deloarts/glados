import { streamSse } from '@/core/realtime/sseClient'

import type { AutoPlanProgressEvent, AutoPlanRequest, AutoPlanResponse } from '../types/scheduleBoardResponse'

const API_ROOT = import.meta.env.VITE_API_URL ?? ''
const AUTO_PLAN_STREAM_URL = `${API_ROOT}/api/v1/web/production-schedule/auto-plan/stream`

/**
 * The stream closed before a result or error frame. The run's outcome is
 * unknown here, but it keeps going on the server.
 */
export class AutoPlanConnectionLostError extends Error {
  constructor() {
    super('Auto-plan stream ended without a result or error frame')
    this.name = 'AutoPlanConnectionLostError'
  }
}

// Runs one auto-plan over the SSE endpoint and resolves with the same shape
// as POST /auto-plan. Unknown event names are ignored.
export async function streamAutoPlanSchedule(
  payload: AutoPlanRequest,
  onProgress: (ev: AutoPlanProgressEvent) => void,
  signal: AbortSignal,
): Promise<AutoPlanResponse> {
  let result: AutoPlanResponse | null = null
  let errorDetail: string | null = null

  await streamSse(
    {
      url: AUTO_PLAN_STREAM_URL,
      method: 'POST',
      body: JSON.stringify(payload),
      // This stream bypasses axios, so it adds the CSRF header itself.
      headers: () => ({
        'Content-Type': 'application/json',
        'X-Requested-With': 'glados',
      }),
      onOpen: () => {},
      onFrame: (frame) => {
        if (frame.event === 'progress') {
          try {
            onProgress(JSON.parse(frame.data) as AutoPlanProgressEvent)
          } catch {
            // Malformed frame: ignore it, same stance as liveStore's 'signal' frame.
          }
        } else if (frame.event === 'result') {
          result = JSON.parse(frame.data) as AutoPlanResponse
        } else if (frame.event === 'error') {
          errorDetail = (JSON.parse(frame.data) as { detail: string }).detail
        }
        // Any other event name (pings, future event types) is ignored.
      },
    },
    signal,
  )

  if (errorDetail !== null) throw new Error(errorDetail)
  if (result !== null) return result
  throw new AutoPlanConnectionLostError()
}
