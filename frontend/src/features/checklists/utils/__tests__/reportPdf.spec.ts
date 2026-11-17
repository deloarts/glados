import { describe, expect, it } from 'vitest'

import { isPdfA2b, renderPdfForTest } from '@/test-utils/renderPdfForTest'
import { composeReport } from '@/shared/reports'
import type { ReportBranding } from '@/shared/reports'
import type { ChecklistResponse } from '../../types/checklist'
import { CHECKLISTS } from '../definitions'
import { checklistReportSpec } from '../report'
import { CHECKLIST_TYPES } from '../types'

const BRANDING: ReportBranding = { appName: 'Glados', companyName: 'Example Ltd', companyLogoUrl: null, domain: null, exportedBy: 'Jane Doe' }

function checklist(type: (typeof CHECKLIST_TYPES)[number]): ChecklistResponse {
  const [first, second] = CHECKLISTS[type].items
  return {
    id: 31,
    public_id: 'b0f6c5d4-0000-4000-8000-000000000031',
    created: '2026-10-08T09:12:00Z',
    type,
    title: 'Press 12',
    header: { designation: 'Press 12', legalBasis: 'directive' },
    answers: { [first!.id]: 'yes', [second!.id]: 'defect' },
    remarks: { [second!.id]: 'Hose worn.' },
    project_id: null,
    product_id: null,
    revision: 'A',
    revision_reason: null,
    superseded_at: null,
    creator_full_name: 'Jane Doe',
    released_at: null,
    released_by_full_name: null,
  } as unknown as ChecklistResponse
}

describe('checklist reports as PDF', () => {
  it.each(CHECKLIST_TYPES)('renders a %s checklist with its explanations as an archival PDF', async (type) => {
    const spec = checklistReportSpec(checklist(type))!

    const pdf = await renderPdfForTest(await composeReport(spec, BRANDING, 'enGB', { hints: true }))

    expect(isPdfA2b(pdf)).toBe(true)
  })
})
