import { describe, it, expect } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'

import PlanningExceptionsTable from '../PlanningExceptionsTable.vue'
import type { PlanningExceptionResponse } from '../../types/planningExceptionResponse'

const t = i18n.global.t as (key: string, values?: Record<string, unknown>) => string

function row(overrides: Partial<PlanningExceptionResponse>): PlanningExceptionResponse {
  return {
    kind: 'lost_at_receipt',
    family: null,
    demand_id: null,
    lot_id: null,
    lot_number: null,
    order_id: null,
    order_number: null,
    line_position: null,
    item_kind: null,
    item_id: null,
    item_number: '',
    item_revision: '',
    item_name: '',
    item_label: '',
    project_id: null,
    project_number: '',
    project_customer: '',
    quantity_short: null,
    unit: null,
    unallocated: null,
    undated: false,
    target_date: null,
    planned_end: null,
    since: null,
    ...overrides,
  }
}

describe('PlanningExceptionsTable', () => {
  it('names each exception with its kind and what is open', () => {
    const wrapper = mountWithApp(PlanningExceptionsTable, {
      props: {
        rows: [
          row({
            kind: 'lost_at_receipt',
            family: 'bought',
            demand_id: 3,
            order_id: 5,
            order_number: 'B-2026-0005',
            line_position: 2,
            quantity_short: 2,
            unit: 'PCS',
          }),
          row({ kind: 'material_short', lot_id: 7, lot_number: 'L-7', undated: true }),
        ],
      },
    })

    const text = wrapper.text()
    expect(text).toContain(t('productionExceptions.kind.lost_at_receipt'))
    expect(text).toContain('B-2026-0005 pos. 2')
    expect(text).toContain(t('productionExceptions.family.bought', { id: 3 }))
    expect(text).toContain(t('productionExceptions.kind.material_short'))
    expect(text).toContain(t('productionExceptions.detail.material_undated'))
    expect(text).toContain('L-7')
  })

  it('says when nothing needs a decision', () => {
    const wrapper = mountWithApp(PlanningExceptionsTable, { props: { rows: [] } })

    expect(wrapper.text()).toContain(t('productionExceptions.empty'))
  })
})
