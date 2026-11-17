import { apiErrorStatus } from '@/core/utils/errors'

/**
 * Runs a lot action and, when the server answers 409 because the lot changed
 * since this view loaded it (another tab switched its source, say), runs
 * `refresh` before passing the error on to its toast or message. The view
 * then shows the lot as it stands now instead of the copy the action was
 * refused for. A failing refresh is swallowed, since the action's own error
 * is the one the user needs to see.
 */
export async function refreshOnConflict<T>(
  action: () => Promise<T>,
  refresh: () => unknown,
): Promise<T> {
  try {
    return await action()
  } catch (e) {
    if (apiErrorStatus(e) === 409) {
      await Promise.resolve()
        .then(refresh)
        .catch(() => undefined)
    }
    throw e
  }
}
