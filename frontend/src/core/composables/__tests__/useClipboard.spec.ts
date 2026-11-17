import { describe, it, expect, vi, beforeEach } from 'vitest'
import { defineComponent, h } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { TOAST_LIFE_SHORT, TOAST_LIFE_LONG } from '../useAppToast'

const toastAddMock = vi.fn<(message: unknown) => void>()
vi.mock('openvue/usetoast', () => ({
  useToast: () => ({ add: toastAddMock }),
}))

import { useClipboard } from '../useClipboard'

function mountComposable() {
  let result!: ReturnType<typeof useClipboard>
  const wrapper = mountWithApp(
    defineComponent({
      setup() {
        result = useClipboard()
        return () => h('div')
      },
    }),
  )
  return { result, wrapper }
}

describe('useClipboard', () => {
  const writeTextMock = vi.fn<(value: string) => Promise<void>>()

  beforeEach(() => {
    i18n.global.locale.value = 'enGB'
    toastAddMock.mockReset()
    writeTextMock.mockReset()
    Object.assign(navigator, { clipboard: { writeText: writeTextMock } })
  })

  it('writes the value to the clipboard and shows a confirmation toast', async () => {
    writeTextMock.mockResolvedValue(undefined)
    const { result } = mountComposable()

    const success = await result.copyToClipboard('ABC-123')

    expect(success).toBe(true)
    expect(writeTextMock).toHaveBeenCalledWith('ABC-123')
    expect(toastAddMock).toHaveBeenCalledWith({
      severity: 'info',
      summary: '',
      detail: 'Copied to clipboard.',
      life: TOAST_LIFE_SHORT,
    })
  })

  it('shows the given success message instead of the default one', async () => {
    writeTextMock.mockResolvedValue(undefined)
    const { result } = mountComposable()

    await result.copyToClipboard('ABC-123', 'Secret copied.')

    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'info', detail: 'Secret copied.' }),
    )
  })

  it('catches a clipboard failure and shows an error toast instead of throwing', async () => {
    writeTextMock.mockRejectedValue(new Error('denied'))
    const { result } = mountComposable()

    const success = await result.copyToClipboard('ABC-123')

    expect(success).toBe(false)
    expect(toastAddMock).toHaveBeenCalledWith({
      severity: 'error',
      summary: '',
      detail: 'Could not copy to clipboard.',
      life: TOAST_LIFE_LONG,
    })
  })
})
