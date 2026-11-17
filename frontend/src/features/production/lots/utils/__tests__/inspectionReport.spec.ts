import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { createReportContext, composeReport } from '@/shared/reports'
import type { ReportBranding } from '@/shared/reports'
import { isPdfA2b, renderPdfForTest } from '@/test-utils/renderPdfForTest'
import { reportTexts } from '@/test-utils/reportTexts'
import { buildInspectionReport } from '../inspectionReport'
import type { InspectionReportData } from '../inspectionReportData'

const BRANDING: ReportBranding = {
  appName: 'Glados',
  companyName: 'Example Engineering GmbH',
  companyLogoUrl: null,
  domain: 'https://glados.example.com',
  exportedBy: 'Jane Doe',
}

const user = (full_name: string) => ({ id: 1, public_id: '00000000-0000-4000-8000-000000000001', username: 'u', full_name, email: '', has_avatar: false })

function completion(overrides: Record<string, unknown>) {
  return {
    id: 1,
    public_id: '00000000-0000-4000-8000-0000000000c1',
    production_order_id: 1863,
    quantity: 49,
    quantity_accepted: 47,
    quantity_rejected: 2,
    quantity_rework: 1,
    quantity_scrap: 1,
    scrap_reason: null,
    reject_reason: 'out_of_tolerance',
    completion_date: '2026-10-07',
    created: '2026-10-07T09:48:00Z',
    note: 'Piece 17 bore 39.992 mm.',
    operator: user('Anna Bogus'),
    operator_id: 1,
    recorded_by: user('Anna Bogus'),
    recorded_by_id: 1,
    ...overrides,
  }
}

function data(status = 'completed'): InspectionReportData {
  const lot = {
    id: 187,
    public_id: '6f1d2c4e-8a3b-4c51-9e27-0b5d8f4a1c63',
    lot_number: 'LOT-26-00412',
    status,
    note: null,
    created: '2026-09-29T08:15:00Z',
    creator: user('Eva Sample'),
    completed_at: status === 'completed' ? '2026-10-16T12:32:00Z' : null,
    quantity: 47,
    quantity_completed: 47,
    quantity_scrapped: 1,
    required_delivery_date: '2026-10-20',
    project_number: 'P-24017',
    project_customer: 'Example Machinery Ltd',
    made_item_id: 9,
    made_item_part_number: 'MT-20417',
    made_item_revision: 'C',
    made_item_article_name: 'Bearing housing',
    made_item_material: 'EN AW-6082 T6',
    source_label: 'Round bar EN AW-6082 T6',
    source_sublabel: 'Ø125 × 3000 mm',
    source_order_number: 'ORD-26-00297',
    source_delivery_date: '2026-10-01T07:40:00Z',
    source_approval_status: 'approved',
    source_approved_date: '2026-09-30T06:40:00Z',
    source_rejection_reason: null,
    origin_lot_number: null,
    origin_disposition: null,
    follow_up_lots: [{ id: 190, lot_number: 'LOT-26-00431', quantity: 1, disposition: 'rework' }],
    positions: [
      {
        id: 11,
        sequence: 1,
        kind: 'internal',
        status: 'completed',
        quantity_completed: 48,
        order_id: null,
        steps: [{ id: 1, role: 'fabrication', fabrication_method_name: 'CNC milling', inspection_method_name: null, note: null }],
      },
      {
        id: 12,
        sequence: 2,
        kind: 'internal',
        status: 'completed',
        quantity_completed: 47,
        order_id: null,
        steps: [
          {
            id: 2,
            role: 'inspection',
            inspection_method_id: 2,
            inspection_method_name: 'Dimensional check (CMM)',
            inspection_method_requires_evidence: true,
            fabrication_method_name: null,
            note: '100 % check of the bore Ø40 H7.',
          },
        ],
      },
      {
        id: 13,
        sequence: 3,
        kind: 'external',
        status: 'completed',
        quantity_completed: 47,
        order_id: 318,
        order_number: 'ORD-26-00318',
        supplier_name: 'Surface Finish Ltd',
        steps: [{ id: 3, role: 'fabrication', fabrication_method_name: 'Anodizing', inspection_method_name: null, note: null }],
      },
    ],
  }
  const orders = [
    {
      id: 1862,
      production_order_number: 'PON-26-01862',
      lot_position_id: 11,
      machine_internal_name: 'DMU-65-1',
      status: 'completed',
      actual_start: '2026-10-05T05:00:00Z',
      actual_end: '2026-10-06T13:30:00Z',
      started_operator: user('Lukas Widget'),
      completions: [completion({ id: 2, production_order_id: 1862, quantity: 1, quantity_accepted: 0, quantity_rejected: 0, quantity_rework: 0, quantity_scrap: 1, scrap_reason: 'tool_breakage', reject_reason: null, note: null })],
    },
    {
      id: 1863,
      production_order_number: 'PON-26-01863',
      lot_position_id: 12,
      machine_internal_name: 'CMM-01',
      status: 'completed',
      actual_start: '2026-10-07T05:05:00Z',
      actual_end: '2026-10-07T09:48:00Z',
      started_operator: user('Anna Bogus'),
      completions: [completion({})],
    },
  ]
  const supplierOrder = {
    id: 318,
    order_number: 'ORD-26-00318',
    items: [
      {
        lot_id: 187,
        lot_position_id: 13,
        position: 2,
        supplier_name: 'Surface Finish Ltd',
        ordered_date: '2026-09-04',
        quantity_delivered: 47,
        delivery_records: [
          {
            delivery_date: '2026-10-14T07:20:00Z',
            quantity: 47,
            quantity_rejected: 1,
            rejection_reason: 'supplier_damage',
            rejection_outcome: 'redeliver',
            rejection_note: 'Burn mark on the flange face.',
            receiver: user('Martin Hypothetical'),
          },
        ],
      },
    ],
  }
  return {
    lot,
    madeItem: { revision: 'C', revision_date: '2026-08-14', revision_note: 'Bore tolerance tightened to H7', mass: 1840, base_size: 'Ø120 × 85 mm' },
    madeItemFiles: [{ id: 1, category: 'drawing', file_name: 'MT-20417-C.pdf' }],
    partImage: null,
    productionOrders: orders,
    filesByOrder: new Map([[1863, [{ file_name: 'CMM_LOT-26-00412.pdf', created: '2026-10-07T09:40:00Z', size_bytes: 421888, sha256: '9f2c7d41b6e05a83c1f4e9d27a6b0c58e3d1f7a2946b8c05de71a3f9b4c62e18' }]]]),
    ordersById: new Map([[318, supplierOrder]]),
    provisionsByPosition: new Map([[13, [{ quantity: 47, provision_date: '2026-09-10' }]]]),
    methods: new Map([[2, { id: 2, description: 'Measure every toleranced dimension on the CMM.' }]]),
    events: [
      { occurred_at: '2026-10-07T09:48:00Z', actor_full_name: 'Anna Bogus', event_type: 'inspection_recorded' },
      { occurred_at: '2026-10-05T09:00:00Z', actor_full_name: 'Planner', event_type: 'steps_reordered' },
    ],
  } as unknown as InspectionReportData
}

