import { describe, it, expect } from 'vitest'

import {
  buildLotFilterParams,
  decodeStepMethod,
  encodeStepMethod,
  type LotFilterContext,
  type LotFilterFieldValues,
} from '../lotFilterParams'

// The params builder ProductionLotsListView.vue uses. Every store field maps
// to exactly one wire param
// (or pair), empty fields are absent rather than undefined keys, and the
// two exclusive families (coverage, step method) never send both sides.

function fields(overrides: Partial<LotFilterFieldValues> = {}): LotFilterFieldValues {
  return {
    search: '',
    projectNumber: '',
    itemArticleName: '',
    itemPartNumber: '',
    statusFilter: null,
    priorityFilter: null,
    creatorFilter: null,
    createdFrom: null,
    createdTo: null,
    changedByFilter: null,
    changedFrom: null,
    changedTo: null,
    needsAssignmentOnly: false,
    needsApprovalOnly: false,
    lotNumber: '',
    targetDateFrom: null,
    targetDateTo: null,
    quantityMin: null,
    quantityMax: null,
    sourceText: '',
    sourceDimension: '',
    sourceType: '',
    sourceStatus: null,
    sourceDeliveryFrom: null,
    sourceDeliveryTo: null,
    stepMethod: null,
    stepStatus: null,
    stepSetupMin: null,
    stepSetupMax: null,
    stepPerPieceMin: null,
    stepPerPieceMax: null,
    stepPlannedStartFrom: null,
    stepPlannedStartTo: null,
    stepPlannedEndFrom: null,
    stepPlannedEndTo: null,
    stepDeliveryFrom: null,
    stepDeliveryTo: null,
    stepNote: '',
    ...overrides,
  }
}

function ctx(overrides: Partial<LotFilterContext> = {}): LotFilterContext {
  return {
    smartFilterEnabled: true,
    showManageOrders: false,
    showManageProduction: false,
    showManageSource: false,
    coverageFilterArmed: false,
    selectedMachineId: null,
    selectedPoolId: null,
    ...overrides,
  }
}

const from = new Date(2026, 0, 15)
const to = new Date(2026, 1, 3)

