import { computed } from 'vue'
import type { ComputedRef } from 'vue'
import { storeToRefs } from 'pinia'

import { useLayoutStore } from '@/core/stores/layoutStore'

/**
 * A theme colour as a CSS variable name and the colour used when the
 * document does not define it.
 */
export type ChartColorToken = readonly [cssVariable: string, fallback: string]

export interface ChartThemeBase {
  text: string
  grid: string
}

function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

/**
 * Concrete colours for a chart.js chart. chart.js cannot read CSS variables,
 * so each token is resolved against the document, and the colours are
 * recomputed when dark mode toggles. Every theme carries the muted text
 * colour for ticks and legends and the border colour for grid lines, next
 * to the chart's own `series` colours.
 */
export function useChartTheme<TKey extends string>(
  series: Record<TKey, ChartColorToken>,
): ComputedRef<ChartThemeBase & Record<TKey, string>> {
  const { isDarkMode } = storeToRefs(useLayoutStore())

  return computed(() => {
    void isDarkMode.value
    const colours = {} as Record<TKey, string>
    for (const key of Object.keys(series) as TKey[]) {
      const [cssVariable, fallback] = series[key]
      colours[key] = cssVar(cssVariable) || fallback
    }
    return {
      text: cssVar('--p-text-muted-color') || '#6b7280',
      grid: cssVar('--p-content-border-color') || '#e5e7eb',
      ...colours,
    }
  })
}
