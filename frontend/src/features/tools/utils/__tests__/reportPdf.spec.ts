import { describe, expect, it, vi } from 'vitest'

vi.mock('../safetyDistance/reportSketches', () => ({
  renderSafetyDistanceSketches: vi.fn<() => Promise<Array<{ svg: string; caption: string | null }>>>(async () => [
    {
      svg: '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="40"><line x1="0" y1="0" x2="100" y2="40" stroke="#1d2430"/></svg>',
      caption: 'Side view',
    },
  ]),
}))

import { isPdfA2b, renderPdfForTest } from '@/test-utils/renderPdfForTest'
import { composeReport } from '@/shared/reports'
import type { ReportBranding } from '@/shared/reports'
import { toolByKey } from '../../registry'
import { encodeDriveSizingInputs } from '../driveSizing/inputs'
import { sampleDriveSizingInput, sampleSafetyDistanceInputs } from '@/features/tools/__tests__/fixtures'
import { encodeSafetyDistanceInputs } from '../safetyDistance/inputRecord'
import { toolReportSpec } from '../toolReport'

const BRANDING: ReportBranding = { appName: 'Glados', companyName: 'Example Ltd', companyLogoUrl: null, domain: null, exportedBy: 'Jane Doe' }

describe('tool reports as PDF', () => {
  it('renders the drive sizing report as an archival PDF', async () => {
    const spec = toolReportSpec(toolByKey('drive_sizing')!, null, {
      inputs: encodeDriveSizingInputs(sampleDriveSizingInput()),
      title: 'Lift axis',
    })!

    const pdf = await renderPdfForTest(await composeReport(spec, BRANDING, 'enGB', {}))

    expect(isPdfA2b(pdf)).toBe(true)
  })

  it('renders the safety distance report with its appendix as an archival PDF', async () => {
    const spec = toolReportSpec(toolByKey('safety_distance')!, null, {
      inputs: encodeSafetyDistanceInputs(sampleSafetyDistanceInputs()),
      title: 'Station 3',
    })!

    const pdf = await renderPdfForTest(await composeReport(spec, BRANDING, 'deAT', { appendix: true }))

    expect(isPdfA2b(pdf)).toBe(true)
  })
})
