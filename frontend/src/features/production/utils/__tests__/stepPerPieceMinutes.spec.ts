import { describe, it, expect } from 'vitest'

import { stepPerPieceMinutes } from '../lotStepDisplay'

describe('stepPerPieceMinutes', () => {
  it('prefers the measured estimate over the budget share', () => {
    expect(stepPerPieceMinutes({ estimated_minutes_per_piece: 4, time_budget_per_piece: 9 })).toBe(4)
    expect(stepPerPieceMinutes({ estimated_minutes_per_piece: 0, time_budget_per_piece: 9 })).toBe(0)
  })

  it('falls back to the budget share, then to null', () => {
    expect(stepPerPieceMinutes({ estimated_minutes_per_piece: null, time_budget_per_piece: 9 })).toBe(9)
    expect(
      stepPerPieceMinutes({ estimated_minutes_per_piece: null, time_budget_per_piece: null }),
    ).toBeNull()
  })
})
