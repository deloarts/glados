import { describe, it, expect, afterEach } from 'vitest'

import { skipReasonLabelKey, skipReasonTooltipKey } from '../autoPlanSkipReasons'
import { i18n } from '@/core/i18n'

import type { AutoPlanSkipReason } from '../../types/scheduleBoardResponse'

// Mirrors productionOrderConflicts.spec.ts's ALL_CONFLICTS treatment: kept
// as an explicit literal list, not derived from the util's own internal
// array, so a new AutoPlanSkipReason union member missing from either place
// fails loudly here too.
const ALL_SKIP_REASONS: AutoPlanSkipReason[] = [
  'waiting_on_material',
  'no_eligible_machine',
  'no_eligible_pool',
  'no_eligible_pool_member',
  'machine_down',
  'changed_while_planning',
]

// A reason string the backend might ship before this union catches up to it:
// exercises the graceful fallback path, distinct from ScheduleConflict's
// treatment (which assumes only real union members ever arrive).
const UNKNOWN_REASON = 'some_future_reason'

describe('skipReasonLabelKey / skipReasonTooltipKey', () => {
  it('builds the expected i18n key path for every AutoPlanSkipReason', () => {
    for (const reason of ALL_SKIP_REASONS) {
      expect(skipReasonLabelKey(reason)).toBe(
        `productionSchedule.autoPlan.skippedOrders.reasons.${reason}`,
      )
      expect(skipReasonTooltipKey(reason)).toBe(
        `productionSchedule.autoPlan.skippedOrders.reasons.${reason}Tooltip`,
      )
    }
  })

  it('falls back to the generic "unknown" key for a reason string outside the union', () => {
    expect(skipReasonLabelKey(UNKNOWN_REASON)).toBe(
      'productionSchedule.autoPlan.skippedOrders.reasons.unknown',
    )
    expect(skipReasonTooltipKey(UNKNOWN_REASON)).toBe(
      'productionSchedule.autoPlan.skippedOrders.reasons.unknownTooltip',
    )
  })

  describe('resolves to a real translation (not the raw key) in both locales', () => {
    afterEach(() => {
      i18n.global.locale.value = 'enGB'
    })

    const reasonsIncludingUnknown: string[] = [...ALL_SKIP_REASONS, UNKNOWN_REASON]

    it('en-GB', () => {
      i18n.global.locale.value = 'enGB'
      for (const reason of reasonsIncludingUnknown) {
        expect(i18n.global.t(skipReasonLabelKey(reason))).not.toBe(skipReasonLabelKey(reason))
        expect(i18n.global.t(skipReasonTooltipKey(reason))).not.toBe(skipReasonTooltipKey(reason))
      }
    })

    it('de-AT', () => {
      i18n.global.locale.value = 'deAT'
      for (const reason of reasonsIncludingUnknown) {
        expect(i18n.global.t(skipReasonLabelKey(reason))).not.toBe(skipReasonLabelKey(reason))
        expect(i18n.global.t(skipReasonTooltipKey(reason))).not.toBe(skipReasonTooltipKey(reason))
      }
    })
  })
})
