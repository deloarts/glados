import { describe, it, expect } from 'vitest'

import {
  poolColumnKey,
  isManualOrder,
  isInspectionOrder,
  isStaticColumn,
  orderColumnKey,
} from '../queueColumnRouting'
import type { RoutingStep } from '../queueColumnRouting'

// ProductionQueueBoard.vue's column-routing logic, a plain module so it can
// be tested without exposing the component's internals.

function step(overrides: Partial<RoutingStep> = {}): RoutingStep {
  return {
    role: 'fabrication',
    fabrication_method_requires_machine: true,
    ...overrides,
  }
}

describe('poolColumnKey', () => {
  it('prefixes the pool id', () => {
    expect(poolColumnKey(7)).toBe('pool-7')
  })
})

describe('isManualOrder', () => {
  it('is false with no steps - defaults to unassigned, not manual', () => {
    expect(isManualOrder([])).toBe(false)
  })

  it('is true when every step is non-machine fabrication', () => {
    expect(isManualOrder([step({ fabrication_method_requires_machine: false })])).toBe(true)
  })

  it('is false when any step requires a machine', () => {
    expect(
      isManualOrder([
        step({ fabrication_method_requires_machine: false }),
        step({ fabrication_method_requires_machine: true }),
      ]),
    ).toBe(false)
  })
})

describe('isInspectionOrder', () => {
  it('is true when any step has role inspection', () => {
    expect(isInspectionOrder([step({ role: 'inspection' })])).toBe(true)
  })

  it('is false when no step is an inspection step', () => {
    expect(isInspectionOrder([step({ role: 'fabrication' })])).toBe(false)
  })

  it('is false with no steps', () => {
    expect(isInspectionOrder([])).toBe(false)
  })
})

describe('isStaticColumn', () => {
  it('is true for manual and inspection', () => {
    expect(isStaticColumn('manual')).toBe(true)
    expect(isStaticColumn('inspection')).toBe(true)
  })

  it('is false for unassigned, machine and pool', () => {
    expect(isStaticColumn('unassigned')).toBe(false)
    expect(isStaticColumn('machine')).toBe(false)
    expect(isStaticColumn('pool')).toBe(false)
  })
})

describe('orderColumnKey (priority: machine > pool > inspection > manual > unassigned)', () => {
  it('a resolved machine wins outright, regardless of pool/step data', () => {
    const key = orderColumnKey(
      { machine_id: 1, machine_pool_id: 7 },
      [step({ role: 'inspection', fabrication_method_requires_machine: false })],
    )
    expect(key).toBe('1')
  })

  it('an unresolved pool assignment routes to the pool column, even over an inspection step', () => {
    const key = orderColumnKey(
      { machine_id: null, machine_pool_id: 7 },
      [step({ role: 'inspection', fabrication_method_requires_machine: false })],
    )
    expect(key).toBe(poolColumnKey(7))
  })

  it('no machine, no pool, an inspection step - the inspection column', () => {
    const key = orderColumnKey(
      { machine_id: null, machine_pool_id: null },
      [step({ role: 'inspection', fabrication_method_requires_machine: false })],
    )
    expect(key).toBe('inspection')
  })

  it('no machine, no pool, every step manual - the manual column', () => {
    const key = orderColumnKey(
      { machine_id: null, machine_pool_id: null },
      [step({ role: 'fabrication', fabrication_method_requires_machine: false })],
    )
    expect(key).toBe('manual')
  })

  it('no machine, no pool, a machine-requiring step - the legacy unassigned fallback', () => {
    const key = orderColumnKey(
      { machine_id: null, machine_pool_id: null },
      [step({ role: 'fabrication', fabrication_method_requires_machine: true })],
    )
    expect(key).toBe('unassigned')
  })

  it('no machine, no pool, no steps at all - unassigned', () => {
    const key = orderColumnKey({ machine_id: null, machine_pool_id: null }, [])
    expect(key).toBe('unassigned')
  })
})
