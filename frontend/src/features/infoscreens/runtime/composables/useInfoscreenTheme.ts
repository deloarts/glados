/**
 * Shows a screen in its own colour mode, preset and primary colour.
 *
 * Everything goes through the layout store's painting calls (`applyPreset`
 * with a primary override, `setDarkMode`), which change what is on screen
 * without recording a user theme: nothing is written to the server and the
 * viewer's own primary stays recorded, so leaving the preview puts the
 * viewer's theme back. A null preset or colour means the tenant default,
 * the theme a page shows before anybody signs in.
 */
import { onScopeDispose } from 'vue'

import { APERTURE_PRESET, APERTURE_PRIMARY, useEasterEggs } from '@/core/composables/useEasterEggs'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useLayoutStore } from '@/core/stores/layoutStore'
import {
  DEFAULT_THEME_PRESET,
  paintScreenTheme,
  updateDeviceScreenMemory,
} from '@/core/terminal/deviceScreenMemory'

import type { InfoscreenFeedScreen } from '../types/infoscreenFeed'

export type InfoscreenTheme = Pick<InfoscreenFeedScreen, 'color_mode' | 'theme_preset' | 'primary_color'>

/**
 * `restoreOnDispose` gives the viewer's theme back when the caller's scope
 * ends, for the preview. `remember` stores every applied theme on the
 * device, so its next boot starts in it before the first feed arrives.
 */
export function useInfoscreenTheme(options: { restoreOnDispose: boolean; remember?: boolean }) {
  const layoutStore = useLayoutStore()
  const darkModeBefore = layoutStore.isDarkMode
  let applied = false

  function apply(theme: InfoscreenTheme): void {
    applied = true
    paintScreenTheme(theme, layoutStore)
    if (options.remember) {
      updateDeviceScreenMemory({
        theme: {
          color_mode: theme.color_mode,
          theme_preset: theme.theme_preset,
          primary_color: theme.primary_color,
        },
      })
    }
  }

  /** Puts the viewer's own theme back, as App.vue applies it. */
  function restore(): void {
    if (!applied) return
    applied = false
    const aperture = useEasterEggs().apertureMode.value
    const savedPreset = useCurrentUserStore().user?.theme_preset
    layoutStore.applyPreset(
      aperture ? APERTURE_PRESET : (savedPreset ?? DEFAULT_THEME_PRESET),
      aperture ? APERTURE_PRIMARY : undefined,
    )
    layoutStore.setDarkMode(darkModeBefore)
  }

  if (options.restoreOnDispose) onScopeDispose(restore)

  return { apply, restore }
}
