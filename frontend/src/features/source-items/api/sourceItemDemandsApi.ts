/**
 * Source item demand and allocation client, built from the shared demand
 * factories. Source item demands are canceled rather than deleted and have
 * no batch import.
 */
import type { Schemas } from '@/core/api/generated'
import { createDemandApi, createOrderItemAllocationApi } from '@/shared/api/createDemandApi'

import type {
  SourceItemDemandCreateRequest,
  SourceItemDemandFilterParams,
  SourceItemDemandUpdateRequest,
} from '../types/sourceItemDemandsRequest'
import type {
  SourceItemDemandResponse,
  SourceItemDemandStatus,
} from '../types/sourceItemDemandsResponse'
import type {
  AutoAllocateSourceItemDemandResponse,
  FulfillSourceItemDemandFromStockResponse,
  SourceItemAllocationResponse,
  SourceItemDemandSummaryResponse,
} from '../types/sourceItemsAllocationsResponse'

export type SourceItemAllocationCreateRequest = Schemas['SourceItemAllocationCreateRequest']

const demandApi = createDemandApi<{
  demand: SourceItemDemandResponse
  filters: SourceItemDemandFilterParams
  createRequest: SourceItemDemandCreateRequest
  updateRequest: SourceItemDemandUpdateRequest
  status: SourceItemDemandStatus
  allocation: SourceItemAllocationResponse
  summary: SourceItemDemandSummaryResponse
  fulfillFromStockResult: FulfillSourceItemDemandFromStockResponse
}>('source')

const orderItemAllocationApi = createOrderItemAllocationApi<{
  allocation: SourceItemAllocationResponse
  createRequest: SourceItemAllocationCreateRequest
  autoAllocateResult: AutoAllocateSourceItemDemandResponse
}>('source')

export const getSourceItemDemands = demandApi.list
export const createSourceItemDemand = demandApi.create
export const updateSourceItemDemand = demandApi.update
export const setSourceItemDemandBucket = demandApi.setBucket
export const updateSourceItemDemandStatus = demandApi.updateStatus
export const getAllocationsForSourceItemDemand = demandApi.getAllocations
export const getSourceItemDemandSummaryBatch = demandApi.getSummaryBatch
export const fulfillSourceItemDemandFromStock = demandApi.fulfillFromStock
export const updateSourceItemStockAllocation = demandApi.updateStockAllocation
export const deleteSourceItemStockAllocation = demandApi.deleteStockAllocation

export const createSourceItemAllocation = orderItemAllocationApi.create
export const updateSourceItemAllocation = orderItemAllocationApi.update
export const deleteSourceItemAllocation = orderItemAllocationApi.remove
export const autoAllocateSourceItemDemand = orderItemAllocationApi.autoAllocate
