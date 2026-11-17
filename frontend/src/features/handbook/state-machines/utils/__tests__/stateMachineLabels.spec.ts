import { describe, it, expect } from 'vitest'

import { i18n } from '@/core/i18n'

import { resolveActionLabel, resolveRowText, resolveStateLabel } from '../stateMachineLabels'

const t = i18n.global.t as (key: string) => string
const te = i18n.global.te as (key: string) => boolean

describe('resolveStateLabel', () => {
  it('resolves every registered machine key to its existing translated prefix', () => {
    expect(resolveStateLabel(t, te, 'production_order_status', 'queued')).toBe(
      t('production.lots.orderStatus.queued'),
    )
    expect(resolveStateLabel(t, te, 'lot_status', 'draft')).toBe(t('production.lots.status.draft'))
    // Not lot_position_status: the backend key is the kind classifier
    // (unassigned/external/internal/mixed), not the derived, never-terminal
    // position status.
    expect(resolveStateLabel(t, te, 'lot_position_kind', 'unassigned')).toBe(
      t('production.lots.positionKind.unassigned'),
    )
    expect(resolveStateLabel(t, te, 'bought_item_demand_status', 'open')).toBe(
      t('boughtItems.demands.status.open'),
    )
    expect(resolveStateLabel(t, te, 'made_item_demand_status', 'allocated')).toBe(
      t('madeItems.demands.status.allocated'),
    )
    expect(resolveStateLabel(t, te, 'source_item_demand_status', 'fulfilled')).toBe(
      t('sourceItems.demands.status.fulfilled'),
    )
  })

  it('falls back to a humanized raw value for an unmapped machine key', () => {
    expect(resolveStateLabel(t, te, 'not_a_registered_machine', 'some_value')).toBe('Some Value')
  })

  it('falls back to a humanized raw value when the prefix exists but the value has no entry', () => {
    expect(resolveStateLabel(t, te, 'lot_position_kind', 'not_a_real_kind')).toBe('Not A Real Kind')
  })
})

describe('resolveStateLabel for the intent and derived machines', () => {
  it('uses the existing status labels of orders, lines, positions, catalogue items and projects', () => {
    expect(resolveStateLabel(t, te, 'order_status', 'draft')).toBe(t('orders.status.draft'))
    expect(resolveStateLabel(t, te, 'order_item_status', 'pending')).toBe(
      t('orders.items.status.pending'),
    )
    expect(resolveStateLabel(t, te, 'lot_position_status', 'ordered_or_queued')).toBe(
      t('production.lots.positionStatus.ordered_or_queued'),
    )
    expect(resolveStateLabel(t, te, 'catalogue_item_status', 'replaced')).toBe(
      t('boughtItems.catalogue.status.replaced'),
    )
    expect(resolveStateLabel(t, te, 'project_status', 'on_hold')).toBe(
      t('resources.projects.status.on_hold'),
    )
  })
})

describe('resolveActionLabel', () => {
  it('translates an action that has a label and humanizes one that has none', () => {
    const translated = te('stateMachines.actions.force_complete')
    expect(resolveActionLabel(t, te, 'force_complete')).toBe(
      translated ? t('stateMachines.actions.force_complete') : 'Force Complete',
    )
    expect(resolveActionLabel(t, te, 'not_an_action')).toBe('Not An Action')
  })
})

describe('resolveRowText', () => {
  it('falls back to the backend text for a key the locale lacks', () => {
    expect(resolveRowText(t, te, 'rows.no_such_table.r1', 'canceled_at set')).toBe(
      'canceled_at set',
    )
  })

  it('reads a key below the stateMachines block when it exists', () => {
    expect(resolveRowText(t, te, 'refresh', 'fallback')).toBe(t('stateMachines.refresh'))
  })
})
