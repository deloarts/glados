import { ref, shallowRef, toValue, watch, type MaybeRefOrGetter } from 'vue'
import { useI18n } from 'vue-i18n'

import { loadHandbookDoc, type HandbookDoc } from '../utils/handbookContent'
import type { AppLocale } from '@/core/i18n'

/**
 * Loads the handbook doc for `slug` in the active locale, re-loading when
 * either changes. `doc` is a shallowRef because it holds a compiled component;
 * making that deeply reactive would be pure overhead.
 */
export function useHandbookDoc(slug: MaybeRefOrGetter<string | undefined>) {
  const { locale } = useI18n()

  const doc = shallowRef<HandbookDoc | null>(null)
  const loading = ref(false)
  const missing = ref(false)

  // Every load is stamped, and a resolved load that is no longer the newest is
  // dropped: switching slugs faster than the chunks arrive would otherwise let
  // an earlier request overwrite a later one.
  let latest = 0

  watch(
    [() => toValue(slug), locale],
    async ([currentSlug, currentLocale]) => {
      const token = ++latest

      if (!currentSlug) {
        doc.value = null
        loading.value = false
        missing.value = false
        return
      }

      loading.value = true
      const loaded = await loadHandbookDoc(currentSlug, currentLocale as AppLocale)
      if (token !== latest) return

      doc.value = loaded
      missing.value = loaded === null
      loading.value = false
    },
    { immediate: true },
  )

  return { doc, loading, missing }
}
