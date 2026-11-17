import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import type { RouteLocationRaw } from 'vue-router'

import { useClipboard } from '@/core/composables/useClipboard'

/** Opens a document of a list row in a new browser tab, or copies its address. */
export function useDocumentRowLinks() {
  const router = useRouter()
  const { t } = useI18n()
  const { copyToClipboard } = useClipboard()

  function href(to: RouteLocationRaw): string {
    return new URL(router.resolve(to).href, window.location.origin).href
  }

  return {
    openInNewTab(to: RouteLocationRaw): void {
      window.open(href(to), '_blank', 'noopener')
    },
    async copyLink(to: RouteLocationRaw): Promise<void> {
      await copyToClipboard(href(to), t('documents.menu.linkCopied'))
    },
  }
}
