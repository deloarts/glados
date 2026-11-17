import type { FabricationMethodResponse } from '@/features/fabrication-methods'
import type { OpenMachineDowntimeResponse } from './machineDowntimeResponse'
import type { ActiveProductionOrderResponse, ProductionMachineStatus } from './productionMachineStatus'
import type { Schemas } from '@/core/api/generated'

export type { FabricationMethodResponse }
export type { OpenMachineDowntimeResponse }
export type { ActiveProductionOrderResponse, ProductionMachineStatus }

export type ProductionMachineResponse = Schemas['ProductionMachineResponse']
