import { describe, it, expect, vi } from 'vitest'
import { createApp } from 'vue'
import ConfirmationService from 'openvue/confirmationservice'
import ConfirmationEventBus from 'openvue/confirmationeventbus'
import type { ConfirmationOptions } from 'openvue/confirmationoptions'

import { settleConfirmationsOnce, settleOnce } from '../settleConfirmationsOnce'

describe('settleOnce', () => {
  it('runs accept once however often it is called', () => {
    const accept = vi.fn<() => void>()
    const options = settleOnce({ accept })

    options.accept!()
    options.accept!()

    expect(accept).toHaveBeenCalledTimes(1)
  })

  it('ignores a reject after an accept, and the other way round', () => {
    const accept = vi.fn<() => void>()
    const reject = vi.fn<() => void>()

    const accepted = settleOnce({ accept, reject })
    accepted.accept!()
    accepted.reject!()
    expect(accept).toHaveBeenCalledTimes(1)
    expect(reject).not.toHaveBeenCalled()

    const rejected = settleOnce({ accept, reject })
    rejected.reject!()
    rejected.accept!()
    expect(reject).toHaveBeenCalledTimes(1)
    expect(accept).toHaveBeenCalledTimes(1)
  })

  it('leaves a missing callback missing and keeps the other options', () => {
    const options = settleOnce({ header: 'Cancel order', onHide: () => {} })

    expect(options.accept).toBeUndefined()
    expect(options.reject).toBeUndefined()
    expect(options.header).toBe('Cancel order')
    expect(options.onHide).toBeTypeOf('function')
  })
})

describe('settleConfirmationsOnce', () => {
  it('guards what the installed service hands to the dialog', () => {
    const app = createApp({})
    app.use(ConfirmationService)
    app.use(settleConfirmationsOnce)
    let received: ConfirmationOptions | undefined
    const listener = (options: ConfirmationOptions) => {
      received = options
    }
    ConfirmationEventBus.on('confirm', listener)
    const accept = vi.fn<() => void>()

    app.config.globalProperties.$confirm.require({ accept })
    received!.accept!()
    received!.accept!()

    ConfirmationEventBus.off('confirm', listener)
    expect(accept).toHaveBeenCalledTimes(1)
  })
})
