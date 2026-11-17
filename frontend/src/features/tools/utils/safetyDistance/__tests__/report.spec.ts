import { describe, expect, it, vi } from 'vitest'

const SKETCH = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><line x1="0" y1="0" x2="10" y2="10"/></svg>'

vi.mock('../reportSketches', () => ({
  renderSafetyDistanceSketches: vi.fn<() => Promise<Array<{ svg: string; caption: string | null }>>>(async () => [
    { svg: SKETCH, caption: 'Side view, not to scale.' },
  ]),
}))

import { createReportContext } from '@/shared/reports'
import { reportTexts } from '@/test-utils/reportTexts'
import { calculateSafetyDistance, safetyDistanceSnapshot } from '../calculate'
import { encodeSafetyDistanceInputs } from '../inputRecord'
import { sampleSafetyDistanceInputs } from '@/features/tools/__tests__/fixtures'
import { safetyDistanceReport } from '../report'
import type { SafetyDistanceInputs, SafetyDistanceMode } from '../types'

function inputsFor(mode: SafetyDistanceMode): SafetyDistanceInputs {
  return { ...sampleSafetyDistanceInputs(), mode }
}

describe('safetyDistanceReport', () => {
  it('reports a light curtain as a calculation record, recalculated from its inputs', async () => {
    const inputs = inputsFor('espe')
    const report = await safetyDistanceReport(encodeSafetyDistanceInputs(inputs), createReportContext('enGB', {}))
    const all = reportTexts(report.body)

    expect(all).toEqual(
      expect.arrayContaining([
        'Separation distance',
        'Light curtain or beams',
        ' = 200 mm',
        'Protective device',
        'Effective detection capability ',
        'Response time',
        'Calculation',
        'Ways past the field',
        'Sketches',
        'Side view, not to scale.',
        'Standards applied',
        'ISO 13855:2024',
      ]),
    )
    // Sign-off happens in the app, so the report has no lines to sign.
    for (const label of ['Checked by', 'Date', 'Signature']) expect(all).not.toContain(label)
    expect(all).not.toContain('Appendix: reference tables')
    expect(JSON.stringify(report.body)).toContain(SKETCH.replace(/"/g, '\\"'))
    expect(report.results).toEqual(safetyDistanceSnapshot(inputs, calculateSafetyDistance(inputs)))
  })

  it('adds the reference tables as an appendix on its own page when asked', async () => {
    const record = encodeSafetyDistanceInputs(inputsFor('espe'))
    const report = await safetyDistanceReport(record, createReportContext('enGB', { appendix: true }))
    const appendix = report.body.at(-1) as { pageBreak?: string }

    expect(reportTexts(report.body)).toContain('Appendix: reference tables')
    expect(appendix.pageBreak).toBe('before')
  })

  it('writes a crushing point in German with its own standard and no response time', async () => {
    const report = await safetyDistanceReport(
      encodeSafetyDistanceInputs(inputsFor('crushing')),
      createReportContext('deAT', { appendix: true }),
    )
    const all = reportTexts(report.body)

    expect(all).toEqual(expect.arrayContaining(['ISO 13854:2017', 'Anhang: Referenztabellen']))
    for (const label of ['Geprüft von', 'Datum', 'Unterschrift']) expect(all).not.toContain(label)
    expect(all).not.toContain('Reaktionszeit')
    expect(all).not.toContain('ISO 13855:2024')
  })
})
