import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'

const toastAddMock = vi.fn<(message: unknown) => void>()
vi.mock('openvue/usetoast', () => ({
  useToast: () => ({ add: toastAddMock }),
}))

import { useClipboard } from '../useClipboard'

function mountComposable() {
  let result!: ReturnType<typeof useClipboard>
  mountWithApp(
    defineComponent({
      setup() {
        result = useClipboard()
        return () => h('div')
      },
    }),
  )
  return result
}

describe('useClipboard copyIfPresent', () => {
  const writeTextMock = vi.fn<(value: string) => Promise<void>>()

  beforeEach(() => {
    toastAddMock.mockReset()
    writeTextMock.mockReset()
    writeTextMock.mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText: writeTextMock } })
  })

  it('copies a number as text', async () => {
    await mountComposable().copyIfPresent(42)
    expect(writeTextMock).toHaveBeenCalledWith('42')
  })

  it.each([null, undefined, ''])('does nothing for the empty value %s', async (value) => {
    await mountComposable().copyIfPresent(value)
    expect(writeTextMock).not.toHaveBeenCalled()
    expect(toastAddMock).not.toHaveBeenCalled()
  })
})
