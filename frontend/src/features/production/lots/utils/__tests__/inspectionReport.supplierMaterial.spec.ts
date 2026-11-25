import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { createReportContext } from '@/shared/reports'
import { reportTexts } from '@/test-utils/reportTexts'
import { buildInspectionReport } from '../inspectionReport'
import type { InspectionReportData } from '../inspectionReportData'

// The smallest data the report builds from: a lot with no inspections, which
// is enough to read its material approval line.
function data(status: string): InspectionReportData {
  return {
    lot: {
      id: 1,
      public_id: '6f1d2c4e-8a3b-4c51-9e27-0b5d8f4a1c63',
      lot_number: 'LOT-26-00001',
      status: 'completed',
      created: '2026-09-29T08:15:00Z',
      creator: null,
      completed_at: '2026-10-16T12:32:00Z',
      quantity: 5,
      quantity_completed: 5,
      quantity_scrapped: 0,
      source_approval_status: status,
      positions: [],
    },
    madeItem: null,
    madeItemFiles: [],
    partImage: null,
    productionOrders: [],
    filesByOrder: new Map(),
    ordersById: new Map(),
    provisionsByPosition: new Map(),
    methods: new Map(),
    events: [],
  } as unknown as InspectionReportData
}

describe('inspection report material approval', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('says why a lot awaiting its first step needed no approval', () => {
    const texts = reportTexts(
      buildInspectionReport(data('awaiting_first_step'), createReportContext('enGB')).body,
    )

    expect(texts).toContain('Not required, the first step is expected at a supplier')
  })

  it('says the supplier of the first step brought the material', () => {
    const texts = reportTexts(
      buildInspectionReport(data('supplier_sourced'), createReportContext('enGB')).body,
    )

    expect(texts).toContain('Not required, the supplier of the first step brings the material')
  })
})
