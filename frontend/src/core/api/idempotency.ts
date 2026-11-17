/**
 * Sends a request whose repetition would book something twice, such as a
 * delivery or a completion, with an Idempotency-Key (backend
 * `services/idempotency.py`). Each call is one user action and takes a new
 * key. When its answer is lost on the way (no response, or a gateway or
 * retryable 503 answer), the request is sent once more with the same key,
 * so the server answers from the first booking instead of booking again.
 */
import axios from 'axios'

import type { WebRequestConfig } from './webRequest'

export const IDEMPOTENCY_HEADER = 'Idempotency-Key'

const RETRY_DELAY_MS = 400
const LOST_ANSWER_STATUSES = new Set([502, 503, 504])

/** A random UUID (version 4). Built from getRandomValues, which unlike
 * randomUUID also exists outside secure contexts, such as a plain-http
 * terminal on the shop floor network. */
export function newIdempotencyKey(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6]! & 0x0f) | 0x40
  bytes[8] = (bytes[8]! & 0x3f) | 0x80
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

function answerLost(error: unknown): boolean {
  if (!axios.isAxiosError(error) || axios.isCancel(error)) return false
  if (!error.response) return true
  if (error.response.data?.code === 'MaintenanceModeError') return false
  return LOST_ANSWER_STATUSES.has(error.response.status)
}

export async function sendIdempotent<T>(send: (config: WebRequestConfig) => Promise<T>): Promise<T> {
  const config: WebRequestConfig = { headers: { [IDEMPOTENCY_HEADER]: newIdempotencyKey() } }
  try {
    return await send(config)
  } catch (error) {
    if (!answerLost(error)) throw error
    await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS))
    return await send(config)
  }
}
