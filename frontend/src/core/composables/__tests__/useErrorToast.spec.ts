import { describe, it, expect, vi, beforeEach } from 'vitest'
import { defineComponent, h } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'

// This consolidates repeated try/catch-toast blocks that were duplicated across the codebase.

const toastAddMock = vi.fn<(message: unknown) => void>()
vi.mock('openvue/usetoast', () => ({
  useToast: () => ({ add: toastAddMock }),
}))

import { TOAST_LIFE_LONG } from '../useAppToast'
import { useErrorToast } from '../useErrorToast'

function mountComposable() {
  let result!: ReturnType<typeof useErrorToast>
  const wrapper = mountWithApp(
    defineComponent({
      setup() {
        result = useErrorToast()
        return () => h('div')
      },
    }),
  )
  return { result, wrapper }
}

describe('useErrorToast', () => {
  beforeEach(() => {
    toastAddMock.mockReset()
  })

  it('returns the action result and adds no toast on success', async () => {
    const { result } = mountComposable()

    const value = await result.withErrorToast(() => Promise.resolve(42), {
      summary: 'Widget',
      fallbackMessage: 'Something went wrong.',
    })

    expect(value).toBe(42)
    expect(toastAddMock).not.toHaveBeenCalled()
  })

  it('adds an error toast and returns undefined when the action rejects', async () => {
    const { result } = mountComposable()

    const value = await result.withErrorToast(() => Promise.reject(new Error('boom')), {
      summary: 'Widget',
      fallbackMessage: 'Something went wrong.',
    })

    expect(value).toBeUndefined()
    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'error', summary: 'Widget', life: TOAST_LIFE_LONG }),
    )
  })

  it('falls back to fallbackMessage when the error carries no usable API message', async () => {
    const { result } = mountComposable()

    await result.withErrorToast(() => Promise.reject(new Error('')), {
      summary: 'Widget',
      fallbackMessage: 'Something went wrong.',
    })

    expect(toastAddMock).toHaveBeenCalledWith(expect.objectContaining({ detail: 'Something went wrong.' }))
  })

  it('leaves detail undefined when no fallbackMessage is given and the error carries no message', async () => {
    const { result } = mountComposable()

    await result.withErrorToast(() => Promise.reject(new Error('boom')), { summary: 'Widget' })

    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'error', summary: 'Widget', detail: undefined }),
    )
  })

  it('respects a custom life', async () => {
    const { result } = mountComposable()

    await result.withErrorToast(() => Promise.reject(new Error('boom')), {
      summary: 'Widget',
      fallbackMessage: 'Something went wrong.',
      life: 9000,
    })

    expect(toastAddMock).toHaveBeenCalledWith(expect.objectContaining({ life: 9000 }))
  })
})
