import { describe, expect, it, vi } from 'vitest'

import { createReportContext } from '@/shared/reports'
import type { ReportContent, ReportSpec } from '@/shared/reports'
import { reportTexts } from '@/test-utils/reportTexts'
import { TOOLS, toolByKey } from '../../registry'
import type { ToolDefinition } from '../../registry'
import type { CalculationResponse } from '../../types/calculation'
import { encodeDriveSizingInputs } from '../driveSizing/inputs'
import { sampleDriveSizingInput } from '@/features/tools/__tests__/fixtures'
import { sizeDrive } from '../driveSizing/engine'
import { driveSizingSnapshot } from '../driveSizing/snapshot'
import { toolReportSpec } from '../toolReport'
import type { ToolReportBuilder } from '../toolReport'
import { controlledDocumentFields } from '@/test-utils/controlledDocument'

const input = sampleDriveSizingInput()

function calculation(overrides: Partial<CalculationResponse> = {}): CalculationResponse {
  return {
    ...controlledDocumentFields(),
    id: 17,
    public_id: 'b0f6c5d4-0000-4000-8000-000000000017',
    created: '2026-10-08T09:12:00Z',
    changed: null,
    changes: [],
    tool: 'drive_sizing',
    title: 'Lift axis station 3',
    note: 'Motor from the frame contract.',
    inputs: encodeDriveSizingInputs(input),
    results: driveSizingSnapshot(input, sizeDrive(input)),
    input_version: 1,
    engine_version: 1,
    project_id: 3,
    product_id: null,
    project_number: 'P-24017',
    product_number: null,
    creator_id: 1,
    creator_full_name: 'Jane Doe',
    released_at: '2026-10-08T15:30:00Z',
    released_by_id: 2,
    released_by_full_name: 'John Smith',
    ...overrides,
  } as CalculationResponse
}

const driveSizing = toolByKey('drive_sizing')!

async function content(spec: ReportSpec | null, locale: 'enGB' | 'deAT' = 'enGB'): Promise<ReportContent> {
  return spec!.build(createReportContext(locale))
}

function detailTexts(report: ReportContent): string[] {
  return reportTexts(report.details.map((detail) => detail.value))
}

describe('toolReportSpec', () => {
  it('has a report for every tool whose calculations can be saved', () => {
    const withoutReport = TOOLS.filter((tool) => tool.saveable && !tool.report).map((tool) => tool.key)

    expect(withoutReport).toEqual([])
  })

  it('has no report for a reference tool', () => {
    expect(toolReportSpec(toolByKey('fit_calculator')!, null)).toBeNull()
  })

  it('reports a saved calculation with its details and prints against it', async () => {
    const spec = toolReportSpec(driveSizing, calculation())!
    const report = await content(spec)

    expect(spec.title).toBe('Lift axis station 3')
    expect(spec.printTarget).toEqual({ document: 'calculation_report', rootPublicId: 'b0f6c5d4-0000-4000-8000-000000000017' })
    expect(report.kind).toBe('Drive sizing')
    expect(report.title).toBe('Lift axis station 3')
    expect(report.subtitle).toBe('Vertical axis, 140 kg, i = 12')
    expect(detailTexts(report)).toEqual(
      expect.arrayContaining(['Project P-24017', 'Motor from the frame contract.', 'CAL-26-0001 rev. A, tool version 1']),
    )
    expect(detailTexts(report).some((text) => text.startsWith('Released by John Smith'))).toBe(true)
    expect(report.notice).toBeNull()
  })

  it('says so when the engine of today gives other results than the saved ones', async () => {
    const report = await content(toolReportSpec(driveSizing, calculation({ results: { ok: true, peakTorqueNm: 1 } })))

    expect(report.notice?.tone).toBe('warn')
    expect(report.notice?.text.startsWith('Calculated again today')).toBe(true)
  })

  it('reports unsaved inputs for download only', async () => {
    const spec = toolReportSpec(driveSizing, null, { inputs: encodeDriveSizingInputs(input), title: 'Vertical axis' })!
    const report = await content(spec, 'deAT')

    expect(spec.printTarget).toBeNull()
    expect(report.title).toBe('Vertikale Achse, 140 kg, i = 12')
    expect(detailTexts(report)).toEqual(['Nicht gespeichert'])
  })

  it('offers the report options of the tool and hands the choice to its report', async () => {
    const builder = vi.fn<ToolReportBuilder>(async () => ({ subtitle: 'Axis', body: [], results: {} }))
    const tool: ToolDefinition = {
      ...driveSizing,
      report: async () => builder,
      reportOptions: [{ key: 'appendix', labelKey: 'tools.safetyDistance.report.appendixOption' }],
    }
    const spec = toolReportSpec(tool, null)!

    await spec.build(createReportContext('enGB', { appendix: true }))

    expect(spec.options).toEqual(tool.reportOptions)
    expect(builder.mock.calls[0]?.[1].options).toEqual({ appendix: true })
  })
})
