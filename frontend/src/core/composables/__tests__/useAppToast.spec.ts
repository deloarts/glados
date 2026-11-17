import { describe, it, expect, vi, beforeEach } from 'vitest'
import { defineComponent, h } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'

const toastAddMock = vi.fn<(message: unknown) => void>()
vi.mock('openvue/usetoast', () => ({
  useToast: () => ({ add: toastAddMock }),
}))

import { useAppToast, TOAST_LIFE_SHORT, TOAST_LIFE_LONG } from '../useAppToast'

function mountComposable() {
  let result!: ReturnType<typeof useAppToast>
  const wrapper = mountWithApp(
    defineComponent({
      setup() {
        result = useAppToast()
        return () => h('div')
      },
    }),
  )
  return { result, wrapper }
}

describe('useAppToast', () => {
  beforeEach(() => {
    toastAddMock.mockReset()
  })

  it('adds a success toast at the short lifetime', () => {
    const { result } = mountComposable()

    result.success('Saved', 'The record was saved.')

    expect(toastAddMock).toHaveBeenCalledWith({
      severity: 'success',
      summary: 'Saved',
      detail: 'The record was saved.',
      life: TOAST_LIFE_SHORT,
    })
  })

  it('adds an info toast at the short lifetime', () => {
    const { result } = mountComposable()

    result.info('Heads up')

    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'info', summary: 'Heads up', life: TOAST_LIFE_SHORT }),
    )
  })

  it('adds a warn toast at the long lifetime', () => {
    const { result } = mountComposable()

    result.warn('Careful')

    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'warn', summary: 'Careful', life: TOAST_LIFE_LONG }),
    )
  })

  it('adds an error toast at the long lifetime', () => {
    const { result } = mountComposable()

    result.error('Failed', 'Something went wrong.')

    expect(toastAddMock).toHaveBeenCalledWith({
      severity: 'error',
      summary: 'Failed',
      detail: 'Something went wrong.',
      life: TOAST_LIFE_LONG,
    })
  })

  it('lets a call override the lifetime', () => {
    const { result } = mountComposable()

    result.error('Failed', undefined, { life: 9000 })

    expect(toastAddMock).toHaveBeenCalledWith(expect.objectContaining({ life: 9000 }))
  })

  it('drops the lifetime entirely for a sticky toast', () => {
    const { result } = mountComposable()

    result.warn('Stays until closed', undefined, { sticky: true })

    expect(toastAddMock).toHaveBeenCalledWith(expect.objectContaining({ life: undefined }))
  })

  it('lets sticky win over an explicit life if both are somehow given', () => {
    const { result } = mountComposable()

    result.error('Stays', undefined, { life: 1000, sticky: true })

    expect(toastAddMock).toHaveBeenCalledWith(expect.objectContaining({ life: undefined }))
  })
})
