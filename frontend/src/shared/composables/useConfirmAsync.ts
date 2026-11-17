import { useConfirm } from 'openvue/useconfirm'
import type { ConfirmationOptions } from 'openvue/confirmationoptions'

/**
 * The dialog options of a confirmation; the outcome comes back as the
 * promise instead of through callbacks.
 */
export type ConfirmAsyncOptions = Omit<ConfirmationOptions, 'accept' | 'reject' | 'onHide'>

/**
 * OpenVue's confirmation dialog as a promise. `ask` opens the dialog through
 * the same `useConfirm().require` with the given options and resolves to
 * true when the user accepts, and to false when they reject or the dialog
 * closes any other way.
 */
export function useConfirmAsync() {
  const confirm = useConfirm()

  function ask(options: ConfirmAsyncOptions): Promise<boolean> {
    return new Promise<boolean>((resolve) => {
      confirm.require({
        ...options,
        accept: () => resolve(true),
        reject: () => resolve(false),
        onHide: () => resolve(false),
      })
    })
  }

  return { ask }
}
