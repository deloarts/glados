import { describe, it, expect } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'

import AutoPlanRunningView from '../AutoPlanRunningView.vue'
import { useAutoPlanRunStore } from '../../stores/autoPlanRunStore'
import type { AutoPlanProgressOrder } from '../../types/scheduleBoardResponse'

function entry(overrides: Partial<AutoPlanProgressOrder> = {}): AutoPlanProgressOrder {
  return {
    order_id: 1,
    production_order_number: 'PO-1',
    lot_number: 'LOT-1',
    made_item_part_number: 'PN-1',
    placed: false,
    before_machine_id: 5,
    after_machine_id: 5,
    before_machine_pool_id: null,
    after_machine_pool_id: null,
    ...overrides,
  }
}

function mountWithFeed(feed: AutoPlanProgressOrder[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useAutoPlanRunStore().feed.push(...feed)
  return mountWithApp(AutoPlanRunningView, {
    pinia,
    props: { machineNameById: { 5: 'Mill 5' }, poolNameById: {} },
    global: { directives: { tooltip: {} } },
  })
}

describe('AutoPlanRunningView', () => {
  it('names the skip reason of an unplaced order with the label the result uses', () => {
    const wrapper = mountWithFeed([entry({ reason: 'changed_while_planning' })])

    const row = wrapper.find('.feed-row-skipped')
    expect(row.text()).toContain(
      i18n.global.t('productionSchedule.autoPlan.skippedOrders.reasons.changed_while_planning'),
    )
    expect(row.text()).not.toContain(i18n.global.t('productionSchedule.autoPlan.progress.skippedTag'))
  })

  it('keeps the plain skipped tag for a skip without a reason', () => {
    const wrapper = mountWithFeed([entry({ reason: null })])

    expect(wrapper.find('.feed-row-skipped').text()).toContain(
      i18n.global.t('productionSchedule.autoPlan.progress.skippedTag'),
    )
    expect(wrapper.find('.feed-skip-reason').exists()).toBe(false)
  })

  it('shows no skip tag for a placed order', () => {
    const wrapper = mountWithFeed([entry({ placed: true, after_machine_id: 6 })])

    expect(wrapper.find('.feed-row-skipped').exists()).toBe(false)
    expect(wrapper.find('.feed-skip-reason').exists()).toBe(false)
  })
})
