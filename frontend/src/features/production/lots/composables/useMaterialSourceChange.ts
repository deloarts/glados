import { computed, type MaybeRefOrGetter, toValue } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { hasAction } from '@/core/utils/lifecycleActions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'

import type { LotResponse, LotSummaryResponse } from '../../types/productionLotsResponse'

type LotSourceChangeFields = Pick<
  LotResponse | LotSummaryResponse,
  'actions' | 'input_demand_id' | 'demand_status'
>

/**
 * Why a lot's material source cannot be changed now, or '' when it can:
 * write:lots is missing, the server offers no switch on the lot (it is
 * finished), or its raw material demand is fulfilled. The lot
 * page's Change button and the lots table's Add Source Item menu entry
 * show the same text.
 */
export function useMaterialSourceChangeReason() {
  const { t } = useI18n()
  const { missing } = useMissingPermission()

  function sourceChangeBlockedReason(
    lot: LotSourceChangeFields | null | undefined,
    canWrite: boolean,
  ): string {
    if (!canWrite) return missing(Permission.WRITE_LOTS)
    if (!lot || !hasAction(lot, 'switch_source')) {
      return t('production.lots.detail.materialSource.finishedTooltip')
    }
    if (lot.input_demand_id && lot.demand_status === 'fulfilled') {
      return t('production.lots.detail.materialSource.lockedTooltip')
    }
    return ''
  }

  return { sourceChangeBlockedReason }
}

/** The reason of `useMaterialSourceChangeReason` for one lot, as the tooltip of the disabled Change button. */
export function useMaterialSourceChange(
  lot: MaybeRefOrGetter<LotResponse | null | undefined>,
  canWrite: MaybeRefOrGetter<boolean>,
) {
  const { sourceChangeBlockedReason } = useMaterialSourceChangeReason()

  const sourceChangeBlocked = computed(() =>
    sourceChangeBlockedReason(toValue(lot), toValue(canWrite)),
  )

  return { sourceChangeBlocked }
}
