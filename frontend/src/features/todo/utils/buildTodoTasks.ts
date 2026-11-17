import { Permission } from '@/core/auth/permissions'
import { DAY_MS, startOfDay, toLocalDayStart, todayStart } from '@/core/utils/dates'
import type { OrderResponse } from '@/features/orders'
import type { BoughtItemDemandResponse } from '@/features/bought-items'
import type { MadeItemDemandResponse } from '@/features/made-items'
import type { SourceItemDemandResponse } from '@/features/source-items'
import type {
  ProductionOrderResponse,
  ScheduleConflict,
} from '@/features/production'
import type { ProjectedSpan } from '@/features/production'
import type { LotSummaryResponse } from '@/features/production'
import type { MeetingTodoSourceResponse } from '../types/todoSourcesResponse'
import type { TodoBucket, TodoCategory, TodoTask, TodoTaskKind } from '../types/todoTask'

// chase_raw_material is a shop floor task because it means production is
// stalled right now, even though resolving it usually means chasing a purchase.
const KIND_CATEGORIES: Record<TodoTaskKind, TodoCategory> = {
  collect_pickup: 'procurement',
  confirm_pickup: 'procurement',
  chase_delivery: 'procurement',
  chase_partial_delivery: 'procurement',
  submit_order: 'procurement',
  order_demand: 'procurement',
  start_production_order: 'shop_floor',
  chase_raw_material: 'shop_floor',
  production_conflict: 'planning',
  plan_lot: 'planning',
  resume_lot: 'planning',
  approve_lot_source: 'planning',
  meeting_todo: 'meetings',
}

const WEEK_AHEAD_DAYS = 7

const TERMINAL_ORDER_ITEM_STATUSES = new Set(['delivered', 'canceled'])

// Only conflicts a person can resolve; the others resolve themselves as the
// schedule advances.
const ACTIONABLE_CONFLICT_PERMISSIONS: Partial<Record<ScheduleConflict, string>> = {
  no_machine_assigned: Permission.WRITE_PRODUCTION_ORDERS,
  capability_mismatch: Permission.WRITE_PRODUCTION_ORDERS,
  uncategorized_step: Permission.WRITE_LOTS,
  missing_time_estimate: Permission.WRITE_LOTS,
  position_not_fully_queued: Permission.WRITE_LOTS,
  past_target_date: Permission.MANAGE_PRODUCTION_ORDERS,
}

// Matches the label SourceItemDemandsTable shows for the same demand.
function sourceDemandLabel(demand: SourceItemDemandResponse): string {
  if (demand.bought_item) return demand.bought_item.article_name
  if (demand.source_item)
    return demand.source_item.dimension || `Source item #${demand.source_item.id}`
  return demand.lot_number
}

function bucketFor(dueDate: Date | null, now: Date): TodoBucket | null {
  if (!dueDate) return 'blockers'
  const today = todayStart(now)
  const due = startOfDay(dueDate)
  if (due.getTime() < today.getTime()) return 'overdue'
  if (due.getTime() === today.getTime()) return 'today'
  if (due.getTime() <= today.getTime() + WEEK_AHEAD_DAYS * DAY_MS) return 'week'
  return null
}

function severityFor(bucket: TodoBucket): string {
  if (bucket === 'overdue') return 'danger'
  if (bucket === 'today') return 'warn'
  if (bucket === 'blockers') return 'help'
  return 'info'
}

export interface BuildTodoTasksParams {
  orders: OrderResponse[]
  boughtDemands: BoughtItemDemandResponse[]
  madeDemands: MadeItemDemandResponse[]
  sourceDemands: SourceItemDemandResponse[]
  productionOrders: ProductionOrderResponse[]
  productionSchedule: Map<number, ProjectedSpan>
  lots: LotSummaryResponse[]
  // The user's own open todos of valid meetings, left out by callers that
  // show no meetings.
  meetingTodos?: MeetingTodoSourceResponse[]
  // Passed in because the revision separator comes from the host store.
  madeItemLabel: (partNumber: string, revision: string) => string
  now?: Date
}

