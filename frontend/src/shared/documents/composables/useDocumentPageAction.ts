import { watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import { useAppToast } from '@/core/composables/useAppToast'

/** The steps a list's row menu leaves to the document page, which carries them out with its own checks. */
export const DOCUMENT_PAGE_ACTIONS = ['edit', 'history', 'release', 'invalidate', 'revise', 'copy'] as const
export type DocumentPageAction = (typeof DOCUMENT_PAGE_ACTIONS)[number]

function isAction(value: unknown): value is DocumentPageAction {
  return typeof value === 'string' && (DOCUMENT_PAGE_ACTIONS as readonly string[]).includes(value)
}

/**
 * A list's row menu opens a document with `?action=…` for a step only the
 * document page can take, such as editing or releasing. Once the page is
 * ready the action is taken off the address and handed to `run`, which
 * starts it like the page's own button would, with the same checks and
 * confirmations. `run` returns false for an action the document does not
 * allow right now, and the user is told.
 */
export function useDocumentPageAction(options: { ready: () => boolean; run: (action: DocumentPageAction) => boolean }) {
  const route = useRoute()
  const router = useRouter()
  const { t } = useI18n()
  const toast = useAppToast()

  watch(
    [() => route.query.action, options.ready],
    ([action, ready]) => {
      if (!ready || action === undefined) return
      const { action: _taken, ...query } = route.query
      void router.replace({ query })
      if (!isAction(action) || !options.run(action)) toast.warn('', t('documents.menu.unavailable'))
    },
    { immediate: true },
  )
}
