import type { ProductionOrderResponse } from '@/features/production/types/productionOrdersResponse'

/**
 * A complete queued production order for ten pieces of one made item on
 * machine 1, the only position of lot 1. The optional `actions` list is
 * left out, so a spec that renders action buttons passes the actions it
 * needs.
 */
export function makeProductionOrderResponse(
  overrides: Partial<ProductionOrderResponse> = {},
): ProductionOrderResponse {
  // Without completion rows the processed pieces are the accepted ones, so
  // an override of the quantity or the completed count keeps them agreeing.
  const quantity = overrides.quantity ?? 10
  const processed = overrides.quantity_processed ?? overrides.quantity_completed ?? 0
  return {
    edit_version: 0,
    quantity_processed: processed,
    quantity_open: Math.max(quantity - processed, 0),
    id: 1,
    public_id: '33333333-3333-3333-3333-333333333333',
    created: '2026-07-01',
    changed: null,
    changed_by_id: null,
    changed_by: null,
    production_order_number: 'PO-1',
    status: 'queued',
    priority: 'normal',
    pinned: false,
    queue_sequence: 1,
    quantity: 10,
    quantity_completed: 0,
    estimated_duration_minutes: 60,
    note: null,
    planned_start: null,
    planned_end: null,
    not_before: null,
    actual_start: null,
    actual_end: null,
    creator_id: 1,
    creator: null,
    planned_by_id: null,
    planned_by: null,
    machine_id: 1,
    machine_internal_name: 'Machine 1',
    machine_pool_id: null,
    machine_pool_name: '',
    lot_position_id: 1,
    lot_id: 1,
    lot_number: 'LOT-1',
    made_item_part_number: 'PN-1',
    made_item_id: 1,
    made_item_revision: 'A',
    made_item_material: null,
    made_item_mass: null,
    made_item_base_size: null,
    lot_position_sequence: 1,
    lot_position_count: 1,
    waiting_on_raw_material: false,
    can_start: true,
    completions: [],
    conflicts: [],
    assessment: null,
    actions: [],
    canceled_at: null,
    created_lots: [],
    interruptions: [],
    planned_end_at_start: null,
    started_operator: null,
    started_operator_id: null,
    ...overrides,
  }
}
