/**
 * Made item demand and allocation client, built from the shared demand
 * factories. Made item demands have no order-item allocations, since
 * production lots cover them.
 */
import { createDemandApi, createDemandBatchApi } from '@/shared/api/createDemandApi'

import type {
  MadeItemAllocationResponse,
  MadeItemDemandSummaryResponse,
  MadeItemFulfillFromStockResponse,
} from '../types/madeItemsAllocationsResponse'
import type {
  CommitBatchMadeItemDemandsRequest,
  CommitBatchMadeItemDemandsResponse,
  ValidateBatchMadeItemDemandsRequest,
  ValidateBatchMadeItemDemandsResponse,
} from '../types/madeItemsDemandsBatchTypes'
import type {
  MadeItemDemandCreateRequest,
  MadeItemDemandFilterParams,
  MadeItemDemandUpdateRequest,
} from '../types/madeItemsDemandsRequest'
import type {
  MadeItemDemandResponse,
  MadeItemDemandStatus,
} from '../types/madeItemsDemandsResponse'

const demandApi = createDemandApi<{
  demand: MadeItemDemandResponse
  filters: MadeItemDemandFilterParams
  createRequest: MadeItemDemandCreateRequest
  updateRequest: MadeItemDemandUpdateRequest
  status: MadeItemDemandStatus
  allocation: MadeItemAllocationResponse
  summary: MadeItemDemandSummaryResponse
  fulfillFromStockResult: MadeItemFulfillFromStockResponse
}>('made')

const batchApi = createDemandBatchApi<{
  validateRequest: ValidateBatchMadeItemDemandsRequest
  validateResponse: ValidateBatchMadeItemDemandsResponse
  commitRequest: CommitBatchMadeItemDemandsRequest
  commitResponse: CommitBatchMadeItemDemandsResponse
}>('made')

export const getMadeItemDemands = demandApi.list
export const createMadeItemDemand = demandApi.create
export const updateMadeItemDemand = demandApi.update
export const setMadeItemDemandBucket = demandApi.setBucket
export const updateMadeItemDemandStatus = demandApi.updateStatus
export const cancelMadeItemDemand = demandApi.cancel
export const getMadeItemAllocationsForDemand = demandApi.getAllocations
export const getMadeItemDemandSummaryBatch = demandApi.getSummaryBatch
export const fulfillMadeItemDemandFromStock = demandApi.fulfillFromStock
export const updateMadeItemStockAllocation = demandApi.updateStockAllocation
export const deleteMadeItemStockAllocation = demandApi.deleteStockAllocation

export const validateBatchMadeItemDemands = batchApi.validateBatch
export const commitBatchMadeItemDemands = batchApi.commitBatch