describe('inspection report', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('reports every inspection with its reason, disposition and evidence', () => {
    const content = buildInspectionReport(data(), createReportContext('enGB'))
    const texts = reportTexts(content.body)

    expect(content.kind).toBe('Inspection report')
    expect(content.title).toBe('LOT-26-00412')
    expect(content.identity).toEqual({ publicId: '6f1d2c4e-8a3b-4c51-9e27-0b5d8f4a1c63', reference: 'Lot LOT-26-00412' })
    expect(content.notice).toBeNull()
    expect(texts).toEqual(
      expect.arrayContaining([
        'Position 2: Dimensional check (CMM)',
        'Measure every toleranced dimension on the CMM.',
        'Out of Tolerance',
        '1 rework, 1 scrap',
        'CMM_LOT-26-00412.pdf',
        '9f2c7d41b6e05a83',
        'Burn mark on the flange face.',
        'Tool Breakage',
        'LOT-26-00431',
      ]),
    )
  })

  it('leaves planning events out of the quality history', () => {
    const texts = reportTexts(buildInspectionReport(data(), createReportContext('enGB')).body)
    expect(texts.join(' ')).not.toContain('reordered')
  })

  it('warns when the lot is not completed', () => {
    const content = buildInspectionReport(data('in_progress'), createReportContext('deAT'))
    expect(content.notice?.tone).toBe('warn')
    expect(content.notice?.text).toContain('Stand zum Zeitpunkt des Exports')
  })

  it('renders as an archival PDF', async () => {
    const pdf = await renderPdfForTest(
      await composeReport(
        { title: 'Inspection report', printTarget: null, build: (context) => buildInspectionReport(data(), context) },
        BRANDING,
        'enGB',
        {},
      ),
    )
    expect(isPdfA2b(pdf)).toBe(true)
    if (process.env.REPORT_SAMPLE) (await import('node:fs')).writeFileSync(process.env.REPORT_SAMPLE, pdf)
  })
})
