import { describe, it, expect } from 'vitest'
import { AxiosError, AxiosHeaders } from 'axios'
import type { AxiosResponse } from 'axios'

import { useSubmitAction } from '../useSubmitAction'

function apiError(detail: string): AxiosError {
  const response = {
    data: { detail },
    status: 400,
    statusText: 'Bad Request',
    headers: {},
    config: { headers: new AxiosHeaders() },
  } as AxiosResponse
  return new AxiosError('Request failed', 'ERR_BAD_REQUEST', undefined, undefined, response)
}

describe('useSubmitAction', () => {
  it('sets submitting while the action runs and resolves true on success', async () => {
    const { submitting, errorMessage, run } = useSubmitAction()
    errorMessage.value = 'stale'
    let seenSubmitting = false

    const ok = await run(async () => {
      seenSubmitting = submitting.value
    }, 'fallback')

    expect(ok).toBe(true)
    expect(seenSubmitting).toBe(true)
    expect(submitting.value).toBe(false)
    expect(errorMessage.value).toBeNull()
  })

  it('shows the API error detail and resolves false on failure', async () => {
    const { submitting, errorMessage, run } = useSubmitAction()

    const ok = await run(() => Promise.reject(apiError('Name taken')), 'fallback')

    expect(ok).toBe(false)
    expect(errorMessage.value).toBe('Name taken')
    expect(submitting.value).toBe(false)
  })

  it('falls back to the given message for an error without a detail', async () => {
    const { errorMessage, run } = useSubmitAction()

    await run(() => Promise.reject(new Error('boom')), 'Something went wrong')

    expect(errorMessage.value).toBe('Something went wrong')
  })

  it("shows the caller's own message for an error it knows", async () => {
    const { errorMessage, run } = useSubmitAction(() => 'Known message')

    await run(() => Promise.reject(apiError('English detail')), 'fallback')

    expect(errorMessage.value).toBe('Known message')
  })
})
