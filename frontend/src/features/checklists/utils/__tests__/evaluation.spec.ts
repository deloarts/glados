import { describe, expect, it } from 'vitest'

import { CHECKLISTS } from '../definitions'
import { completionPercent, countAnswers, findingsWithoutRemark, problemsOf, verdictOf } from '../evaluation'
import { formatReference, formatReferences } from '../references'
import { emptyHeader, emptyState, isIsoDate, legalBasisFor } from '../state'
import type { Answer, ChecklistState } from '../types'

const TODAY = new Date(2026, 9, 8)
const pneumatics = CHECKLISTS.pneumatics

function answerAll(answer: Answer): ChecklistState {
  const state = emptyState(TODAY)
  for (const item of pneumatics.items) state.answers[item.id] = answer
  return state
}

describe('answer counts and verdict', () => {
  it('counts every answer state and the unanswered items', () => {
    const state = emptyState(TODAY)
    const [a, b, c, d] = pneumatics.items
    if (!a || !b || !c || !d) throw new Error('too few items')
    state.answers[a.id] = 'na'
    state.answers[b.id] = 'yes'
    state.answers[c.id] = 'no'
    state.answers[d.id] = 'defect'

    const counts = countAnswers(pneumatics.items, state.answers)
    expect(counts).toEqual({
      total: pneumatics.items.length,
      answered: 4,
      open: pneumatics.items.length - 4,
      na: 1,
      yes: 1,
      no: 1,
      defect: 1,
    })
    expect(verdictOf(counts)).toBe('failed')
  })

  it('stays open while items are unanswered and there are no findings', () => {
    const state = answerAll('yes')
    const first = pneumatics.items[0]
    if (first) delete state.answers[first.id]
    expect(verdictOf(countAnswers(pneumatics.items, state.answers))).toBe('open')
  })

  it('passes once every item is answered without findings, n/a included', () => {
    const state = answerAll('yes')
    const first = pneumatics.items[0]
    if (first) state.answers[first.id] = 'na'
    const counts = countAnswers(pneumatics.items, state.answers)

    expect(verdictOf(counts)).toBe('passed')
    expect(completionPercent(counts)).toBe(100)
  })

  it('fails when every item is answered and one is a finding', () => {
    for (const finding of ['no', 'defect'] as const) {
      const state = answerAll('yes')
      const last = pneumatics.items[pneumatics.items.length - 1]
      if (last) state.answers[last.id] = finding
      expect(verdictOf(countAnswers(pneumatics.items, state.answers))).toBe('failed')
    }
  })

  it('fails as soon as one item is a finding, even while others are unanswered', () => {
    const state = answerAll('no')
    const first = pneumatics.items[0]
    if (first) delete state.answers[first.id]
    const counts = countAnswers(pneumatics.items, state.answers)

    expect(verdictOf(counts)).toBe('failed')
    expect(completionPercent(counts)).toBe(99)
  })

  it('names the findings that still need a remark', () => {
    const state = emptyState(TODAY)
    state.answers['circuit.manualOverride'] = 'no'
    state.answers['vesselCheck.noModifications'] = 'defect'
    state.remarks['vesselCheck.noModifications'] = 'Weld seam on the nozzle'
    expect(findingsWithoutRemark(pneumatics, state)).toEqual(['circuit.manualOverride'])
  })

  it('lists findings in checklist order with position and remark', () => {
    const state = emptyState(TODAY)
    const later = pneumatics.itemById.get('vesselCheck.noModifications')
    const earlier = pneumatics.itemById.get('circuit.manualOverride')
    if (!later || !earlier) throw new Error('missing item')
    state.answers[later.id] = 'defect'
    state.answers[earlier.id] = 'no'
    state.answers['circuit.iso1219'] = 'yes'
    state.remarks[later.id] = 'Weld seam on the nozzle'

    expect(problemsOf(pneumatics, state)).toEqual([
      { id: 'circuit.manualOverride', position: '1.2/6', answer: 'no', remark: '' },
      { id: 'vesselCheck.noModifications', position: '2.14/3', answer: 'defect', remark: 'Weld seam on the nozzle' },
    ])
  })
})

describe('legal basis', () => {
  it('switches to the Regulation for machinery placed on the market from 2027-01-20', () => {
    expect(legalBasisFor('2027-01-19', TODAY)).toBe('directive')
    expect(legalBasisFor('2027-01-20', TODAY)).toBe('regulation')
    expect(legalBasisFor('2030-06-01', TODAY)).toBe('regulation')
  })

  it('decides by today when no valid planned date is given', () => {
    expect(legalBasisFor('', TODAY)).toBe('directive')
    expect(legalBasisFor('', new Date(2027, 0, 20))).toBe('regulation')
    expect(legalBasisFor('soon', new Date(2027, 5, 1))).toBe('regulation')
    expect(emptyHeader(TODAY).legalBasis).toBe('directive')
  })

  it('accepts only real calendar dates', () => {
    expect(isIsoDate('2027-01-20')).toBe(true)
    expect(isIsoDate('2028-02-29')).toBe(true)
    expect(isIsoDate('2027-02-29')).toBe(false)
    expect(isIsoDate('20.01.2027')).toBe(false)
  })

  it('cites the machinery requirements as Annex I or Annex III', () => {
    const t = (key: string, params?: Record<string, unknown>) =>
      key.endsWith('.machinery') ? `Annex ${String(params?.annex)} ${String(params?.point)}` : key
    expect(formatReference({ kind: 'machinery', point: '1.5.4' }, 'directive', t)).toBe('Annex I 1.5.4')
    expect(formatReference({ kind: 'machinery', point: '1.5.4' }, 'regulation', t)).toBe('Annex III 1.5.4')
  })

  it('joins consecutive clauses of one document and consecutive machinery points', () => {
    const t = (key: string, params?: Record<string, unknown>) => {
      if (key.endsWith('.machinery')) return `Annex ${String(params?.annex)} ${String(params?.point)}`
      if (key.endsWith('.iso4413')) return 'ISO 4413:2010'
      if (key.endsWith('.iso12100')) return 'ISO 12100:2010'
      return key
    }
    const refs = [
      { kind: 'clause', doc: 'iso4413', clause: '5.2' },
      { kind: 'clause', doc: 'iso4413', clause: '5.4.1.6' },
      { kind: 'machinery', point: '1.7' },
      { kind: 'machinery', point: '1.2.2' },
      { kind: 'clause', doc: 'iso12100', clause: '6.2.8' },
    ] as const
    expect(formatReferences(refs, 'regulation', t)).toEqual([
      'ISO 4413:2010, 5.2, 5.4.1.6',
      'Annex III 1.7, 1.2.2',
      'ISO 12100:2010, 6.2.8',
    ])
  })
})
