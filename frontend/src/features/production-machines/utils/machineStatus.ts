import { formatISODateTime } from '@/core/utils/dates'
import type {
  ProductionMachineResponse,
  ProductionMachineStatus,
} from '../types/productionMachinesResponse'

// Tag severity per machine status, matching the precedence the backend
// resolves: down is the hardest state, idle the most neutral.
export const machineStatusSeverity: Record<ProductionMachineStatus, string> = {
  down: 'danger',
  running: 'success',
  paused: 'warn',
  idle: 'secondary',
}

// Defaults to idle, like the backend schema.
export function machineStatus(machine: ProductionMachineResponse): ProductionMachineStatus {
  return machine.status ?? 'idle'
}

// Status tooltip: the open downtime when down, the occupying orders when
// running or paused, otherwise a "no order" note.
export function machineStatusTooltip(
  machine: ProductionMachineResponse,
  t: (key: string, params?: Record<string, unknown>) => string,
): string {
  const status = machineStatus(machine)
  if (status === 'down' && machine.open_downtime) {
    return t('productionMachines.status.downTooltip', {
      time: formatISODateTime(machine.open_downtime.started_at),
      reason: t(`productionMachines.downtime.reasons.${machine.open_downtime.reason}`),
    })
  }
  const activeOrders = machine.active_orders ?? []
  if ((status === 'running' || status === 'paused') && activeOrders.length > 0) {
    return activeOrders.map((order) => order.production_order_number).join(', ')
  }
  return t('productionMachines.status.noOrderTooltip')
}
