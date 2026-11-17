/**
 * Makes every confirmation dialog act on one answer only. OpenVue's
 * ConfirmDialog calls `accept` or `reject` on each click and keeps its buttons
 * clickable while the dialog fades out, so a double click on "Cancel order"
 * ran the cancel twice and the second request failed with a conflict. The
 * plugin wraps the service's `require` once at startup, which covers every
 * `useConfirm().require` and `useConfirmAsync().ask` in the app.
 */
import type { App } from 'vue'
import type { ConfirmationOptions } from 'openvue/confirmationoptions'

/** The options with `accept` and `reject` sharing one guard: whichever runs
 * first wins and every later call of either is ignored. */
export function settleOnce(options: ConfirmationOptions): ConfirmationOptions {
  let settled = false
  const once = (callback: (() => void) | undefined): (() => void) | undefined =>
    callback &&
    (() => {
      if (settled) return
      settled = true
      callback()
    })
  return { ...options, accept: once(options.accept), reject: once(options.reject) }
}

/** Installed after OpenVue's ConfirmationService, whose object is the one both
 * `$confirm` and `useConfirm()` hand out. */
export const settleConfirmationsOnce = {
  install(app: App): void {
    const service = app.config.globalProperties.$confirm
    const require = service.require.bind(service)
    service.require = (options: ConfirmationOptions) => require(settleOnce(options))
  },
}
