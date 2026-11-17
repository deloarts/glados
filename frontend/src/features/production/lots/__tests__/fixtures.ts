import { makeLotResponse } from '@/test-utils/factories'

import type { LotPositionResponse, LotResponse } from '../../types/productionLotsResponse'
import type { LifecycleAction } from '@/core/utils/lifecycleActions'

// The lot and position shapes the production specs share, built on the
// factories in test-utils. A spec that needs a different baseline (status,
// kind, quantity) keeps its own local variant.

const TERMINAL_LOT_STATUSES = ['completed', 'canceled', 'scrapped']

/**
 * The actions the backend offers a manager of lots on a lot, from the lot
 * intent table: hold from a planned or running lot, resume from a held one,
 * cancel, scrap and structure edits on any lot that is not finished, a
 * quantity edit on a draft lot, force-complete once something was
 * produced, the source decisions while the material source waits for one,
 * and the source switch on any lot that is not finished.
 */
export function lotActions(status: string, produced = 0, sourceApproval = 'not_required'): LifecycleAction[] {
  if (TERMINAL_LOT_STATUSES.includes(status)) return []
  const actions: LifecycleAction[] = []
  if (['partially_planned', 'planned', 'in_progress'].includes(status)) actions.push('hold')
  if (status === 'on_hold') actions.push('resume')
  actions.push('cancel')
  if (produced > 0) actions.push('force_complete')
  actions.push('scrap', 'edit_structure', 'reorder_positions')
  if (status === 'draft') actions.push('edit_quantity')
  if (['pending', 'rejected'].includes(sourceApproval)) actions.push('approve_source')
  if (sourceApproval === 'pending') actions.push('reject_source')
  actions.push('switch_source')
  return actions
}

/**
 * The actions the backend offers on a position, from the lot position intent
 * table, for a lot that is not finished unless `lotTerminal` says so.
 */
export function positionActions(
  position: Pick<
    LotPositionResponse,
    'kind' | 'order_item_status' | 'order_item_closed_short' | 'quantity_remaining'
  >,
  lotTerminal = false,
): LifecycleAction[] {
  const liveLine = position.order_item_status ?? ''
  const closedShort = position.order_item_closed_short ?? false
  const external = position.kind === 'external' || position.kind === 'mixed'
  const remaining = position.quantity_remaining > 0
  const actions: LifecycleAction[] = []
  if (
    !lotTerminal &&
    (!liveLine || closedShort) &&
    (position.kind === 'unassigned' || position.kind === 'internal' || closedShort) &&
    remaining
  ) {
    actions.push('assign_external')
  }
  if (external && (liveLine === 'pending' || liveLine === 'requested')) {
    actions.push('unassign_external')
  }
  if (!lotTerminal && remaining) actions.push('assign_internal')
  if (external) actions.push('record_provision')
  return actions
}

export function makeLot(positions: LotPositionResponse[]): LotResponse {
  return makeLotResponse({
    actions: lotActions('draft'),
    lot_number: 'LOT-1',
    quantity_completed: 0,
    status: 'draft',
    positions,
  })
}

export function makePosition(overrides: Partial<LotPositionResponse> = {}): LotPositionResponse {
  const position: LotPositionResponse = {
    id: 1,
    public_id: '22222222-2222-2222-2222-222222222222',
    created: '2026-07-01',
    changed: null,
    changed_by: null,
    changed_by_id: null,
    sequence: 1,
    kind: 'unassigned',
    status: 'pending',
    quantity: 5,
    quantity_completed: 0,
    quantity_remaining: 5,
    note: null,
    creator_id: 1,
    lot_id: 1,
    steps: [
      {
        id: 1,
        public_id: '11111111-1111-1111-1111-111111111111',
        created: '2026-07-01',
        note: null,
        estimated_setup_minutes: null,
        estimated_minutes_per_piece: null,
        time_budget_per_piece: null,
        sequence: 1,
        creator_id: 1,
        fabrication_method_id: 1,
        role: 'fabrication' as const,
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
      },
    ],
    order_item_id: null,
    order_id: null,
    order_number: '',
    supplier_name: '',
    order_item_status: '',
    order_item_closed_short: false,
    earlier_order_lines: [],
    expected_delivery_date: null,
    production_orders: [],
    actions: [],
    planned_delivery_date: null,
    planned_pickup_date: null,
    ...overrides,
  }
  return { ...position, actions: overrides.actions ?? positionActions(position) }
}
