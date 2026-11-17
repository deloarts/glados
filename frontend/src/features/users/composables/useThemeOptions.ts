import { computed } from 'vue'
import { storeToRefs } from 'pinia'

import { useHostStore } from '@/core/host/stores/hostStore'
import { useLayoutStore } from '@/core/stores/layoutStore'

/**
 * The theme presets, primary colours and surfaces a user may pick: the
 * layout's palettes narrowed to those the host allows.
 */
export function useThemeOptions() {
  const hostStore = useHostStore()
  const { primaryColors, surfaces } = storeToRefs(useLayoutStore())

  const presetOptions = computed(() => hostStore.themePresets)
  const filteredPrimaryColors = computed(() =>
    primaryColors.value.filter((c) => hostStore.themePrimaries.includes(c.name)),
  )
  const filteredSurfaces = computed(() =>
    surfaces.value.filter((s) => hostStore.themeSurfaces.includes(s.name)),
  )

  return { presetOptions, filteredPrimaryColors, filteredSurfaces }
}
