import { describe, it, expect, afterEach } from 'vitest'

import { conflictLabelKey, conflictSeverity, conflictTooltipKey } from '../productionOrderConflicts'
import { i18n } from '@/core/i18n'

import type { ScheduleConflict } from '../../types/productionOrdersResponse'

// Kept as an explicit literal list, not derived from
// Object.keys(conflictSeverity): conflictSeverity is typed
// Record<ScheduleConflict, string>, so TypeScript already fails the build
// if a new union member is missing there. This list makes a missing entry
// fail loudly at plain `vitest run` time too, and is also what pins the
// severity/label expectations below to a real ScheduleConflict, not a typo.
const ALL_CONFLICTS: ScheduleConflict[] = [
  'no_machine_assigned',
  'capability_mismatch',
  'uncategorized_step',
  'position_not_fully_queued',
  'waiting_on_predecessor',
  'waiting_on_material',
  'estimate_from_time_budget',
  'missing_time_estimate',
  'past_target_date',
  'external_date_before_predecessor',
  'machine_down',
]

describe('conflictSeverity', () => {
  it('has a severity for every ScheduleConflict', () => {
    for (const conflict of ALL_CONFLICTS) {
      expect(conflictSeverity[conflict]).toBeTruthy()
    }
  })

  it('flags waiting_on_material (no material at all) harder than waiting_on_predecessor (a mid-chain wait)', () => {
    expect(conflictSeverity.waiting_on_material).toBe('warn')
    expect(conflictSeverity.waiting_on_predecessor).toBe('info')
  })

  it('flags machine_down at the hardest severity, same as past_target_date', () => {
    expect(conflictSeverity.machine_down).toBe('danger')
  })
})

describe('conflictLabelKey / conflictTooltipKey', () => {
  it('builds the expected i18n key path for every ScheduleConflict', () => {
    for (const conflict of ALL_CONFLICTS) {
      expect(conflictLabelKey(conflict)).toBe(`productionQueue.conflicts.${conflict}`)
      expect(conflictTooltipKey(conflict)).toBe(`productionQueue.conflicts.${conflict}Tooltip`)
    }
  })

  describe('resolves to a real translation (not the raw key) in both locales', () => {
    afterEach(() => {
      i18n.global.locale.value = 'enGB'
    })

    it('en-GB', () => {
      i18n.global.locale.value = 'enGB'
      for (const conflict of ALL_CONFLICTS) {
        expect(i18n.global.t(conflictLabelKey(conflict))).not.toBe(conflictLabelKey(conflict))
        expect(i18n.global.t(conflictTooltipKey(conflict))).not.toBe(conflictTooltipKey(conflict))
      }
    })

    it('de-AT', () => {
      i18n.global.locale.value = 'deAT'
      for (const conflict of ALL_CONFLICTS) {
        expect(i18n.global.t(conflictLabelKey(conflict))).not.toBe(conflictLabelKey(conflict))
        expect(i18n.global.t(conflictTooltipKey(conflict))).not.toBe(conflictTooltipKey(conflict))
      }
    })
  })
})
