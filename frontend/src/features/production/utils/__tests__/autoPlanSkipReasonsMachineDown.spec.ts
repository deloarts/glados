import { describe, it, expect, afterEach } from 'vitest'

import { skipReasonLabelKey, skipReasonTooltipKey } from '../autoPlanSkipReasons'
import { i18n } from '@/core/i18n'

// Coverage for the machine_down AutoPlanSkipReason specifically, kept
// separate from autoPlanSkipReasons.spec.ts (an existing, untouched test
// file) rather than extending its own literal ALL_SKIP_REASONS list.
describe('skipReasonLabelKey / skipReasonTooltipKey for machine_down', () => {
  it('builds the expected i18n key path', () => {
    expect(skipReasonLabelKey('machine_down')).toBe(
      'productionSchedule.autoPlan.skippedOrders.reasons.machine_down',
    )
    expect(skipReasonTooltipKey('machine_down')).toBe(
      'productionSchedule.autoPlan.skippedOrders.reasons.machine_downTooltip',
    )
  })

  describe('resolves to a real translation (not the raw key) in both locales', () => {
    afterEach(() => {
      i18n.global.locale.value = 'enGB'
    })

    it('en-GB', () => {
      i18n.global.locale.value = 'enGB'
      expect(i18n.global.t(skipReasonLabelKey('machine_down'))).not.toBe(
        skipReasonLabelKey('machine_down'),
      )
      expect(i18n.global.t(skipReasonTooltipKey('machine_down'))).not.toBe(
        skipReasonTooltipKey('machine_down'),
      )
    })

    it('de-AT', () => {
      i18n.global.locale.value = 'deAT'
      expect(i18n.global.t(skipReasonLabelKey('machine_down'))).not.toBe(
        skipReasonLabelKey('machine_down'),
      )
      expect(i18n.global.t(skipReasonTooltipKey('machine_down'))).not.toBe(
        skipReasonTooltipKey('machine_down'),
      )
    })
  })
})
