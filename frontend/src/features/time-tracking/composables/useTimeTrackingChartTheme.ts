import { useChartTheme } from '@/shared/composables/useChartTheme'

/**
 * Concrete colours for the time tracking charts, resolved from the theme's
 * CSS variables because chart.js cannot read them, and recomputed when dark
 * mode toggles. The series hues are fixed palette steps rather than the
 * user's primary colour, so a theme never makes "worked" and "short of
 * target" the same colour; blue, teal and orange at step 600 were checked
 * for colour-blind separation on the light and the dark surface.
 */
export function useTimeTrackingChartTheme() {
  return useChartTheme({
    worked: ['--p-blue-600', '#2563eb'],
    over: ['--p-teal-600', '#0d9488'],
    short: ['--p-orange-600', '#ea580c'],
    target: ['--p-surface-400', '#a3a3a3'],
    surface: ['--p-content-background', '#ffffff'],
  })
}
