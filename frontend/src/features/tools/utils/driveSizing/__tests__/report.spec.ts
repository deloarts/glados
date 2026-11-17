import { describe, expect, it } from 'vitest'

import { createReportContext } from '@/shared/reports'
import { reportTexts } from '@/test-utils/reportTexts'
import { chartLayout } from '../chart'
import { sizeDrive } from '../engine'
import { useDriveSizingFormat } from '../format'
import { encodeDriveSizingInputs } from '../inputs'
import { emptyDriveSizingInput } from '../model'
import { sampleDriveSizingInput } from '@/features/tools/__tests__/fixtures'
import { chartSvg, driveSizingReport } from '../report'
import { driveSizingSnapshot } from '../snapshot'

describe('driveSizingReport', () => {
  it('reports the example axis with every section, recalculated from its inputs', () => {
    const input = sampleDriveSizingInput()
    const report = driveSizingReport(encodeDriveSizingInputs(input), createReportContext('enGB'))
    const all = reportTexts(report.body)

    expect(report.subtitle).toBe('Vertical axis, 140 kg, i = 12')
    expect(all).toEqual(
      expect.arrayContaining([
        'Results',
        'All checks passed.',
        'Settings',
        'Speed and torque over the cycle',
        'Motion profile',
        'Segments',
        'Peak motor torque',
        '6.47 Nm',
        'Rack and pinion',
      ]),
    )
    expect(report.results).toEqual(driveSizingSnapshot(input, sizeDrive(input)))
  })

  it('writes texts and numbers in the language of the report', () => {
    const report = driveSizingReport(encodeDriveSizingInputs(sampleDriveSizingInput()), createReportContext('deAT'))
    const all = reportTexts(report.body)

    expect(report.subtitle).toBe('Vertikale Achse, 140 kg, i = 12')
    expect(all).toEqual(expect.arrayContaining(['Ergebnisse', 'Alle Nachweise erfüllt.', '6,47 Nm']))
  })

  it('lists what is missing instead of results for incomplete inputs', () => {
    const report = driveSizingReport(encodeDriveSizingInputs(emptyDriveSizingInput()), createReportContext('enGB'))
    const all = reportTexts(report.body)

    expect(all).toEqual(expect.arrayContaining(['No results yet', 'Stroke (Axis) is missing.', 'Settings']))
    expect(all).not.toContain('Results')
    expect(all).not.toContain('Motion profile')
    expect(report.results).toMatchObject({ ok: false })
  })
})

describe('chartSvg', () => {
  it('draws the curve, the reference lines and their labels in fixed colours', () => {
    const fmt = useDriveSizingFormat('enGB')
    const svg = chartSvg(
      [
        [0, 0],
        [1, 5],
        [2, 0],
      ],
      2,
      [{ value: 6, symbol: ['M', 'max'], tone: 'limit' }],
      'Nm',
      'Time in s',
      fmt,
    )
    const doc = new DOMParser().parseFromString(svg, 'image/svg+xml')

    expect(doc.querySelector('parsererror')).toBeNull()
    expect(doc.documentElement.getAttribute('font-family')).toBe('Carlito')
    expect(doc.querySelectorAll('path')).toHaveLength(2)
    expect(svg).toContain('stroke-dasharray="6 4"')
    expect(svg).not.toContain('var(--')
    expect([...doc.querySelectorAll('text')].map((node) => node.textContent)).toEqual(
      expect.arrayContaining(['Mmax', 'Nm', 'Time in s']),
    )
  })

  it('escapes text so a unit cannot break the markup', () => {
    const svg = chartSvg([], 1, [], '<b>&', 'x', useDriveSizingFormat('enGB'))

    expect(svg).toContain('&lt;b&gt;&amp;')
  })
})

describe('chartLayout', () => {
  it('pushes reference labels apart that would overlap', () => {
    const layout = chartLayout(
      [
        [0, 0],
        [1, 10],
      ],
      1,
      [
        { value: 5, symbol: ['M', 'N'], tone: 'rated' },
        { value: 5.1, symbol: ['M', 'rms'], tone: 'mean' },
      ],
    )
    const [upper, lower] = layout.labels

    expect(lower!.y - upper!.y).toBeGreaterThanOrEqual(14)
  })
})
