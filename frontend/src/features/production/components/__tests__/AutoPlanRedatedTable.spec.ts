import { describe, it, expect } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { i18n } from '@/core/i18n'
import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeTestRouter, RouteStub } from '@/test-utils/factories'
import AutoPlanRedatedTable from '../AutoPlanRedatedTable.vue'

import type { RedatedOrder } from '../../utils/autoPlanRedated'

const t = (key: string) => i18n.global.t(key)

function row(id: number, before: string, after: string): RedatedOrder {
  return {
    order_id: id,
    production_order_number: `PON-${id}`,
    lot_id: id,
    lot_number: `LOT-${id}`,
    made_item_part_number: 'TN-1',
    made_item_revision: '0',
    column: 'inspection',
    machine_id: null,
    machine_pool_id: null,
    before_planned_start: before,
    before_planned_end: before,
    after_planned_start: after,
    after_planned_end: after,
    reason: null,
  }
}

const EARLIER = row(6, '2026-12-11T07:00:00Z', '2026-11-25T11:00:00Z')
const LATER = row(8, '2026-11-26T07:00:00Z', '2026-11-30T07:00:00Z')

async function mountTable(props: Partial<InstanceType<typeof AutoPlanRedatedTable>['$props']> = {}) {
  const router = makeTestRouter([
    { path: '/production/orders/:id(\\d+)', name: 'ProductionOrderDetail', component: RouteStub },
  ])
  await router.push('/')
  const wrapper = mountWithApp(AutoPlanRedatedTable, {
    props: {
      rows: [EARLIER, LATER],
      keptDay: 3,
      walkFailed: false,
      machineNameById: {},
      poolNameById: {},
      ...props,
    },
    global: { plugins: [router] },
  })
  await flushPromises()
  return { wrapper, router }
}

describe('AutoPlanRedatedTable', () => {
  it('lists the re-dated orders and counts the ones that kept their day', async () => {
    const { wrapper } = await mountTable()

    expect(wrapper.text()).toContain('PON-6')
    expect(wrapper.text()).toContain('PON-8')
    expect(wrapper.text()).toContain('Inspection')
    expect(wrapper.text()).toContain('3 other open orders kept their day.')
  })

  it('filters the rows to the orders that moved earlier', async () => {
    const { wrapper } = await mountTable()

    await wrapper.findComponent({ name: 'SelectButton' }).vm.$emit('update:modelValue', 'earlier')
    await flushPromises()

    expect(wrapper.text()).toContain('PON-6')
    expect(wrapper.text()).not.toContain('PON-8')
  })

  it('opens the order on a row click', async () => {
    const { wrapper, router } = await mountTable()

    await wrapper.findComponent({ name: 'DataTable' }).vm.$emit('row-click', { data: LATER })
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('ProductionOrderDetail')
    expect(router.currentRoute.value.params.id).toBe('8')
  })

  it('says so when the walk failed, and when it moved nothing', async () => {
    const failed = await mountTable({ walkFailed: true })
    expect(failed.wrapper.text()).toContain(t('productionSchedule.autoPlan.redated.walkFailed'))
    expect(failed.wrapper.findComponent({ name: 'DataTable' }).exists()).toBe(false)

    const none = await mountTable({ rows: [] })
    expect(none.wrapper.text()).toContain(t('productionSchedule.autoPlan.redated.none'))
  })
})
