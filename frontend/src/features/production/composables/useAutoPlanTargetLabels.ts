import { useI18n } from 'vue-i18n'

import { formatDateOrDash } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

/**
 * Display helpers shared by the Auto-Plan progress feed and results table.
 * Names resolve from the maps the dialog loads; an unknown id falls back to
 * `#<id>`.
 */
export function useAutoPlanTargetLabels(
  machineNameById: () => Record<number, string>,
  poolNameById: () => Record<number, string>,
) {
  const { t } = useI18n()

  function machineLabel(id: number | null): string {
    if (id === null) return t('productionPlanning.noAssignment')
    return machineNameById()[id] ?? `#${id}`
  }

  function poolLabel(id: number): string {
    return poolNameById()[id] ?? `#${id}`
  }

  function formatWindow(start: string | null, end: string | null): string {
    if (!start && !end) return getEmptyPlaceholder()
    const from = formatDateOrDash(start)
    const to = formatDateOrDash(end)
    return `${from} – ${to}`
  }

  return { machineLabel, poolLabel, formatWindow }
}