describe('buildLotFilterParams', () => {
  it('sends nothing at all when every field is at its default', () => {
    const params = buildLotFilterParams(fields(), ctx())

    expect(params).toEqual({})
    expect(Object.keys(params)).toHaveLength(0)
  })

  it('maps the text filters one to one', () => {
    expect(
      buildLotFilterParams(
        fields({
          search: 'FN',
          projectNumber: 'P-1',
          itemArticleName: 'Bracket',
          lotNumber: 'LOT-7',
          sourceText: 'S355',
          stepNote: 'deburr',
        }),
        ctx(),
      ),
    ).toEqual({
      search: 'FN',
      project_number: 'P-1',
      item_article_name: 'Bracket',
      lot_number: 'LOT-7',
      source_text: 'S355',
      step_note: 'deburr',
    })
  })

  it('maps the split item and source fields of the combined filters', () => {
    expect(
      buildLotFilterParams(
        fields({ itemPartNumber: 'PN-12', sourceDimension: '40 x 8', sourceType: 'Flat bar' }),
        ctx(),
      ),
    ).toEqual({ item_part_number: 'PN-12', source_dimension: '40 x 8', source_type: 'Flat bar' })
  })

  it('maps the pickers one to one', () => {
    expect(
      buildLotFilterParams(
        fields({
          statusFilter: 'planned',
          priorityFilter: 'high',
          creatorFilter: 7,
          changedByFilter: 9,
          sourceStatus: 'ordered',
          stepStatus: 'queued',
        }),
        ctx(),
      ),
    ).toEqual({
      status: 'planned',
      priority: 'high',
      creator_id: 7,
      changed_by_id: 9,
      source_status: 'ordered',
      step_status: 'queued',
    })
  })

  it('serializes every date range as local YYYY-MM-DD bounds', () => {
    expect(
      buildLotFilterParams(
        fields({
          createdFrom: from,
          createdTo: to,
          changedFrom: from,
          changedTo: to,
          targetDateFrom: from,
          targetDateTo: to,
          sourceDeliveryFrom: from,
          sourceDeliveryTo: to,
          stepPlannedStartFrom: from,
          stepPlannedStartTo: to,
          stepPlannedEndFrom: from,
          stepPlannedEndTo: to,
          stepDeliveryFrom: from,
          stepDeliveryTo: to,
        }),
        ctx(),
      ),
    ).toEqual({
      created_from: '2026-01-15',
      created_to: '2026-02-03',
      changed_from: '2026-01-15',
      changed_to: '2026-02-03',
      target_date_from: '2026-01-15',
      target_date_to: '2026-02-03',
      source_delivery_from: '2026-01-15',
      source_delivery_to: '2026-02-03',
      step_planned_start_from: '2026-01-15',
      step_planned_start_to: '2026-02-03',
      step_planned_end_from: '2026-01-15',
      step_planned_end_to: '2026-02-03',
      step_delivery_from: '2026-01-15',
      step_delivery_to: '2026-02-03',
    })
  })

  it('sends a lone range end on its own', () => {
    expect(buildLotFilterParams(fields({ targetDateTo: to }), ctx())).toEqual({
      target_date_to: '2026-02-03',
    })
  })

  it('maps the numeric ranges and keeps an explicit zero', () => {
    expect(
      buildLotFilterParams(
        fields({
          quantityMin: 0,
          quantityMax: 50,
          stepSetupMin: 10,
          stepSetupMax: 30,
          stepPerPieceMin: 0.5,
          stepPerPieceMax: 2,
        }),
        ctx(),
      ),
    ).toEqual({
      quantity_min: 0,
      quantity_max: 50,
      step_setup_min: 10,
      step_setup_max: 30,
      step_per_piece_min: 0.5,
      step_per_piece_max: 2,
    })
  })

  it('lets needsAssignmentOnly replace the single-status filter with the statuses list', () => {
    expect(
      buildLotFilterParams(fields({ needsAssignmentOnly: true, statusFilter: 'planned' }), ctx()),
    ).toEqual({ statuses: ['draft', 'partially_planned'] })
  })

  it('sends needsApprovalOnly as the pending source approval status', () => {
    expect(buildLotFilterParams(fields({ needsApprovalOnly: true }), ctx())).toEqual({
      source_approval_status: 'pending',
    })
  })

  describe('step method', () => {
    it('decodes a fabrication method into its own param only', () => {
      const params = buildLotFilterParams(fields({ stepMethod: 'fabrication:3' }), ctx())

      expect(params).toEqual({ step_fabrication_method_id: 3 })
      expect('step_inspection_method_id' in params).toBe(false)
    })

    it('decodes an inspection method into its own param only', () => {
      expect(buildLotFilterParams(fields({ stepMethod: 'inspection:4' }), ctx())).toEqual({
        step_inspection_method_id: 4,
      })
    })

    it('ignores an unknown or malformed encoding', () => {
      expect(decodeStepMethod('machine:3')).toEqual({})
      expect(decodeStepMethod('fabrication:abc')).toEqual({})
      expect(decodeStepMethod('fabrication:0')).toEqual({})
      expect(decodeStepMethod('')).toEqual({})
      expect(decodeStepMethod(null)).toEqual({})
    })

    it('round-trips through encodeStepMethod', () => {
      expect(decodeStepMethod(encodeStepMethod('fabrication', 12))).toEqual({
        step_fabrication_method_id: 12,
      })
      expect(decodeStepMethod(encodeStepMethod('inspection', 5))).toEqual({
        step_inspection_method_id: 5,
      })
    })
  })

  describe('smart filter', () => {
    it.each([
      ['showManageOrders', 'orders'],
      ['showManageProduction', 'machines'],
      ['showManageSource', 'source'],
    ] as const)('sends actionable_for for the open %s panel', (flag, expected) => {
      expect(buildLotFilterParams(fields(), ctx({ [flag]: true }))).toEqual({
        actionable_for: expected,
      })
    })

    it('sends no actionable_for while the smart filter is switched off', () => {
      expect(
        buildLotFilterParams(fields(), ctx({ showManageOrders: true, smartFilterEnabled: false })),
      ).toEqual({})
    })

    it('narrows to the selected machine when the coverage filter is armed', () => {
      expect(
        buildLotFilterParams(
          fields(),
          ctx({ showManageProduction: true, coverageFilterArmed: true, selectedMachineId: 9 }),
        ),
      ).toEqual({ actionable_for: 'machines', coverable_by_machine_id: 9 })
    })

    it('prefers the machine over the pool and falls back to any pool', () => {
      expect(
        buildLotFilterParams(
          fields(),
          ctx({ coverageFilterArmed: true, selectedMachineId: 9, selectedPoolId: 2 }),
        ),
      ).toEqual({ coverable_by_machine_id: 9 })
      expect(
        buildLotFilterParams(fields(), ctx({ coverageFilterArmed: true, selectedPoolId: 2 })),
      ).toEqual({ coverable_by_pool_id: 2 })
      expect(buildLotFilterParams(fields(), ctx({ coverageFilterArmed: true }))).toEqual({
        coverable_by_any_pool: true,
      })
    })

    it('sends no coverage param when disarmed or when the smart filter is off', () => {
      expect(buildLotFilterParams(fields(), ctx({ selectedMachineId: 9 }))).toEqual({})
      expect(
        buildLotFilterParams(
          fields(),
          ctx({ coverageFilterArmed: true, selectedMachineId: 9, smartFilterEnabled: false }),
        ),
      ).toEqual({})
    })
  })
})
