import type { ILink, ITask } from '@svar-ui/vue-gantt'
import { DAY_MS, toLocalDayStart, todayStart } from '@/core/utils/dates'
import { stepMethodLabel } from './lotStepDisplay'
import { runningSince } from './runningSince'
import type { ProductionOrderResponse } from '../types/productionOrdersResponse'
import type { LotPositionResponse, LotResponse } from '../types/productionLotsResponse'
import { sortedBySequence } from './sequence'

// Only for the client-side estimate of an order the backend has not
// scheduled yet. Durations round up to whole days of this many minutes.
const ONE_DAY_MINUTES = 8 * 60

const ACTIVE_STATUSES = new Set<ProductionOrderResponse['status']>([
  'queued',
  'in_progress',
  'paused',
])

export function isActiveProductionOrder(order: ProductionOrderResponse): boolean {
  return ACTIVE_STATUSES.has(order.status)
}

// Task id scheme the planning view's drag handlers rely on.
export const MACHINE_TASK_ID_PREFIX = 'machine-'
export const UNASSIGNED_MACHINE_KEY = 'unassigned'
export const ORDER_TASK_ID_PREFIX = 'production-order-'
export const EXTERNAL_TASK_ID_PREFIX = 'external-position-'
export const EXTERNAL_GROUP_TASK_ID = 'external-steps'

export function machineTaskId(machineId: number | null): string {
  return `${MACHINE_TASK_ID_PREFIX}${machineId ?? UNASSIGNED_MACHINE_KEY}`
}

function orderTaskId(order: ProductionOrderResponse): string {
  return `${ORDER_TASK_ID_PREFIX}${order.id}`
}

function externalTaskId(position: LotPositionResponse): string {
  return `${EXTERNAL_TASK_ID_PREFIX}${position.id}`
}

function durationDaysFor(order: ProductionOrderResponse): number {
  const minutes =
    order.estimated_duration_minutes > 0 ? order.estimated_duration_minutes : ONE_DAY_MINUTES
  return Math.max(1, Math.ceil(minutes / ONE_DAY_MINUTES))
}

export interface ProjectedSpan {
  start: Date
  end: Date
}

interface OrderPlanningNode {
  kind: 'order'
  id: string
  order: ProductionOrderResponse
}

interface ExternalPlanningNode {
  kind: 'external'
  id: string
  position: LotPositionResponse
}

type PlanningNode = OrderPlanningNode | ExternalPlanningNode

export interface ProductionScheduleParams {
  machines: { id: number; internal_name: string }[]
  // Only queued, in-progress and paused orders carry a forward schedule.
  orders: ProductionOrderResponse[]
  // Lots referenced by an active order; only positions are read.
  lots: LotResponse[]
  // External position id to its order item's ordered_date. Without one the
  // step renders as a point at its delivery date.
  orderedDateByPositionId: Map<number, string | null>
  now?: Date
}

