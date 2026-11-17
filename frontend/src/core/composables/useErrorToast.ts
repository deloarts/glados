import { useAppToast } from '@/core/composables/useAppToast'
import { i18n } from '@/core/i18n'
import { extractApiError } from '@/core/utils/errors'

export interface WithErrorToastOptions {
  /** Toast summary, usually the entity's own label (name, number, ...). */
  summary: string
  /**
   * Shown when the API error carries no usable message. Omit to leave the
   * toast's detail empty in that case, same as a bare `extractApiError(e) ??
   * undefined`.
   */
  fallbackMessage?: string
  /** Overrides the error toast's default lifetime. */
  life?: number
}

/**
 * Runs an async action, surfacing any failure as an error toast instead of
 * throwing.
 *
 * It replaces the `try { await X() } catch (e) { toast.add(...) }` block
 * that tables and detail views would otherwise repeat; callers keep whatever
 * side effect belongs on success inside `fn`. The toast goes through
 * `useAppToast().error`, so it lives as long as every other error toast.
 */
export function useErrorToast() {
  const toast = useAppToast()

  async function withErrorToast<T>(
    fn: () => Promise<T>,
    options: WithErrorToastOptions,
  ): Promise<T | undefined> {
    try {
      return await fn()
    } catch (e) {
      toast.error(options.summary, extractApiError(e) ?? options.fallbackMessage, { life: options.life })
      return undefined
    }
  }

  /**
   * Returns a `.catch` handler that shows a rejection as an error toast, for
   * a promise that is started and not awaited, such as a background load.
   * The summary defaults to the generic error message.
   */
  function toastOnError(summary?: string): (e: unknown) => void {
    return (e) => {
      toast.error(summary ?? i18n.global.t('common.unexpectedError'), extractApiError(e) ?? undefined)
    }
  }

  return { withErrorToast, toastOnError }
}
