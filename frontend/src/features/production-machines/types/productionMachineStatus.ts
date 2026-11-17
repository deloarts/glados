import type { Schemas } from '@/core/api/generated'

export type ProductionMachineStatus = Schemas['ProductionMachineStatus']

// Denormalized onto ProductionMachineResponse.active_orders, see
// productionMachinesResponse.ts. Only orders currently in_progress or
// paused ever appear here.
export type ActiveProductionOrderResponse = Schemas['ActiveProductionOrderResponse']
