import { describe, it, expect } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { Permission } from '@/core/auth/permissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeProductionOrderResponse } from '@/test-utils/factories'

import LotProductionOrderRecord from '../LotProductionOrderRecord.vue'

import type { ProductionOrderCompletionResponse } from '../../../../types/productionOrdersResponse'
import type { LifecycleAction } from '@/core/utils/lifecycleActions'

function completion(
  id: number,
  overrides: Partial<ProductionOrderCompletionResponse> = {},
): ProductionOrderCompletionResponse {
  return {
    id,
    public_id: `00000000-0000-0000-0000-00000000000${id}`,
    production_order_id: 1,
    quantity: 2,
    quantity_accepted: 2,
    quantity_rejected: 0,
    quantity_rework: 0,
    quantity_scrap: 0,
    scrap_reason: null,
    reject_reason: null,
    completion_date: '2026-10-25',
    note: null,
    operator_id: 1,
    operator: null,
    recorded_by_id: 1,
    recorded_by: null,
    created: '2026-10-25T08:00:00Z',
    reverses_completion_id: null,
    machine_id: null,
    ...overrides,
  }
}

function mountRecord(
  completions: ProductionOrderCompletionResponse[],
  permissions: string[],
  actions: LifecycleAction[] = ['pause', 'record_completion', 'reverse_completion'],
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = { is_systemuser: false, permissions } as never
  return mountWithApp(LotProductionOrderRecord, {
    pinia,
    props: {
      row: {
        order: makeProductionOrderResponse({ id: 1, status: 'in_progress', completions, actions }),
        startedBy: null,
        endedBy: null,
        duration: null,
        estimate: '',
        assessment: null,
        comparison: null,
      },
    },
  })
}

function reverseButtons(wrapper: ReturnType<typeof mountRecord>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .filter((b) => b.props('label') === 'Reverse')
}

describe('LotProductionOrderRecord reversal', () => {
  it('offers a reversal for a completion that rejected nothing and emits it', async () => {
    const wrapper = mountRecord([completion(1)], [Permission.MANAGE_PRODUCTION_ORDERS])

    const [button] = reverseButtons(wrapper)
    expect(button!.attributes('disabled')).toBeUndefined()
    await button!.trigger('click')

    const emitted = wrapper.emitted('reverse') as [unknown, ProductionOrderCompletionResponse][]
    expect(emitted.map(([, reversed]) => reversed.id)).toEqual([1])
  })

  it('shows the reversal disabled without the permission', () => {
    const wrapper = mountRecord([completion(1)], [Permission.WRITE_PRODUCTION_ORDERS])

    const buttons = reverseButtons(wrapper)
    expect(buttons).toHaveLength(1)
    expect(buttons[0]!.attributes('disabled')).toBeDefined()
  })

  it('offers no reversal when the order does not offer one, as on a held or finished lot', () => {
    const wrapper = mountRecord([completion(1)], [Permission.MANAGE_PRODUCTION_ORDERS], [])

    expect(reverseButtons(wrapper)).toHaveLength(0)
  })

  it('offers no reversal for a reversed completion, a reversal or one that rejected pieces', () => {
    const wrapper = mountRecord(
      [
        completion(1),
        completion(2, { quantity: -2, quantity_accepted: -2, reverses_completion_id: 1 }),
        completion(3, { quantity_accepted: 1, quantity_rejected: 1 }),
      ],
      [Permission.MANAGE_PRODUCTION_ORDERS],
    )

    expect(reverseButtons(wrapper)).toHaveLength(0)
    expect(wrapper.text()).toContain('Reversal of #1')
    expect(wrapper.text()).toContain('reversed')
  })
})
