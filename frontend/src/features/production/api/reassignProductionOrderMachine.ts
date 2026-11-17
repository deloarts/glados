import { webApi } from '@/core/api/webRequest'

import type { ReassignProductionOrderMachineRequest } from '../types/productionOrdersRequest'
import type { ProductionOrderResponse } from '../types/productionOrdersResponse'

// payload targets either a specific machine (machine_id, possibly null to
// clear it) or a machine pool (machine_pool_id); the two are mutually
// exclusive, see ReassignProductionOrderMachineRequest.
export async function reassignProductionOrderMachine(
  productionOrderId: number,
  payload: ReassignProductionOrderMachineRequest,
): Promise<ProductionOrderResponse> {
  return webApi.put('/production-orders/{production_order_id}/machine', {
    path: { production_order_id: productionOrderId },
    body: payload,
  })
}
