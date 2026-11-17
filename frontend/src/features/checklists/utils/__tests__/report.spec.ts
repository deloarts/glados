import { describe, expect, it } from 'vitest'

import { i18n } from '@/core/i18n'
import { createReportContext } from '@/shared/reports'
import type { ReportContent } from '@/shared/reports'
import { reportTexts } from '@/test-utils/reportTexts'
import type { ChecklistResponse } from '../../types/checklist'
import { CHECKLISTS, itemHintKey, itemTextKey } from '../definitions'
import { checklistReportSpec } from '../report'
import { CHECKLIST_TYPES } from '../types'
import type { ChecklistType } from '../types'

const [FIRST, SECOND] = CHECKLISTS.hydraulics.items

function checklist(overrides: Partial<ChecklistResponse> = {}): ChecklistResponse {
  return {
    id: 31,
    public_id: 'b0f6c5d4-0000-4000-8000-000000000031',
    created: '2026-10-08T09:12:00Z',
    changed: null,
    changes: [],
    type: 'hydraulics',
    title: 'Press 12',
    header: {
      ownerNumber: 'P-24017',
      ownerCustomer: 'Example Ltd',
      ownerProduct: 'M26000',
      ownerManager: 'Jane Doe',
      designation: 'Press 12',
      legalBasis: 'regulation',
      assessedOn: '2026-10-08',
    },
    answers: { [FIRST!.id]: 'yes', [SECOND!.id]: 'no' },
    remarks: { [SECOND!.id]: 'Guard missing on the pump coupling.' },
    definition_version: 1,
    item_count: CHECKLISTS.hydraulics.items.length,
    answered_count: 2,
    finding_count: 1,
    verdict: 'failed',
    finished: false,
    release_required: true,
    read_only: false,
    project_id: 3,
    product_id: null,
    project_number: 'P-24017',
    product_number: null,
    lineage: 'b0f6c5d4-0000-4000-8000-0000000000aa',
    document_number: 'CHK-26-0017',
    revision: 'B',
    revision_reason: 'Pump replaced',
    is_latest: true,
    superseded_at: null,
    creator_id: 1,
    creator_full_name: 'Jane Doe',
    released_at: null,
    released_by_id: null,
    released_by_full_name: null,
    reason: null,
    ...overrides,
  } as unknown as ChecklistResponse
}

async function build(c: ChecklistResponse, locale: 'enGB' | 'deAT' = 'enGB', options = {}): Promise<ReportContent> {
  return checklistReportSpec(c)!.build(createReportContext(locale, options))
}

const t = (key: string) => i18n.global.t(key, {}, { locale: 'enGB' })

describe('checklistReportSpec', () => {
  it('prints the selected revision against the checklist and offers the explanations', () => {
    const spec = checklistReportSpec(checklist())!

    expect(spec.title).toBe('Press 12')
    expect(spec.printTarget).toEqual({ document: 'checklist_report', rootPublicId: 'b0f6c5d4-0000-4000-8000-000000000031' })
    expect(spec.options).toEqual([{ key: 'hints', labelKey: 'checklists.report.hintsOption' }])
  })

  it('shows the details, the result and the findings of the revision', async () => {
    const report = await build(checklist())
    const details = reportTexts(report.details.map((detail) => detail.value))
    const body = reportTexts(report.body)

    expect(report.kind).toBe('Hydraulics')
    expect(details).toEqual(expect.arrayContaining(['Project P-24017', 'Draft, not released', 'CHK-26-0017 rev. B, Pump replaced']))
    expect(body).toEqual(
      expect.arrayContaining([
        'Result',
        'Failed',
        'Findings',
        'Guard missing on the pump coupling.',
        'Checklist data',
        'Example Ltd',
        'Regulation (EU) 2023/1230',
        '8 Oct 2026',
        'Not released yet',
      ]),
    )
    expect(body).not.toContain('Changes since revision A')
  })

  it('shows the release that signed the revision off', async () => {
    const report = await build(
      checklist({ released_at: '2026-10-09T08:00:00Z', released_by_full_name: 'John Smith', verdict: 'passed' }),
    )

    expect(reportTexts(report.details.map((detail) => detail.value)).some((text) => text.startsWith('Released by John Smith'))).toBe(true)
  })

  it.each(CHECKLIST_TYPES)('reports every item of a %s checklist', async (type: ChecklistType) => {
    const definition = CHECKLISTS[type]
    const report = await build(checklist({ type, answers: {}, remarks: {} }))
    const body = reportTexts(report.body)

    const missing = definition.items.filter((item) => !body.includes(t(itemTextKey(type, item)))).map((item) => item.id)

    expect(missing).toEqual([])
    for (const part of definition.parts) expect(body.some((text) => text.startsWith(`${part.number} `))).toBe(true)
  })

  it('adds the explanations of the items only when asked', async () => {
    const definition = CHECKLISTS.hydraulics
    const item = definition.items.find((candidate) => candidate.hint)!
    const hint = t(itemHintKey('hydraulics', item))

    expect(reportTexts((await build(checklist())).body)).not.toContain(hint)
    expect(reportTexts((await build(checklist(), 'enGB', { hints: true })).body)).toContain(hint)
  })

  it('writes the report in the chosen language', async () => {
    const report = await build(checklist(), 'deAT')

    expect(reportTexts(report.body)).toEqual(expect.arrayContaining(['Ergebnis', 'Nicht bestanden', '08.10.2026']))
  })

  it('has no report for a checklist type this app does not know', () => {
    expect(checklistReportSpec(checklist({ type: 'welding' }))).toBeNull()
  })
})
