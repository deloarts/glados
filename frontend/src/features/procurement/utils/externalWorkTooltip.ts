import { formatDateOrDash } from '@/core/utils/dates'

import type { Schemas } from '@/core/api/generated'
import type { LocalizedText } from '@/shared/utils/localizedText'

type DateTerm = Schemas['DateTermResult']
type Translate = (key: string, named?: Record<string, unknown>, plural?: number) => string

const KEY = 'procurement.externalWork.tooltip'

/**
 * The tooltip of a date in the external work list: one line per term of
 * how the date came about, then a note when the stored date has not caught
 * up yet. A lead time is subtracted while the latest pickup is counted back
 * and added while "back by" is counted forward, so the caller says which.
 */
export function externalWorkDateTooltip(
  terms: DateTerm[],
  options: {
    t: Translate
    localize: (text: LocalizedText) => string
    leadTimeSign: '+' | '−'
    stale: boolean
  },
): string | undefined {
  if (terms.length === 0) return undefined
  const { t, localize } = options
  const methods = (term: DateTerm) => term.methods.map((m) => localize(m)).join(', ')
  const lines = terms.map((term) => {
    const date = formatDateOrDash(term.date)
    const days = term.days ?? 0
    switch (term.kind) {
      case 'after_step':
        return t(`${KEY}.afterStep`, { methods: methods(term), date })
      case 'raw_material':
        return t(`${KEY}.rawMaterial`, { date })
      case 'late_arrival':
        return t(`${KEY}.lateArrival`, { date })
      case 'response_time':
        return t(`${KEY}.responseTime`, { days }, days)
      case 'target_lot':
        return t(`${KEY}.targetLot`, { date })
      case 'target_demand':
        return t(`${KEY}.targetDemand`, { date, demand: term.reference })
      case 'safety_margin':
        return t(`${KEY}.safetyMargin`, { days }, days)
      case 'later_step':
        return term.minutes !== null
          ? t(`${KEY}.laterStepMinutes`, { days, methods: methods(term), minutes: term.minutes }, days)
          : t(`${KEY}.laterStep`, { days, methods: methods(term) }, days)
      case 'wait_after':
        return t(`${KEY}.waitAfter`, { days, methods: methods(term), minutes: term.minutes ?? 0 }, days)
      case 'back_by':
        return t(`${KEY}.backBy`, { date })
      case 'lead_time':
        return t(
          `${KEY}.leadTime`,
          { sign: options.leadTimeSign, days, source: t(`${KEY}.leadSource.${term.source ?? 'default'}`) },
          days,
        )
      case 'latest_pickup':
        return t(`${KEY}.latestPickup`, { date })
      case 'supplier_date':
        return t(`${KEY}.supplierDate`, { date, order: term.reference })
      case 'result':
        return t(`${KEY}.result`, { date })
      default:
        return ''
    }
  })
  if (options.stale) lines.push(t(`${KEY}.stale`))
  return lines.filter(Boolean).join('\n')
}
