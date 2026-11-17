import { useMachineCapability } from '../../composables/useMachineCapability'

import type { ProductionMachineResponse, MachinePoolResponse } from '@/features/production-machines'
import type { OrderResponse } from '@/features/orders'
import type { LotPositionResponse } from '../../types/productionLotsResponse'

// Grouped options of the assign Select in the lot step list.

export interface AssignTargetGroup {
  key: 'pools' | 'machines' | 'manual' | 'orders' | 'create'
  label: string
  items: { key: string; label: string }[]
}

export type AssignTargetKey =
  | `pool:${number}`
  | `machine:${number}`
  | `order:${number}`
  | 'manual'
  | 'order:new'

export interface BuildAssignTargetGroupsInput {
  position: LotPositionResponse
  machines: ProductionMachineResponse[]
  pools: MachinePoolResponse[]
  orders: OrderResponse[]
  /** write:production_orders gates the Pools/Machines/Manual groups. */
  canAssignInternal: boolean
  /** write:orders gates the Orders/Create groups. */
  canAssignExternal: boolean
  labels: {
    pools: string
    machines: string
    manual: string
    orders: string
    create: string
    /** Item label for the Manual group's single "Queue without machine" entry. */
    queueWithoutMachine: string
    /** Item label for the Create group's single "Create order…" entry. */
    createOrder: string
  }
}

/**
 * Groups, in order Pools, Machines, Manual, Orders, Create. Empty groups are
 * omitted except Create, which is shown whenever permitted.
 *
 * A QA position only gets the Machines group, limited to QA machines, since
 * QA work is never queued machine-less nor ordered externally.
 */
export function buildAssignTargetGroups(input: BuildAssignTargetGroupsInput): AssignTargetGroup[] {
  const { position, machines, pools, orders, canAssignInternal, canAssignExternal, labels } = input
  const { getCapableMachines, candidatePoolsForPosition, positionIsManual, positionRequiresQaMachine } =
    useMachineCapability()

  const isQaPosition = positionRequiresQaMachine(position)
  const groups: AssignTargetGroup[] = []

  if (canAssignInternal) {
    const candidatePools = candidatePoolsForPosition(position, pools)
    if (candidatePools.length > 0) {
      groups.push({
        key: 'pools',
        label: labels.pools,
        items: candidatePools.map((pool) => ({ key: `pool:${pool.id}`, label: pool.name })),
      })
    }

    const capableMachines = getCapableMachines(position, machines)
    if (capableMachines.length > 0) {
      groups.push({
        key: 'machines',
        label: labels.machines,
        items: capableMachines.map((machine) => ({
          key: `machine:${machine.id}`,
          label: machine.internal_name,
        })),
      })
    }

    if (!isQaPosition && positionIsManual(position)) {
      groups.push({
        key: 'manual',
        label: labels.manual,
        items: [{ key: 'manual', label: labels.queueWithoutMachine }],
      })
    }
  }

  if (canAssignExternal && !isQaPosition) {
    if (orders.length > 0) {
      groups.push({
        key: 'orders',
        label: labels.orders,
        items: orders.map((order) => ({
          key: `order:${order.id}`,
          label: `${order.order_number} · ${order.supplier_name}`,
        })),
      })
    }

    groups.push({
      key: 'create',
      label: labels.create,
      items: [{ key: 'order:new', label: labels.createOrder }],
    })
  }

  return groups
}

/** Inverse of the assign target key scheme; null for anything else. */
export function parseAssignTargetKey(
  key: string,
):
  | { kind: 'pool' | 'machine' | 'order'; id: number }
  | { kind: 'manual' }
  | { kind: 'create' }
  | null {
  if (key === 'manual') return { kind: 'manual' }
  if (key === 'order:new') return { kind: 'create' }
  const match = key.match(/^(pool|machine|order):(\d+)$/)
  if (!match) return null
  return { kind: match[1] as 'pool' | 'machine' | 'order', id: Number(match[2]) }
}
