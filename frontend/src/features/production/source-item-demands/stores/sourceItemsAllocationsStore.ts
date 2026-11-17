import { createAllocationsStore } from '@/shared/stores/createAllocationsStore'
import {
  getSourceItemDemandSummaryBatch,
  autoAllocateSourceItemDemand,
  fulfillSourceItemDemandFromStock,
  getAllocationsForSourceItemDemand,
  createSourceItemAllocation,
  updateSourceItemAllocation,
  deleteSourceItemAllocation,
  updateSourceItemStockAllocation,
  deleteSourceItemStockAllocation,
} from '@/features/source-items'


export const useSourceItemsAllocationsStore = createAllocationsStore('sourceItemsAllocations', {
  getSummaryBatch: getSourceItemDemandSummaryBatch,
  autoAllocate: autoAllocateSourceItemDemand,
  fulfillFromStock: fulfillSourceItemDemandFromStock,
  getAllocationsForDemand: getAllocationsForSourceItemDemand,
  createAllocation: createSourceItemAllocation,
  updateAllocation: updateSourceItemAllocation,
  deleteAllocation: deleteSourceItemAllocation,
  updateStockAllocation: updateSourceItemStockAllocation,
  deleteStockAllocation: deleteSourceItemStockAllocation,
})