// The dependency graph and schedule shared by the gantt and the kanban.
// A queued order follows the previous order on its machine and its lot
// predecessor. External steps are nodes with fixed dates, positions without
// an order are skipped, and pinned and running orders are anchors.
function buildScheduleGraph(params: ProductionScheduleParams) {
  const { machines, orders, lots, orderedDateByPositionId } = params
  const now = todayStart(params.now)

  const activeOrders = orders.filter(isActiveProductionOrder)

  const positionById = new Map<number, LotPositionResponse>()
  for (const lot of lots) {
    for (const position of lot.positions ?? []) {
      positionById.set(position.id, position)
    }
  }

  const nodesById = new Map<string, PlanningNode>()
  const machinePredecessor = new Map<string, string>()
  const lotPredecessors = new Map<string, string[]>()
  const visualLinks = new Map<string, { source: string; target: string }>()

  for (const order of activeOrders) {
    const id = orderTaskId(order)
    nodesById.set(id, { kind: 'order', id, order })
  }

  const ordersByPosition = new Map<number, ProductionOrderResponse[]>()
  for (const order of activeOrders) {
    const list = ordersByPosition.get(order.lot_position_id)
    if (list) list.push(order)
    else ordersByPosition.set(order.lot_position_id, [order])
  }

  for (const lot of lots) {
    const sortedPositions = sortedBySequence(lot.positions)

    const nodeGroups: PlanningNode[][] = []
    for (const position of sortedPositions) {
      if (position.kind === 'external') {
        // Shown even without a delivery date so the chain stays connected.
        const id = externalTaskId(position)
        const node: PlanningNode = { kind: 'external', id, position }
        nodesById.set(id, node)
        nodeGroups.push([node])
        continue
      }

      const positionOrders = ordersByPosition.get(position.id) ?? []
      if (positionOrders.length === 0) continue
      nodeGroups.push(
        positionOrders
          .map((order) => nodesById.get(orderTaskId(order)))
          .filter((n): n is PlanningNode => !!n),
      )
    }

    for (let i = 1; i < nodeGroups.length; i++) {
      const predecessors = nodeGroups[i - 1]
      const successors = nodeGroups[i]
      if (!predecessors || !successors) continue

      for (const successor of successors) {
        const list = lotPredecessors.get(successor.id) ?? []
        for (const predecessor of predecessors) {
          list.push(predecessor.id)
          const linkId = `production-planning-link-${predecessor.id}-${successor.id}`
          visualLinks.set(linkId, { source: predecessor.id, target: successor.id })
        }
        lotPredecessors.set(successor.id, list)
      }
    }
  }

  // Only real machines; the unassigned bucket has no capacity to pack against.
  for (const machine of machines) {
    const machineOrders = activeOrders
      .filter((order) => order.machine_id === machine.id)
      .sort((a, b) => a.queue_sequence - b.queue_sequence)
    for (let i = 1; i < machineOrders.length; i++) {
      const current = machineOrders[i]
      const previous = machineOrders[i - 1]
      if (!current || !previous) continue
      machinePredecessor.set(orderTaskId(current), orderTaskId(previous))
    }
  }

  const spanCache = new Map<string, ProjectedSpan>()
  const resolving = new Set<string>()

  function computeSpan(nodeId: string): ProjectedSpan {
    const cached = spanCache.get(nodeId)
    if (cached) return cached

    const node = nodesById.get(nodeId)
    if (!node || resolving.has(nodeId)) {
      // Missing id or a cycle in malformed data; fall back to now.
      const span = { start: now, end: now }
      spanCache.set(nodeId, span)
      return span
    }
    resolving.add(nodeId)

    const lotPredIds = lotPredecessors.get(nodeId) ?? []
    const lotPredEnd =
      lotPredIds.length > 0
        ? new Date(Math.max(...lotPredIds.map((id) => computeSpan(id).end.getTime())))
        : null

    let span: ProjectedSpan
    if (node.kind === 'external') {
      if (node.position.expected_delivery_date) {
        const end = toLocalDayStart(node.position.expected_delivery_date)
        const orderedDateRaw = orderedDateByPositionId.get(node.position.id)
        // Both endpoints collapse to the start of their local day so the instant
        // and the calendar date stay comparable.
        const orderedDate = orderedDateRaw ? toLocalDayStart(orderedDateRaw) : null
        // Spans from ordering to expected delivery; a later ordered date is clamped.
        const start = orderedDate && orderedDate.getTime() <= end.getTime() ? orderedDate : end
        span = { start, end }
      } else {
        // Without a delivery date it sits at its earliest possible point.
        const start = lotPredEnd && lotPredEnd > now ? lotPredEnd : now
        span = { start, end: start }
      }
    } else {
      const order = node.order
      const durationMs = durationDaysFor(order) * DAY_MS
      // A started order runs from its latest start or resume, like the backend walk.
      const runningStart = order.status === 'queued' ? null : runningSince(order)

      if (runningStart) {
        const start = toLocalDayStart(runningStart.toISOString())
        const estimatedEnd = new Date(start.getTime() + durationMs)
        // The walk stretches the planned end of an order that overruns.
        const plannedEnd = order.planned_end ? toLocalDayStart(order.planned_end) : null
        span = { start, end: plannedEnd && plannedEnd > estimatedEnd ? plannedEnd : estimatedEnd }
      } else if (order.planned_start) {
        // The backend's schedule is authoritative whenever it exists.
        const start = toLocalDayStart(order.planned_start)
        const end = order.planned_end
          ? toLocalDayStart(order.planned_end)
          : new Date(start.getTime() + durationMs)
        span = { start, end: end > start ? end : new Date(start.getTime() + durationMs) }
      } else {
        // A client-side guess until the backend schedules the order.
        const machinePredId = machinePredecessor.get(nodeId)
        const machinePredEnd = machinePredId ? computeSpan(machinePredId).end : null

        const notBefore = order.not_before ? toLocalDayStart(order.not_before) : null

        const candidates = [now, notBefore, machinePredEnd, lotPredEnd].filter(
          (d): d is Date => d !== null,
        )
        const start = new Date(Math.max(...candidates.map((d) => d.getTime())))
        span = { start, end: new Date(start.getTime() + durationMs) }
      }
    }

    resolving.delete(nodeId)
    spanCache.set(nodeId, span)
    return span
  }

  function fabricationMethodLabel(positionId: number): string {
    const position = positionById.get(positionId)
    if (!position) return ''
    return [...new Set((position.steps ?? []).map((step) => stepMethodLabel(step)))].join(', ')
  }

  return { now, activeOrders, nodesById, visualLinks, computeSpan, fabricationMethodLabel }
}

// The projected schedule alone, used by the kanban to bucket orders.
export function computeProductionSchedule(
  params: ProductionScheduleParams,
): Map<number, ProjectedSpan> {
  const { nodesById, computeSpan } = buildScheduleGraph(params)
  const spanByOrderId = new Map<number, ProjectedSpan>()
  for (const node of nodesById.values()) {
    if (node.kind === 'order') {
      spanByOrderId.set(node.order.id, computeSpan(node.id))
    }
  }
  return spanByOrderId
}

