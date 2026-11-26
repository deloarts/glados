import { describe, expect, it } from 'vitest'

import { i18n } from '@/core/i18n'
import { externalWorkDateTooltip } from '../externalWorkTooltip'

import type { Schemas } from '@/core/api/generated'

type DateTerm = Schemas['DateTermResult']

function term(kind: DateTerm['kind'], fields: Partial<DateTerm> = {}): DateTerm {
  return { kind, date: null, days: null, minutes: null, methods: [], source: null, reference: '', ...fields }
}

const t = (key: string, named?: Record<string, unknown>, plural?: number) =>
  plural === undefined ? i18n.global.t(key, named ?? {}) : i18n.global.t(key, named ?? {}, plural)
const localize = (text: Record<string, string>) => text.enGB ?? ''

describe('externalWorkDateTooltip', () => {
  it('counts the latest pickup back from the target date, one line per term', () => {
    const tooltip = externalWorkDateTooltip(
      [
        term('target_demand', { date: '2026-08-20', reference: '3' }),
        term('safety_margin', { days: 2 }),
        term('later_step', { days: 1, minutes: 20, methods: [{ enGB: 'Visual check' }] }),
        term('back_by', { date: '2026-08-17' }),
        term('lead_time', { days: 4, source: 'method' }),
        term('result', { date: '2026-08-13' }),
      ],
      { t, localize, leadTimeSign: '−', stale: false },
    )

    expect(tooltip?.split('\n')).toEqual([
      'Target date 2026-08-20 (from demand #3)',
      '− 2 days safety margin',
      '− 1 day Visual check (20 min)',
      '= back by 2026-08-17',
      '− 4 days lead time (from the methods)',
      '= 2026-08-13',
    ])
  })

  it('adds the lead time when counting forward, and flags a plan still being updated', () => {
    const tooltip = externalWorkDateTooltip(
      [
        term('after_step', { date: '2026-08-03', methods: [{ enGB: 'Milling' }] }),
        term('response_time', { days: 1 }),
        term('result', { date: '2026-08-04' }),
      ],
      { t, localize, leadTimeSign: '+', stale: true },
    )

    expect(tooltip?.split('\n')).toEqual([
      'Milling ready on 2026-08-03',
      '+ 1 day response time',
      '= 2026-08-04',
      'The plan is being updated, this date may still change.',
    ])
  })

  it('counts the wait after a later step back in days', () => {
    const tooltip = externalWorkDateTooltip(
      [
        term('target_lot', { date: '2026-08-20' }),
        term('later_step', { days: 1, minutes: 30, methods: [{ enGB: 'Painting' }] }),
        term('wait_after', { days: 2, minutes: 1440, methods: [{ enGB: 'Painting' }] }),
        term('back_by', { date: '2026-08-17' }),
      ],
      { t, localize, leadTimeSign: '−', stale: false },
    )

    expect(tooltip?.split('\n')).toEqual([
      'Target date of the lot 2026-08-20',
      '− 1 day Painting (30 min)',
      '− 2 days waiting after Painting (1440 min)',
      '= back by 2026-08-17',
    ])
  })

  it('counts a passed expected arrival from today', () => {
    const tooltip = externalWorkDateTooltip(
      [
        term('raw_material', { date: '2026-11-20' }),
        term('late_arrival', { date: '2026-11-25' }),
        term('response_time', { days: 1 }),
        term('result', { date: '2026-11-26' }),
      ],
      { t, localize, leadTimeSign: '+', stale: false },
    )

    expect(tooltip?.split('\n')).toEqual([
      'Raw material in on 2026-11-20',
      'Not there yet, counts from today 2026-11-25',
      '+ 1 day response time',
      '= 2026-11-26',
    ])
  })

  it('shows nothing for a date without terms', () => {
    expect(externalWorkDateTooltip([], { t, localize, leadTimeSign: '+', stale: false })).toBeUndefined()
  })
})
