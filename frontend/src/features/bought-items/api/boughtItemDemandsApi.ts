/**
 * Bought item demand and allocation client, built from the shared demand
 * factories.
 */
import type { Schemas } from '@/core/api/generated'
import {
  createDemandApi,
  createDemandBatchApi,
  createOrderItemAllocationApi,
} from '@/shared/api/createDemandApi'

import type {
  AllocationResponse,
  AutoAllocateResponse,
  DemandSummaryResponse,
  FulfillFromStockResponse,
} from '../types/boughtItemsAllocationsResponse'
import type {
  CommitBatchDemandsRequest,
  CommitBatchDemandsResponse,
  ValidateBatchDemandsRequest,
  ValidateBatchDemandsResponse,
} from '../types/boughtItemsDemandsBatchTypes'
import type {
  DemandItemCreateRequest,
  DemandItemFilterParams,
  DemandItemUpdateRequest,
} from '../types/boughtItemsDemandsRequest'
import type { BoughtItemDemandResponse, BoughtItemDemandStatus } from '../types/boughtItemsDemandsResponse'

export type AllocationCreateRequest = Schemas['AllocationCreateRequest']

const demandApi = createDemandApi<{
  demand: BoughtItemDemandResponse
  filters: DemandItemFilterParams
  createRequest: DemandItemCreateRequest
  updateRequest: DemandItemUpdateRequest
  status: BoughtItemDemandStatus
  allocation: AllocationResponse
  summary: DemandSummaryResponse
  fulfillFromStockResult: FulfillFromStockResponse
}>('bought')

const batchApi = createDemandBatchApi<{
  validateRequest: ValidateBatchDemandsRequest
  validateResponse: ValidateBatchDemandsResponse
  commitRequest: CommitBatchDemandsRequest
  commitResponse: CommitBatchDemandsResponse
}>('bought')

const orderItemAllocationApi = createOrderItemAllocationApi<{
  allocation: AllocationResponse
  createRequest: AllocationCreateRequest
  autoAllocateResult: AutoAllocateResponse
}>('bought')

export const getDemands = demandApi.list
export const createDemand = demandApi.create
export const updateDemand = demandApi.update
export const setDemandBucket = demandApi.setBucket
export const updateDemandStatus = demandApi.updateStatus
export const cancelDemand = demandApi.cancel
export const getAllocationsForDemand = demandApi.getAllocations
export const getDemandSummaryBatch = demandApi.getSummaryBatch
export const fulfillDemandFromStock = demandApi.fulfillFromStock
export const updateStockAllocation = demandApi.updateStockAllocation
export const deleteStockAllocation = demandApi.deleteStockAllocation

export const validateBatchDemands = batchApi.validateBatch
export const commitBatchDemands = batchApi.commitBatch

export const createAllocation = orderItemAllocationApi.create
export const updateAllocation = orderItemAllocationApi.update
export const deleteAllocation = orderItemAllocationApi.remove
export const autoAllocateDemand = orderItemAllocationApi.autoAllocate
