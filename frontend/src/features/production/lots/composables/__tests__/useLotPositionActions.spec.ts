import { describe, it, expect, vi, beforeEach } from 'vitest'
import { computed, defineComponent, h } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'

const deleteMock = vi.fn<(url: string) => Promise<unknown>>(() => Promise.resolve({ data: {} }))

vi.mock('@/core/api', () => ({
  default: {
    delete: (url: string) => deleteMock(url),
  },
}))

import { useLotPositionActions } from '../useLotPositionActions'
import type { LotPositionResponse } from '../../../types/productionLotsResponse'

function makePosition(overrides: Partial<LotPositionResponse> = {}): LotPositionResponse {
  return {
    id: 7,
    public_id: '22222222-2222-2222-2222-222222222222',
    created: '2026-08-01T09:00:00',
    changed: null,
    sequence: 1,
    kind: 'external',
    status: 'pending',
    quantity: 5,
    quantity_completed: 0,
    quantity_remaining: 5,
    note: null,
    creator_id: 1,
    lot_id: 1,
    steps: [],
    order_item_id: null,
    order_id: null,
    order_number: '',
    supplier_name: '',
    order_item_status: 'pending',
    expected_delivery_date: null,
    production_orders: [],
    ...overrides,
  } as LotPositionResponse
}

// Drives the composable inside a tiny host component (same technique
// useLotStructureDraft.spec.ts uses), since useLotPositionActions isn't
// itself a component. `result` is captured out of setup().
function mountActions(lotId = 1) {
  const pinia = createPinia()
  setActivePinia(pinia)

  let result!: ReturnType<typeof useLotPositionActions>
  const wrapper = mountWithApp(
    defineComponent({
      setup() {
        result = useLotPositionActions(computed(() => lotId))
        return () => h('div')
      },
    }),
    { pinia },
  )
  return { wrapper, result }
}

describe('useLotPositionActions', () => {
  beforeEach(() => {
    deleteMock.mockClear()
  })

  it('starts with every dialog closed and no target', () => {
    const { result } = mountActions()

    expect(result.showAssign.value).toBe(false)
    expect(result.assignTarget.value).toBeNull()
    expect(result.showAssignInternal.value).toBe(false)
    expect(result.assignInternalTarget.value).toBeNull()
    expect(result.showProvisions.value).toBe(false)
    expect(result.provisionsTarget.value).toBeNull()
    expect(result.showAppendPosition.value).toBe(false)
  })

  it('openAssign sets the target and shows the assign dialog', () => {
    const { result } = mountActions()
    const position = makePosition()

    result.openAssign(position)

    expect(result.assignTarget.value).toEqual(position)
    expect(result.showAssign.value).toBe(true)
    // The other two dialogs are untouched.
    expect(result.showAssignInternal.value).toBe(false)
    expect(result.showProvisions.value).toBe(false)
  })

  it('openAssignInternal and openProvisions each track their own target independently', () => {
    const { result } = mountActions()
    const internalTarget = makePosition({ id: 8, kind: 'unassigned' })
    const provisionTarget = makePosition({ id: 9 })

    result.openAssignInternal(internalTarget)
    result.openProvisions(provisionTarget)

    expect(result.assignInternalTarget.value).toEqual(internalTarget)
    expect(result.showAssignInternal.value).toBe(true)
    expect(result.provisionsTarget.value).toEqual(provisionTarget)
    expect(result.showProvisions.value).toBe(true)
  })

  it('openAppendPosition shows the append dialog', () => {
    const { result } = mountActions()

    result.openAppendPosition()

    expect(result.showAppendPosition.value).toBe(true)
  })

  it('unassign calls the unassign endpoint for the given lot and position', async () => {
    const { result } = mountActions(42)

    await result.unassign(makePosition({ id: 7 }))

    expect(deleteMock).toHaveBeenCalledWith('/production-lots/42/positions/7/assign')
  })

  it('unassign reads lotId fresh, following a reactive change rather than freezing it', async () => {
    let lotId = 1
    const pinia = createPinia()
    setActivePinia(pinia)
    let result!: ReturnType<typeof useLotPositionActions>
    mountWithApp(
      defineComponent({
        setup() {
          result = useLotPositionActions(computed(() => lotId))
          return () => h('div')
        },
      }),
      { pinia },
    )

    lotId = 99
    await result.unassign(makePosition({ id: 3 }))

    expect(deleteMock).toHaveBeenCalledWith('/production-lots/99/positions/3/assign')
  })
})
