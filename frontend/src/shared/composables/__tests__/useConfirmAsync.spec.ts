import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { ConfirmationOptions } from 'openvue/confirmationoptions'

const confirmRequireMock = vi.fn<(option: ConfirmationOptions) => void>()

vi.mock('openvue/useconfirm', () => ({
  useConfirm: () => ({ require: confirmRequireMock }),
}))

import { useConfirmAsync } from '../useConfirmAsync'

function lastOptions(): ConfirmationOptions {
  const options = confirmRequireMock.mock.calls.at(-1)?.[0]
  if (!options) throw new Error('confirm.require was not called')
  return options
}

describe('useConfirmAsync', () => {
  beforeEach(() => {
    confirmRequireMock.mockReset()
  })

  it('passes the dialog options through to confirm.require', () => {
    const { ask } = useConfirmAsync()

    void ask({
      group: 'g',
      header: 'Header',
      message: 'Message',
      rejectProps: { label: 'Cancel', severity: 'secondary' },
    })

    expect(lastOptions()).toMatchObject({
      group: 'g',
      header: 'Header',
      message: 'Message',
      rejectProps: { label: 'Cancel', severity: 'secondary' },
    })
  })

  it('resolves true on accept', async () => {
    const { ask } = useConfirmAsync()

    const answer = ask({ message: 'Sure?' })
    lastOptions().accept?.()

    await expect(answer).resolves.toBe(true)
  })

  it('resolves false on reject and when the dialog is hidden', async () => {
    const { ask } = useConfirmAsync()

    const rejected = ask({ message: 'Sure?' })
    lastOptions().reject?.()
    const hidden = ask({ message: 'Sure?' })
    lastOptions().onHide?.()

    await expect(rejected).resolves.toBe(false)
    await expect(hidden).resolves.toBe(false)
  })
})
