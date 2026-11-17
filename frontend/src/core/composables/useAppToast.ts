import { useToast } from 'openvue/usetoast'

/** Default lifetime for success/info toasts, in milliseconds. */
export const TOAST_LIFE_SHORT = 3000

/** Default lifetime for warn/error toasts, in milliseconds. */
export const TOAST_LIFE_LONG = 5000

export interface AppToastOptions {
  /** Overrides the severity's default lifetime for this one toast. */
  life?: number
  /** Keeps the toast on screen until the user closes it, ignoring `life`. */
  sticky?: boolean
}

type ToastSeverity = 'success' | 'info' | 'warn' | 'error'

/**
 * Thin wrapper around OpenVue's `useToast` that fixes the lifetime per
 * severity instead of leaving every call site to pick its own `life` value,
 * so toasts behave consistently across the app. `life` and `sticky` are the
 * escape hatch for the rare toast that genuinely needs a different duration.
 */
export function useAppToast() {
  const toast = useToast()

  function add(
    severity: ToastSeverity,
    defaultLife: number,
    summary: string,
    detail?: string,
    options?: AppToastOptions,
  ): void {
    toast.add({
      severity,
      summary,
      detail,
      life: options?.sticky ? undefined : (options?.life ?? defaultLife),
    })
  }

  return {
    success: (summary: string, detail?: string, options?: AppToastOptions) =>
      add('success', TOAST_LIFE_SHORT, summary, detail, options),
    info: (summary: string, detail?: string, options?: AppToastOptions) =>
      add('info', TOAST_LIFE_SHORT, summary, detail, options),
    warn: (summary: string, detail?: string, options?: AppToastOptions) =>
      add('warn', TOAST_LIFE_LONG, summary, detail, options),
    error: (summary: string, detail?: string, options?: AppToastOptions) =>
      add('error', TOAST_LIFE_LONG, summary, detail, options),
  }
}
