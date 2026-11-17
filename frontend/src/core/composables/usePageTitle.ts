import { inject, provide, ref, watch } from 'vue'
import type { InjectionKey } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { usePublicBrandingStore } from '@/core/stores/publicBrandingStore'

export interface PageTitleApi {
  /**
   * Replaces the route's generic title with the loaded entity's own name
   * or number (a lot number, an order number, a machine name, ...). Cleared
   * again on the next navigation.
   */
  setPageTitle: (text: string) => void
}

const PAGE_TITLE_KEY: InjectionKey<PageTitleApi> = Symbol('pageTitle')

/**
 * Drives `document.title` from the current route's `meta.titleKey`, combined
 * with the app name from publicBrandingStore, and keeps it current as the
 * route or the active locale changes. Falls back to the app name alone when
 * the matched route carries no `titleKey`.
 *
 * Installed once, in AppLayout, so it applies to every authenticated page;
 * that call does the actual route/locale watching and `provide`s the result.
 * A detail view further down the tree calls this same function to read the
 * provided `setPageTitle` back out, rather than starting a second,
 * independent instance that would fight the installed one over
 * `document.title` on the next locale or branding change.
 */
export function usePageTitle(): PageTitleApi {
  const existing = inject(PAGE_TITLE_KEY, null)
  if (existing) return existing

  const route = useRoute()
  const { t, locale } = useI18n()
  const brandingStore = usePublicBrandingStore()

  const override = ref<string | null>(null)

  function apply(): void {
    const titleKey = route.meta.titleKey
    const base = override.value ?? (typeof titleKey === 'string' ? t(titleKey) : null)
    document.title = base ? `${base} · ${brandingStore.appName}` : brandingStore.appName
  }

  // Every navigation starts from the route's own title again, because an
  // override left over from the previous page would otherwise keep showing
  // (e.g. a lot number) after navigating away from it.
  watch(
    () => route.fullPath,
    () => {
      override.value = null
      apply()
    },
    { immediate: true },
  )

  watch([locale, () => brandingStore.appName], apply)

  function setPageTitle(text: string): void {
    override.value = text
    apply()
  }

  const api: PageTitleApi = { setPageTitle }
  provide(PAGE_TITLE_KEY, api)
  return api
}
