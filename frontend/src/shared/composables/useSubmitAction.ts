import { ref } from 'vue'

import { extractApiError } from '@/core/utils/errors'

/**
 * The busy flag and inline error of a write action in a dialog or form.
 * `run` clears the error, sets `submitting` while `action` runs, and on a
 * failure shows the API's error detail, or `fallbackMessage` when the error
 * carries none. It resolves to whether the action succeeded and never
 * rejects, so the caller needs no `try` of its own.
 *
 * Both refs stay writable, so a caller can still show a validation message
 * or clear the error when its dialog opens. `messageFor` lets a caller show
 * its own message for an error it knows, such as a translated error code.
 */
export function useSubmitAction(messageFor?: (e: unknown) => string | null) {
  const submitting = ref(false)
  const errorMessage = ref<string | null>(null)

  async function run(action: () => Promise<unknown>, fallbackMessage: string): Promise<boolean> {
    submitting.value = true
    errorMessage.value = null
    try {
      await action()
      return true
    } catch (e) {
      errorMessage.value = messageFor?.(e) ?? extractApiError(e) ?? fallbackMessage
      return false
    } finally {
      submitting.value = false
    }
  }

  return { submitting, errorMessage, run }
}
