import { createAllocationsStore } from '@/shared/stores/createAllocationsStore'
import {
  getDemandSummaryBatch,
  autoAllocateDemand,
  fulfillDemandFromStock,
  getAllocationsForDemand,
  createAllocation,
  updateAllocation,
  deleteAllocation,
  updateStockAllocation,
  deleteStockAllocation,
} from '@/features/bought-items'


export const useBoughtItemsAllocationsStore = createAllocationsStore('boughtItemsAllocations', {
  getSummaryBatch: getDemandSummaryBatch,
  autoAllocate: autoAllocateDemand,
  fulfillFromStock: fulfillDemandFromStock,
  getAllocationsForDemand,
  createAllocation,
  updateAllocation,
  deleteAllocation,
  updateStockAllocation,
  deleteStockAllocation,
})
