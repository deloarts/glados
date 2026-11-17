import { describe, expect, it } from 'vitest'

import { summarizeFit, summarizeGeneralTolerances, summarizeThreads } from '../toolSummaries'

const t = (key: string) => key

describe('tool summaries', () => {
  it('summarises a fit with its type', () => {
    const results = {
      size: 25,
      hole: { code: 'H7', upper: 21, lower: 0 },
      shaft: { code: 'g6', upper: -7, lower: -20 },
      fit: { type: 'clearance', maxClearance: 41, minClearance: 7 },
    }
    expect(summarizeFit(results, t)).toBe('Ø25 H7/g6, tools.fitCalculator.types.clearance')
  })

  it('summarises general tolerances and threads', () => {
    expect(summarizeGeneralTolerances({ designation: 'ISO 2768-mK', size: 25, linear: 0.2 }, t)).toBe(
      'ISO 2768-mK, 25 mm, ±0.2 mm',
    )
    expect(summarizeThreads({ thread: 'M8', propertyClass: '8.8', torque: 25 }, t)).toBe('M8 8.8, 25 Nm')
  })

  it('returns an empty string for an unexpected shape', () => {
    expect(summarizeFit({ hole: 'H7' }, t)).toBe('')
    expect(summarizeGeneralTolerances({}, t)).toBe('')
    expect(summarizeThreads({ thread: 8 }, t)).toBe('')
  })
})
