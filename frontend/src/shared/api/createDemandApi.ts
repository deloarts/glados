/**
 * Demand and allocation endpoints that the bought, made and source item
 * features share. The three backends expose the same routes under a
 * kind-specific prefix (`/bought-items-demands`, `/made-items-demands`,
 * `/source-item-demands`, plus the matching `-allocations` prefix), so one
 * factory produces each feature's client and the typed `webApi` checks every
 * route against all three kinds at compile time.
 *
 * Only routes that exist with the same shape for every kind listed in a
 * factory's kind parameter live here. Endpoints that one kind lacks get
 * their own narrower factory below (batch import, order-item allocations),
 * and endpoints unique to one kind stay in that feature's `api/` folder.
 *
 * The schema checks routes, path params, queries and request bodies. Response
 * types come from the feature's type map, because each feature refines the
 * generated response shapes (see e.g. `boughtItemsDemandsResponse.ts`).
 */
import { sendIdempotent } from '@/core/api/idempotency'
import {
  webApi,
  type QueryOf,
  type WebPath,
  type WebRequestConfig,
  type WebRequestOptions,
} from '@/core/api/webRequest'
import type { PageResponse } from '@/core/api/types'

const DEMAND_ROUTES = {
  bought: { demands: '/bought-items-demands', allocations: '/bought-items-allocations' },
  made: { demands: '/made-items-demands', allocations: '/made-items-allocations' },
  source: { demands: '/source-item-demands', allocations: '/source-item-allocations' },
} as const

export type DemandKind = keyof typeof DEMAND_ROUTES

type DemandsPath<K extends DemandKind> = (typeof DEMAND_ROUTES)[K]['demands']

type BodyOf<P extends string, M extends 'post' | 'put'> =
  WebRequestOptions<P, M> extends { body: infer B } ? B : never

type ListPath = DemandsPath<DemandKind> & WebPath<'get'>
type ItemPath = `${DemandsPath<DemandKind>}/{demand_id}`
type StatusPath = `${DemandsPath<DemandKind>}/{demand_id}/status`

/**
 * Per-feature types for one demand kind. Request types are constrained by
 * the schema, so a feature filter or payload that drifts from the backend
 * fails to compile.
 */
export interface DemandApiTypes {
  demand: unknown
  filters: QueryOf<ListPath>
  createRequest: BodyOf<DemandsPath<DemandKind>, 'post'>
  updateRequest: BodyOf<ItemPath, 'put'>
  status: QueryOf<StatusPath, 'put'>['new_status']
  allocation: unknown
  summary: unknown
  fulfillFromStockResult: unknown
}

export function createDemandApi<T extends DemandApiTypes>(kind: DemandKind) {
  const { demands, allocations } = DEMAND_ROUTES[kind]

  return {
    async list(params?: T['filters'], config?: WebRequestConfig): Promise<PageResponse<T['demand']>> {
      return (await webApi.get(demands, { query: params, config })) as PageResponse<T['demand']>
    },

    async create(payload: T['createRequest']): Promise<T['demand']> {
      return (await webApi.post(demands, { body: payload })) as T['demand']
    },

    async update(id: number, payload: T['updateRequest']): Promise<T['demand']> {
      return (await webApi.put(`${demands}/{demand_id}`, {
        path: { demand_id: id },
        body: payload,
      })) as T['demand']
    },

    async setBucket(id: number, bucketId: number | null): Promise<T['demand']> {
      return (await webApi.put(`${demands}/{demand_id}/bucket`, {
        path: { demand_id: id },
        body: { bucket_id: bucketId },
      })) as T['demand']
    },

    async updateStatus(id: number, newStatus: T['status']): Promise<T['demand']> {
      return (await webApi.put(`${demands}/{demand_id}/status`, {
        path: { demand_id: id },
        query: { new_status: newStatus },
        body: null,
      })) as T['demand']
    },

    /** Cancels the demand, which releases every allocation it holds. */
    async cancel(id: number): Promise<T['demand']> {
      return (await webApi.post(`${demands}/{demand_id}/cancel`, {
        path: { demand_id: id },
        body: null,
      })) as T['demand']
    },

    async getAllocations(demandId: number): Promise<T['allocation'][]> {
      return (await webApi.get(`${allocations}/demand/{demand_id}`, {
        path: { demand_id: demandId },
      })) as T['allocation'][]
    },

    async getSummaryBatch(demandIds: number[]): Promise<Record<number, T['summary']>> {
      return (await webApi.post(`${allocations}/demands/summary-batch`, {
        body: demandIds,
      })) as Record<number, T['summary']>
    },

    async fulfillFromStock(
      demandId: number,
      quantity: number,
    ): Promise<T['fulfillFromStockResult']> {
      return (await sendIdempotent((config) =>
        webApi.post(`${allocations}/demand/{demand_id}/fulfill-from-stock`, {
          path: { demand_id: demandId },
          body: { quantity },
          config,
        }),
      )) as T['fulfillFromStockResult']
    },

    async updateStockAllocation(demandId: number, quantity: number): Promise<T['allocation']> {
      return (await webApi.put(`${allocations}/demand/{demand_id}/stock`, {
        path: { demand_id: demandId },
        body: { quantity },
      })) as T['allocation']
    },

    async deleteStockAllocation(demandId: number): Promise<void> {
      await webApi.delete(`${allocations}/demand/{demand_id}/stock`, {
        path: { demand_id: demandId },
      })
    },
  }
}

