import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { App } from 'vue'

import {
  handleUnhandledRejection,
  handleVueError,
  installGlobalErrorHandlers,
} from '../installGlobalErrorHandlers'

type ToastAddMock = ReturnType<typeof vi.fn<(message: unknown) => void>>

function fakeApp(toastAdd?: ToastAddMock): App {
  return {
    config: {
      globalProperties: {
        $toast: toastAdd ? { add: toastAdd } : undefined,
      },
    },
  } as unknown as App
}

function rejectionEvent(reason: unknown): PromiseRejectionEvent {
  return { reason } as PromiseRejectionEvent
}

// Matches how src/core/utils/__tests__/errors.spec.ts mocks axios errors:
// axios.isAxiosError only duck-checks `isAxiosError`, so a plain object is
// enough, no need to construct a real AxiosError.
function axiosError(status: number) {
  return { isAxiosError: true, response: { status } }
}

// axios.isCancel only duck-checks `__CANCEL__`.
function axiosCancellation() {
  return { __CANCEL__: true }
}

describe('handleVueError', () => {
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    consoleErrorSpy.mockRestore()
  })

  it('logs the error with the Vue info string and shows a toast', () => {
    const toastAdd = vi.fn<(message: unknown) => void>()
    const app = fakeApp(toastAdd)
    const err = new Error('boom')

    handleVueError(app, err, 'render function')

    expect(consoleErrorSpy).toHaveBeenCalledWith(
      'Unhandled Vue error:',
      err,
      'Info:',
      'render function',
    )
    expect(toastAdd).toHaveBeenCalledWith(expect.objectContaining({ severity: 'error', life: 5000 }))
  })

  it('does not throw when no ToastService is installed on the app', () => {
    const app = fakeApp()

    expect(() => handleVueError(app, new Error('boom'), 'setup function')).not.toThrow()
  })
})

describe('handleUnhandledRejection', () => {
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    consoleErrorSpy.mockRestore()
  })

  it('logs and shows a toast for a plain rejection', () => {
    const toastAdd = vi.fn<(message: unknown) => void>()
    const app = fakeApp(toastAdd)

    handleUnhandledRejection(app, rejectionEvent(new Error('boom')))

    expect(consoleErrorSpy).toHaveBeenCalled()
    expect(toastAdd).toHaveBeenCalledWith(expect.objectContaining({ severity: 'error', life: 5000 }))
  })

  it('ignores an axios cancellation', () => {
    const toastAdd = vi.fn<(message: unknown) => void>()
    const app = fakeApp(toastAdd)

    handleUnhandledRejection(app, rejectionEvent(axiosCancellation()))

    expect(toastAdd).not.toHaveBeenCalled()
    expect(consoleErrorSpy).not.toHaveBeenCalled()
  })

  it('ignores an axios error with a 401 response, already handled by the response interceptor', () => {
    const toastAdd = vi.fn<(message: unknown) => void>()
    const app = fakeApp(toastAdd)

    handleUnhandledRejection(app, rejectionEvent(axiosError(401)))

    expect(toastAdd).not.toHaveBeenCalled()
    expect(consoleErrorSpy).not.toHaveBeenCalled()
  })

  it('ignores an axios error with a 503 response, already handled by the response interceptor', () => {
    const toastAdd = vi.fn<(message: unknown) => void>()
    const app = fakeApp(toastAdd)

    handleUnhandledRejection(app, rejectionEvent(axiosError(503)))

    expect(toastAdd).not.toHaveBeenCalled()
    expect(consoleErrorSpy).not.toHaveBeenCalled()
  })

  it('still shows a toast for an axios error with an unrelated status', () => {
    const toastAdd = vi.fn<(message: unknown) => void>()
    const app = fakeApp(toastAdd)

    handleUnhandledRejection(app, rejectionEvent(axiosError(500)))

    expect(toastAdd).toHaveBeenCalled()
  })
})

describe('installGlobalErrorHandlers', () => {
  it('sets app.config.errorHandler and registers a window unhandledrejection listener', () => {
    const addEventListenerSpy = vi.spyOn(window, 'addEventListener')
    const app = fakeApp(vi.fn<(message: unknown) => void>())

    installGlobalErrorHandlers(app)

    expect(app.config.errorHandler).toBeTypeOf('function')
    expect(addEventListenerSpy).toHaveBeenCalledWith('unhandledrejection', expect.any(Function))

    addEventListenerSpy.mockRestore()
  })
})