export function buildTodoTasks(params: BuildTodoTasksParams): TodoTask[] {
  const now = params.now ?? new Date()
  const tasks: TodoTask[] = []

  function push(
    task: Omit<TodoTask, 'bucket' | 'severity' | 'important' | 'category'> & {
      bucket?: TodoBucket
      important?: boolean
    },
  ): void {
    const bucket = task.bucket ?? bucketFor(task.dueDate, now)
    if (!bucket) return
    const important =
      task.important ?? (bucket === 'overdue' || bucket === 'today' || task.highPriority)
    tasks.push({
      ...task,
      bucket,
      category: KIND_CATEGORIES[task.kind],
      severity: severityFor(bucket),
      important,
    })
  }

  // ── Procurement ────────────────────────────────────────────────────
  for (const order of params.orders) {
    if (order.status === 'draft' || order.status === 'requested' || order.status === 'partially_ordered') {
      push({
        id: `submit-order-${order.id}`,
        kind: 'submit_order',
        titleKey: 'todo.tasks.submitOrder.title',
        titleParams: { orderNumber: order.order_number },
        subtitleKey: 'todo.tasks.submitOrder.subtitle',
        subtitleParams: { supplier: order.supplier_name },
        dueDate: null,
        route: `/procurement/orders`,
        permission: Permission.WRITE_ORDERS,
        highPriority: false,
      })
    }

    for (const item of order.items ?? []) {
      if (TERMINAL_ORDER_ITEM_STATUSES.has(item.status)) continue

      // The supplier confirmed it is ready to collect.
      if (item.ready_for_pickup_date) {
        push({
          id: `collect-pickup-${item.id}`,
          kind: 'collect_pickup',
          titleKey: 'todo.tasks.collectPickup.title',
          titleParams: { item: item.item_article_name },
          subtitleKey: 'todo.tasks.collectPickup.subtitle',
          subtitleParams: { supplier: item.supplier_name, orderNumber: order.order_number },
          dueDate: toLocalDayStart(item.ready_for_pickup_date),
          route: `/procurement/orders`,
          permission: Permission.WRITE_ORDERS,
          highPriority: false,
        })
        continue
      }

      // Pickup expected but readiness not yet confirmed, so chase the supplier.
      if (item.expected_pickup_date) {
        push({
          id: `confirm-pickup-${item.id}`,
          kind: 'confirm_pickup',
          titleKey: 'todo.tasks.confirmPickup.title',
          titleParams: { item: item.item_article_name },
          subtitleKey: 'todo.tasks.confirmPickup.subtitle',
          subtitleParams: { supplier: item.supplier_name, orderNumber: order.order_number },
          dueDate: toLocalDayStart(item.expected_pickup_date),
          route: `/procurement/orders`,
          permission: Permission.WRITE_ORDERS,
          highPriority: false,
        })
        continue
      }

      // A partial delivery is outstanding regardless of its expected date.
      if (item.quantity_delivered > 0 && item.quantity_delivered < item.quantity) {
        const expected = item.expected_delivery_date
          ? toLocalDayStart(item.expected_delivery_date)
          : null
        // A remainder that is not late yet goes to blockers instead of being
        // dropped for falling outside the one-week window.
        const isLate = !!expected && expected.getTime() < todayStart(now).getTime()
        push({
          id: `chase-partial-delivery-${item.id}`,
          kind: 'chase_partial_delivery',
          titleKey: 'todo.tasks.chasePartialDelivery.title',
          titleParams: { item: item.item_article_name },
          subtitleKey: 'todo.tasks.chasePartialDelivery.subtitle',
          subtitleParams: {
            delivered: item.quantity_delivered,
            quantity: item.quantity,
            supplier: item.supplier_name,
            orderNumber: order.order_number,
          },
          dueDate: isLate ? expected : null,
          bucket: isLate ? undefined : 'blockers',
          route: `/procurement/orders`,
          permission: Permission.WRITE_ORDERS,
          highPriority: false,
        })
        continue
      }

      // A normal delivery that hasn't arrived: only a task once it's late.
      if (item.expected_delivery_date) {
        const due = toLocalDayStart(item.expected_delivery_date)
        if (due.getTime() < todayStart(now).getTime()) {
          push({
            id: `chase-delivery-${item.id}`,
            kind: 'chase_delivery',
            titleKey: 'todo.tasks.chaseDelivery.title',
            titleParams: { item: item.item_article_name },
            subtitleKey: 'todo.tasks.chaseDelivery.subtitle',
            subtitleParams: { supplier: item.supplier_name, orderNumber: order.order_number },
            dueDate: due,
            route: `/procurement/orders`,
            permission: Permission.WRITE_ORDERS,
            highPriority: false,
          })
        }
      }
    }
  }

  // ── Demands awaiting ordering ──────────────────────────────────────
  function pushDemand(
    demand: BoughtItemDemandResponse | MadeItemDemandResponse | SourceItemDemandResponse,
    label: string,
    idPrefix: string,
    route: string,
  ): void {
    if (demand.status !== 'open') return
    push({
      id: `${idPrefix}-${demand.id}`,
      kind: 'order_demand',
      titleKey: 'todo.tasks.orderDemand.title',
      titleParams: { item: label },
      subtitleKey: 'todo.tasks.orderDemand.subtitle',
      subtitleParams: { project: demand.project_number, quantity: demand.quantity },
      dueDate: demand.desired_delivery_date ? toLocalDayStart(demand.desired_delivery_date) : null,
      route,
      permission: Permission.WRITE_DEMAND_ITEMS,
      highPriority: demand.high_priority,
    })
  }

  for (const demand of params.boughtDemands) {
    pushDemand(
      demand,
      demand.item_article_name,
      'order-bought-demand',
      '/procurement/bought-items-demand',
    )
  }
  for (const demand of params.madeDemands) {
    pushDemand(
      demand,
      demand.item_article_name,
      'order-made-demand',
      '/procurement/made-items-demand',
    )
  }
  for (const demand of params.sourceDemands) {
    pushDemand(
      demand,
      sourceDemandLabel(demand),
      'order-source-demand',
      '/procurement/source-items-demand',
    )
  }

  // ── Production ─────────────────────────────────────────────────────
  for (const order of params.productionOrders) {
    if (order.status === 'queued' || order.status === 'paused') {
      const projected = params.productionSchedule.get(order.id)
      if (projected) {
        push({
          id: `start-production-order-${order.id}`,
          kind: 'start_production_order',
          titleKey: 'todo.tasks.startProductionOrder.title',
          titleParams: {
            lotNumber: order.lot_number,
            partNumber: params.madeItemLabel(order.made_item_part_number, order.made_item_revision),
          },
          subtitleKey: 'todo.tasks.startProductionOrder.subtitle',
          subtitleParams: {
            machine: order.machine_internal_name,
            position: order.lot_position_sequence,
            count: order.lot_position_count,
          },
          dueDate: projected.start,
          route: `/production/lots/${order.lot_id}`,
          lotId: order.lot_id,
          permission: Permission.WRITE_PRODUCTION_ORDERS,
          highPriority: order.priority === 'critical' || order.priority === 'high',
        })
      }
    }

    if (order.status === 'completed' || order.status === 'canceled') continue

    // Always surfaced, since it stalls work today whatever the schedule says.
    if (order.waiting_on_raw_material) {
      push({
        id: `chase-raw-material-${order.id}`,
        kind: 'chase_raw_material',
        titleKey: 'todo.tasks.chaseRawMaterial.title',
        titleParams: { lotNumber: order.lot_number },
        subtitleKey: 'todo.tasks.chaseRawMaterial.subtitle',
        subtitleParams: {
          partNumber: params.madeItemLabel(order.made_item_part_number, order.made_item_revision),
          orderNumber: order.production_order_number,
        },
        dueDate: null,
        bucket: 'blockers',
        route: `/production/lots/${order.lot_id}`,
        lotId: order.lot_id,
        permission: Permission.WRITE_PRODUCTION_ORDERS,
        highPriority: false,
        important: true,
      })
    }

    // Conflicts have no date, so they land in blockers.
    for (const conflict of order.conflicts ?? []) {
      const permission = ACTIONABLE_CONFLICT_PERMISSIONS[conflict]
      if (!permission) continue
      push({
        id: `production-conflict-${order.id}-${conflict}`,
        kind: 'production_conflict',
        titleKey: `productionQueue.conflicts.${conflict}`,
        titleParams: {},
        subtitleKey: 'todo.tasks.productionConflict.subtitle',
        subtitleParams: {
          lotNumber: order.lot_number,
          orderNumber: order.production_order_number,
        },
        dueDate: null,
        bucket: 'blockers',
        route: `/production/lots/${order.lot_id}`,
        lotId: order.lot_id,
        permission,
        highPriority: conflict === 'past_target_date',
      })
    }
  }

  // ── Lots needing attention ─────────────────────────────────────────
  for (const lot of params.lots) {
    // No `continue` here: a lot pending source approval can also need planning.
    if (
      lot.source_approval_status === 'pending' &&
      lot.status !== 'completed' &&
      lot.status !== 'canceled'
    ) {
      push({
        id: `approve-lot-source-${lot.id}`,
        kind: 'approve_lot_source',
        titleKey: 'todo.tasks.approveLotSource.title',
        titleParams: { lotNumber: lot.lot_number },
        subtitleKey: 'todo.tasks.approveLotSource.subtitle',
        subtitleParams: {
          partNumber: params.madeItemLabel(lot.made_item_part_number, lot.made_item_revision),
          quantity: lot.quantity,
        },
        dueDate: null,
        bucket: 'blockers',
        route: `/production/lots/${lot.id}`,
        lotId: lot.id,
        permission: Permission.MANAGE_LOTS,
        highPriority: lot.priority === 'critical' || lot.priority === 'high',
        important: true,
      })
    }

    // An on-hold lot stays visible until someone resumes or cancels it.
    if (lot.status === 'on_hold') {
      push({
        id: `resume-lot-${lot.id}`,
        kind: 'resume_lot',
        titleKey: 'todo.tasks.resumeLot.title',
        titleParams: { lotNumber: lot.lot_number },
        subtitleKey: 'todo.tasks.resumeLot.subtitle',
        subtitleParams: {
          partNumber: params.madeItemLabel(lot.made_item_part_number, lot.made_item_revision),
          quantity: lot.quantity,
        },
        dueDate: null,
        bucket: 'blockers',
        route: `/production/lots/${lot.id}`,
        lotId: lot.id,
        permission: Permission.WRITE_LOTS,
        highPriority: lot.priority === 'critical' || lot.priority === 'high',
        important: true,
      })
      continue
    }

    if (lot.status !== 'draft' && lot.status !== 'partially_planned') continue
    push({
      id: `plan-lot-${lot.id}`,
      kind: 'plan_lot',
      titleKey: 'todo.tasks.planLot.title',
      titleParams: { lotNumber: lot.lot_number },
      subtitleKey: 'todo.tasks.planLot.subtitle',
      subtitleParams: {
          partNumber: params.madeItemLabel(lot.made_item_part_number, lot.made_item_revision),
          quantity: lot.quantity,
        },
      dueDate: lot.required_delivery_date ? toLocalDayStart(lot.required_delivery_date) : null,
      route: `/production/lots/${lot.id}`,
      lotId: lot.id,
      permission: Permission.WRITE_LOTS,
      highPriority: lot.priority === 'critical' || lot.priority === 'high',
    })
  }

  // ── Meeting todos ──────────────────────────────────────────────────
  // The server lists only the user's own open todos of valid meetings, so
  // each one is a task without a permission of its own. It is bucketed by
  // its due date like every other task, an undated one waits under
  // blockers, and the route opens the meeting at the todo's card. A meeting
  // todo is assigned to this user by name, so it always counts as
  // important and shows without Show All, unlike the team-wide tasks.
  for (const todo of params.meetingTodos ?? []) {
    const due = todo.due_date ? toLocalDayStart(todo.due_date) : null
    push({
      id: `meeting-todo-${todo.todo_id}`,
      kind: 'meeting_todo',
      titleKey: 'todo.tasks.meetingTodo.title',
      titleParams: { title: todo.title },
      subtitleKey: todo.card_scope ? 'todo.tasks.meetingTodo.subtitle' : 'todo.tasks.meetingTodo.subtitleNoScope',
      subtitleParams: {
        meetingNumber: todo.meeting_number,
        meetingName: todo.meeting_name,
        scope: todo.card_scope ?? '',
      },
      dueDate: due,
      route: `/meetings/${todo.meeting_id}#card-${todo.card_id}`,
      permission: null,
      highPriority: false,
      important: true,
    })
  }

  return tasks
}

const BUCKET_ORDER: Record<TodoBucket, number> = {
  overdue: 0,
  today: 1,
  week: 2,
  blockers: 3,
}

// Most urgent first: bucket, then flagged-priority, then actual due date.
export function sortTodoTasks(tasks: TodoTask[]): TodoTask[] {
  return [...tasks].sort((a, b) => {
    const bucketDiff = BUCKET_ORDER[a.bucket] - BUCKET_ORDER[b.bucket]
    if (bucketDiff !== 0) return bucketDiff
    if (a.highPriority !== b.highPriority) return a.highPriority ? -1 : 1
    const aTime = a.dueDate?.getTime() ?? Number.MAX_SAFE_INTEGER
    const bTime = b.dueDate?.getTime() ?? Number.MAX_SAFE_INTEGER
    return aTime - bTime
  })
}
