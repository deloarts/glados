import { describe, it, expect } from 'vitest'

import { buildTimeComparison, effectivePerPieceMinutes } from '../timeComparison'

import type { FabricationLotStep, LotStepResponse } from '../../../types/productionLotsResponse'
import type { ManufacturingAssessmentResponse } from '../../../types/productionOrdersResponse'

function makeStep(overrides: Partial<FabricationLotStep> = {}): LotStepResponse {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-07-01',
    note: null,
    estimated_setup_minutes: 10,
    estimated_minutes_per_piece: 2,
    time_budget_per_piece: null,
    sequence: 1,
    creator_id: 1,
    fabrication_method_id: 1,
    role: 'fabrication',
    inspection_method_id: null,
    inspection_method_name: null,
    inspection_method_requires_evidence: null,
    fabrication_method_name: { enGB: 'Milling' },
    fabrication_method_requires_machine: true,
    fabrication_method_required_external: false,
    fabrication_method_default_supplier_id: null,
    lot_id: 1,
    position_id: 1,
    source_process_id: null,
    ...overrides,
  }
}

function makeAssessment(
  overrides: Partial<ManufacturingAssessmentResponse> = {},
): ManufacturingAssessmentResponse {
  return {
    id: 1,
    public_id: '66666666-6666-6666-6666-666666666666',
    production_order_id: 1,
    operator_id: 2,
    operator: null,
    actual_minutes_per_piece: 3,
    actual_setup_minutes: 15,
    complexity: 'normal',
    note: null,
    created: '2026-07-11',
    ...overrides,
  }
}

describe('effectivePerPieceMinutes', () => {
  it('prefers the measured estimate over the budget fallback', () => {
    expect(
      effectivePerPieceMinutes(
        makeStep({ estimated_minutes_per_piece: 2, time_budget_per_piece: 9 }),
      ),
    ).toBe(2)
  })

  it('falls back to the project time budget when nothing is measured', () => {
    expect(
      effectivePerPieceMinutes(
        makeStep({ estimated_minutes_per_piece: null, time_budget_per_piece: 9 }),
      ),
    ).toBe(9)
  })

  it('is 0 when neither exists, matching the backend', () => {
    expect(
      effectivePerPieceMinutes(
        makeStep({ estimated_minutes_per_piece: null, time_budget_per_piece: null }),
      ),
    ).toBe(0)
  })
})

describe('buildTimeComparison', () => {
  it('returns null when the order has no assessment', () => {
    expect(
      buildTimeComparison({
        steps: [makeStep()],
        orderQuantity: 5,
        estimatedDurationMinutes: 20,
        assessment: null,
      }),
    ).toBeNull()
  })

  it('compares setup, per piece and total with minute and percent diffs', () => {
    const rows = buildTimeComparison({
      steps: [makeStep({ estimated_setup_minutes: 10, estimated_minutes_per_piece: 2 })],
      orderQuantity: 5,
      // 10 setup + 5 x 2 = 20
      estimatedDurationMinutes: 20,
      assessment: makeAssessment({ actual_setup_minutes: 15, actual_minutes_per_piece: 3 }),
    })

    expect(rows).not.toBeNull()
    const [setup, perPiece, total] = rows!

    expect(setup).toMatchObject({ estimated: 10, actual: 15, diffMinutes: 5, diffPercent: 50 })
    expect(perPiece).toMatchObject({ estimated: 2, actual: 3, diffMinutes: 1, diffPercent: 50 })
    // 15 setup + 5 x 3 = 30, against a 20 estimate
    expect(total).toMatchObject({ estimated: 20, actual: 30, diffMinutes: 10, diffPercent: 50 })
  })

  it('sums estimates across every step of a multi-step position', () => {
    const rows = buildTimeComparison({
      steps: [
        makeStep({ id: 1, estimated_setup_minutes: 10, estimated_minutes_per_piece: 2 }),
        makeStep({ id: 2, estimated_setup_minutes: 5, estimated_minutes_per_piece: 1 }),
      ],
      orderQuantity: 4,
      estimatedDurationMinutes: 27,
      assessment: makeAssessment(),
    })!

    expect(rows[0]!.estimated).toBe(15)
    expect(rows[1]!.estimated).toBe(3)
  })

  it('reports a negative diff when the job beat its estimate', () => {
    const rows = buildTimeComparison({
      steps: [makeStep({ estimated_setup_minutes: 20, estimated_minutes_per_piece: 4 })],
      orderQuantity: 2,
      estimatedDurationMinutes: 28,
      assessment: makeAssessment({ actual_setup_minutes: 10, actual_minutes_per_piece: 2 }),
    })!

    expect(rows[0]!.diffMinutes).toBe(-10)
    expect(rows[0]!.diffPercent).toBe(-50)
    // 10 + 2 x 2 = 14 against 28
    expect(rows[2]!).toMatchObject({ actual: 14, diffMinutes: -14, diffPercent: -50 })
  })

  it('leaves the setup row uncomparable when no actual setup was recorded', () => {
    const rows = buildTimeComparison({
      steps: [makeStep({ estimated_setup_minutes: 10 })],
      orderQuantity: 5,
      estimatedDurationMinutes: 20,
      assessment: makeAssessment({ actual_setup_minutes: null }),
    })!

    expect(rows[0]).toMatchObject({
      estimated: 10,
      actual: null,
      diffMinutes: null,
      diffPercent: null,
    })
    // ...but the total still counts the missing setup as zero, as the
    // backend's own arithmetic does.
    expect(rows[2]!.actual).toBe(15)
  })

  it('withholds the percentage when the estimate is zero rather than dividing by it', () => {
    const rows = buildTimeComparison({
      steps: [makeStep({ estimated_setup_minutes: 0, estimated_minutes_per_piece: 0 })],
      orderQuantity: 5,
      estimatedDurationMinutes: 0,
      assessment: makeAssessment({ actual_setup_minutes: 5, actual_minutes_per_piece: 1 }),
    })!

    expect(rows[0]).toMatchObject({ diffMinutes: 5, diffPercent: null })
    expect(rows[2]).toMatchObject({ diffMinutes: 10, diffPercent: null })
  })
})