export interface BuildProductionPlanningParams extends ProductionScheduleParams {
  machines: { id: number; internal_name: string; fabricationMethods: string[] }[]
  noAssignmentLabel: string
  externalLabel: string
  dateUnknownSuffix: string
  // Translates a conflict code for the bar tooltip; defaults to the raw code.
  conflictLabel?: (conflict: string) => string
  madeItemLabel: (partNumber: string, revision: string) => string
}

export interface BuildProductionPlanningResult {
  tasks: ITask[]
  links: ILink[]
}

// Builds the planning gantt rows (grouped by machine, plus unassigned and
// external groups) and the finish-to-start links from one schedule graph.
export function buildProductionPlanning(
  params: BuildProductionPlanningParams,
): BuildProductionPlanningResult {
  const { machines, noAssignmentLabel, externalLabel, dateUnknownSuffix } = params
  const conflictLabel = params.conflictLabel ?? ((conflict: string) => conflict)
  const { now, activeOrders, nodesById, visualLinks, computeSpan, fabricationMethodLabel } =
    buildScheduleGraph(params)

  const tasks: ITask[] = []

  function withMethodSuffix(label: string, method: string): string {
    return method ? `${label} (${method})` : label
  }

  // Machines and the unassigned group keep an empty row so there is a drop
  // target. The external group is never a drop target, so it hides when empty.
  function pushGroup(groupId: string, label: string, nodeIds: string[], forceShow = false): void {
    if (nodeIds.length === 0 && !forceShow) return

    const entries = nodeIds.map((id) => ({ id, span: computeSpan(id) }))
    const groupStart =
      entries.length > 0 ? new Date(Math.min(...entries.map((e) => e.span.start.getTime()))) : now
    const groupEnd =
      entries.length > 0 ? new Date(Math.max(...entries.map((e) => e.span.end.getTime()))) : now

    tasks.push({
      id: groupId,
      text: label,
      start: groupStart,
      end: groupEnd,
      type: 'summary',
      parent: 0,
      // SVAR crashes on an open summary without children.
      open: entries.length > 0,
    })

    for (const { id, span } of entries) {
      const node = nodesById.get(id)
      if (!node) continue

      if (node.kind === 'external') {
        const label = `${node.position.order_number} (${node.position.supplier_name})`
        tasks.push({
          id: node.id,
          text: node.position.expected_delivery_date ? label : `${label}${dateUnknownSuffix}`,
          start: span.start,
          end: span.end,
          type: 'task',
          parent: groupId,
        })
        continue
      }

      const order = node.order
      // Lot, part and position lead so a bar is recognizable.
      const orderLabel = `${order.lot_number} · ${params.madeItemLabel(order.made_item_part_number, order.made_item_revision)} · Pos ${order.lot_position_sequence}/${order.lot_position_count}`
      const details =
        (order.conflicts?.length ?? 0) > 0
          ? `${order.production_order_number}, ${order.conflicts!.map(conflictLabel).join(', ')}`
          : order.production_order_number
      tasks.push({
        id: node.id,
        text: withMethodSuffix(orderLabel, fabricationMethodLabel(order.lot_position_id)),
        details,
        start: span.start,
        end: span.end,
        // An unknown type renders as a normal bar with this string as a CSS
        // class, here `.conflict`.
        type: (order.conflicts?.length ?? 0) > 0 ? 'conflict' : 'task',
        parent: groupId,
        status: order.status,
        progress:
          order.quantity > 0 ? Math.round((order.quantity_completed / order.quantity) * 100) : 0,
      })
    }
  }

  const unassignedOrderIds = activeOrders
    .filter((order) => order.machine_id === null)
    .map((order) => orderTaskId(order))
  pushGroup(machineTaskId(null), noAssignmentLabel, unassignedOrderIds, true)

  for (const machine of machines) {
    const machineOrderIds = activeOrders
      .filter((order) => order.machine_id === machine.id)
      .sort((a, b) => a.queue_sequence - b.queue_sequence)
      .map((order) => orderTaskId(order))
    const machineLabel = withMethodSuffix(
      machine.internal_name,
      machine.fabricationMethods.join(', '),
    )
    pushGroup(machineTaskId(machine.id), machineLabel, machineOrderIds, true)
  }

  const externalNodeIds = [...nodesById.values()]
    .filter((node): node is ExternalPlanningNode => node.kind === 'external')
    .map((node) => node.id)
  pushGroup(EXTERNAL_GROUP_TASK_ID, externalLabel, externalNodeIds)

  const links: ILink[] = [...visualLinks.entries()].map(([id, { source, target }]) => ({
    id,
    source,
    target,
    type: 'e2s',
  }))

  return { tasks, links }
}
