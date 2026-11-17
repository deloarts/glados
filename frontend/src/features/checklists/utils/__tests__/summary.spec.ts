import { describe, expect, it } from 'vitest'

import { CHECKLISTS } from '../definitions'
import { emptyState } from '../state'
import { checklistResults } from '../summary'

const TODAY = new Date(2026, 9, 8)

describe('checklist results', () => {
  it('holds codes, counts, completion and findings, never translated text', () => {
    const definition = CHECKLISTS.hydraulics
    const state = emptyState(TODAY)
    definition.items.slice(0, 10).forEach((item) => (state.answers[item.id] = 'yes'))
    const [first, second] = definition.items
    if (first) state.answers[first.id] = 'defect'
    if (second) state.answers[second.id] = 'no'
    if (first) state.remarks[first.id] = 'Parts list missing'
    const total = definition.items.length

    const results = checklistResults(definition, state)

    expect(results).toEqual({
      type: 'hydraulics',
      legalBasis: 'directive',
      counts: { total, answered: 10, open: total - 10, na: 0, yes: 8, no: 1, defect: 1 },
      completion: Math.floor((10 / total) * 100),
      verdict: 'failed',
      problems: [
        { id: 'assessment.documents', position: '1.1/1', answer: 'defect', remark: 'Parts list missing' },
        { id: 'assessment.circuitFunctions', position: '1.1/1.1', answer: 'no', remark: '' },
      ],
    })
    expect(JSON.parse(JSON.stringify(results))).toEqual(results)
  })
})
