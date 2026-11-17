import type { IScaleConfig } from '@svar-ui/vue-gantt'

export type GanttResolution = 'day' | 'week' | 'month'

export const GANTT_RESOLUTIONS: GanttResolution[] = ['day', 'week', 'month']

export function scalesForResolution(resolution: GanttResolution): IScaleConfig[] {
  switch (resolution) {
    case 'day':
      return [
        { unit: 'month', step: 1, format: '%F %Y' },
        { unit: 'day', step: 1, format: '%j' },
      ]
    case 'month':
      return [
        { unit: 'year', step: 1, format: '%Y' },
        { unit: 'month', step: 1, format: '%M' },
      ]
    case 'week':
    default:
      return [
        { unit: 'month', step: 1, format: '%F %Y' },
        { unit: 'week', step: 1, format: '%W' },
      ]
  }
}
