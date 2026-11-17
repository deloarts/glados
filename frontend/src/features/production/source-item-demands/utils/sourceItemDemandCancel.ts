/**
 * Why a raw material demand cannot be canceled now. The server offers the
 * cancel action only while the demand is live and its lot has not started
 * production, so a live demand without the action means the lot started.
 */

import { hasAction } from '@/core/utils/lifecycleActions'
import type { SourceItemDemandResponse } from '@/features/source-items'

export type CancelBlockedReason = '' | 'permission' | 'ended' | 'lotStarted'

export function cancelBlockedReason(
  demand: SourceItemDemandResponse,
  canWriteLots: boolean,
): CancelBlockedReason {
  if (!canWriteLots) return 'permission'
  if (hasAction(demand, 'cancel')) return ''
  if (demand.status === 'fulfilled' || demand.status === 'canceled') return 'ended'
  return 'lotStarted'
}
