export type TodoTaskKind =
  | 'collect_pickup'
  | 'confirm_pickup'
  | 'chase_delivery'
  | 'chase_partial_delivery'
  | 'submit_order'
  | 'order_demand'
  | 'start_production_order'
  | 'production_conflict'
  | 'chase_raw_material'
  | 'plan_lot'
  | 'resume_lot'
  | 'approve_lot_source'
  | 'meeting_todo'

// `blockers` holds undated tasks, such as conflicts and draft orders.
export type TodoBucket = 'overdue' | 'today' | 'week' | 'blockers'

// Grouped by who does the work, not by which entity the task belongs to.
export type TodoCategory = 'procurement' | 'shop_floor' | 'planning' | 'meetings'

export const TODO_CATEGORIES: TodoCategory[] = ['procurement', 'shop_floor', 'planning', 'meetings']

export interface TodoTask {
  // Stable across rebuilds.
  id: string
  kind: TodoTaskKind
  category: TodoCategory
  bucket: TodoBucket
  // Translation keys keep the builder independent of i18n.
  titleKey: string
  titleParams: Record<string, string | number>
  subtitleKey: string
  subtitleParams: Record<string, string | number>
  dueDate: Date | null
  route: string
  // Takes priority over `route`, since a lot only opens as a dialog.
  lotId?: number
  // Tasks the user lacks this permission for are hidden; null for a task
  // that is the user's own, such as a meeting todo assigned to them.
  permission: string | null
  severity: string
  highPriority: boolean
  // Listed while "Show all" is off: due now, high priority, or blocking work.
  important: boolean
}
