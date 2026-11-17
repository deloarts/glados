import type { App } from 'vue'
import axios from 'axios'

import { TOAST_LIFE_LONG } from '@/core/composables/useAppToast'
import { i18n } from '@/core/i18n'

/**
 * True for a rejection the axios response interceptor (src/core/api/index.ts)
 * already reacts to on its own: a cancelled request, or a 401/503 that
 * triggers session expiry or the maintenance lockout respectively. Both still
 * reject the promise afterwards, so without this check every one of those
 * would also surface a second, redundant error toast here.
 */
function isHandledByResponseInterceptor(reason: unknown): boolean {
  if (axios.isCancel(reason)) return true
  if (axios.isAxiosError(reason)) {
    const status = reason.response?.status
    return status === 401 || status === 503
  }
  return false
}

/** Shows the generic error toast, guarded for an app with no ToastService installed. */
function showGenericErrorToast(app: App): void {
  const toast = app.config.globalProperties.$toast
  if (!toast) return

  toast.add({
    severity: 'error',
    summary: i18n.global.t('common.unexpectedError'),
    life: TOAST_LIFE_LONG,
  })
}

/**
 * Vue's global error handler. Vue swallows the error after this runs rather
 * than rethrowing it, so without this a render, lifecycle-hook, or template
 * event-handler exception would otherwise vanish with no trace and no
 * feedback to the user.
 */
export function handleVueError(app: App, err: unknown, info: string): void {
  console.error('Unhandled Vue error:', err, 'Info:', info)
  showGenericErrorToast(app)
}

/**
 * `window` `unhandledrejection` handler, for any promise nobody awaited or
 * caught. Skips a rejection the axios response interceptor already handles
 * (see isHandledByResponseInterceptor) so those do not double up on toasts.
 */
export function handleUnhandledRejection(app: App, event: PromiseRejectionEvent): void {
  if (isHandledByResponseInterceptor(event.reason)) return

  console.error('Unhandled promise rejection:', event.reason)
  showGenericErrorToast(app)
}

/**
 * Wires both global failure surfaces to the same generic error toast: Vue's
 * own errorHandler for anything thrown during render, a lifecycle hook, or a
 * template event handler, and window's unhandledrejection for a promise
 * nobody awaited or caught. Call once at bootstrap, after ToastService and
 * i18n are installed on the app.
 */
export function installGlobalErrorHandlers(app: App): void {
  app.config.errorHandler = (err, _instance, info) => handleVueError(app, err, info)
  window.addEventListener('unhandledrejection', (event) => handleUnhandledRejection(app, event))
}