type BatchKind = Extract<DemandKind, 'bought' | 'made'>
type BatchValidatePath = `${DemandsPath<BatchKind>}/batch/validate`
type BatchCommitPath = `${DemandsPath<BatchKind>}/batch/commit`

export interface DemandBatchApiTypes {
  validateRequest: BodyOf<BatchValidatePath, 'post'>
  validateResponse: unknown
  commitRequest: BodyOf<BatchCommitPath, 'post'>
  commitResponse: unknown
}

/**
 * Spreadsheet demand import (validate a batch, then commit it), offered by
 * the bought and made item backends only.
 */
export function createDemandBatchApi<T extends DemandBatchApiTypes>(kind: BatchKind) {
  const { demands } = DEMAND_ROUTES[kind]

  return {
    async validateBatch(payload: T['validateRequest']): Promise<T['validateResponse']> {
      return (await webApi.post(`${demands}/batch/validate`, {
        body: payload,
      })) as T['validateResponse']
    },

    async commitBatch(payload: T['commitRequest']): Promise<T['commitResponse']> {
      return (await sendIdempotent((config) =>
        webApi.post(`${demands}/batch/commit`, { body: payload, config }),
      )) as T['commitResponse']
    },
  }
}

type OrderAllocationKind = Extract<DemandKind, 'bought' | 'source'>
type AllocationsPath<K extends DemandKind> = (typeof DEMAND_ROUTES)[K]['allocations']

export interface OrderItemAllocationApiTypes {
  allocation: unknown
  createRequest: BodyOf<`${AllocationsPath<OrderAllocationKind>}/`, 'post'>
  autoAllocateResult: unknown
}

/**
 * Allocations of purchase order items to a demand, which exist for bought
 * and source items. Made item demands are covered by production lots
 * instead, so the made backend has none of these routes.
 */
export function createOrderItemAllocationApi<T extends OrderItemAllocationApiTypes>(
  kind: OrderAllocationKind,
) {
  const { allocations } = DEMAND_ROUTES[kind]

  return {
    // The trailing slash is how these clients have always called the route.
    async create(payload: T['createRequest']): Promise<T['allocation']> {
      return (await sendIdempotent((config) =>
        webApi.post(`${allocations}/`, { body: payload, config }),
      )) as T['allocation']
    },

    async update(
      demandId: number,
      orderItemId: number,
      quantity: number,
    ): Promise<T['allocation']> {
      return (await webApi.put(`${allocations}/demand/{demand_id}/order-item/{order_item_id}`, {
        path: { demand_id: demandId, order_item_id: orderItemId },
        body: { quantity },
      })) as T['allocation']
    },

    async remove(demandId: number, orderItemId: number): Promise<void> {
      await webApi.delete(`${allocations}/demand/{demand_id}/order-item/{order_item_id}`, {
        path: { demand_id: demandId, order_item_id: orderItemId },
      })
    },

    async autoAllocate(demandId: number): Promise<T['autoAllocateResult']> {
      return (await webApi.post(`${allocations}/demand/{demand_id}/auto-allocate`, {
        path: { demand_id: demandId },
      })) as T['autoAllocateResult']
    },
  }
}
