import ConfirmationEventBus from 'openvue/confirmationeventbus'
import type { ConfirmationOptions } from 'openvue/confirmationoptions'

/**
 * Answers every confirmation the code under test asks for, the way a user
 * clicking the dialog's button would, so a spec can drive a confirmed action
 * without mounting a ConfirmDialog. It returns the asked options, and the
 * returned `stop` removes the listener again.
 */
export function answerConfirmations(answer: 'accept' | 'reject' = 'accept') {
  const asked: ConfirmationOptions[] = []
  const listener = (options: ConfirmationOptions) => {
    asked.push(options)
    queueMicrotask(() => (answer === 'accept' ? options.accept?.() : options.reject?.()))
  }
  ConfirmationEventBus.on('confirm', listener)
  return { asked, stop: () => ConfirmationEventBus.off('confirm', listener) }
}
