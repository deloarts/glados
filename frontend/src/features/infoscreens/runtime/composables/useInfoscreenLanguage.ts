/**
 * Shows a screen in its own language: the built-in copy, the date and
 * weekday names and the number formats. Text people typed in stays as
 * entered. The feed carries the language already resolved, the screen's
 * own or else the tenant default.
 *
 * Only the UI locale changes. Nothing is written to the server, so leaving
 * the preview puts the viewer's own language back.
 */
import { onScopeDispose, watch } from 'vue'

import { i18n } from '@/core/i18n'
import type { AppLocale } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import {
  forgetShownScreenLanguage,
  paintScreenLanguage,
  updateDeviceScreenMemory,
} from '@/core/terminal/deviceScreenMemory'

/**
 * `restoreOnDispose` gives the viewer's language back when the caller's
 * scope ends, for the preview. `remember` stores every applied language on
 * the device next to the theme, so its next boot starts in it.
 */
export function useInfoscreenLanguage(options: { restoreOnDispose: boolean; remember?: boolean }) {
  const currentUserStore = useCurrentUserStore()
  const localeBefore = i18n.global.locale.value as AppLocale
  let applied: AppLocale | null = null

  function apply(language: AppLocale): void {
    applied = language
    paintScreenLanguage(language)
    if (options.remember) updateDeviceScreenMemory({ language })
  }

  /** Puts the viewer's own language back, as their session sets it. */
  function restore(): void {
    if (!applied) return
    applied = null
    forgetShownScreenLanguage()
    i18n.global.locale.value = (currentUserStore.user?.language as AppLocale | undefined) ?? localeBefore
  }

  if (options.restoreOnDispose) {
    // A preview opened straight from its address loads the viewer's session
    // alongside the feed, and the session sets the viewer's language when it
    // lands, so the screen's language is put back over it.
    watch(
      () => currentUserStore.user?.language,
      () => {
        if (applied) paintScreenLanguage(applied)
      },
    )
    onScopeDispose(restore)
  }

  return { apply, restore }
}
