import type { Schemas } from '@/core/api/generated'

import type { MadeItemResponse } from './madeItemsResponse'

export type MadeItemDemandStatus = Schemas['MadeItemDemandStatus']

/**
 * item can be absent, e.g. when the item was hard-deleted, and uses
 * MadeItemResponse, whose processes are refined to the role union. bucket_id
 * carries only the id; names and colors come from the buckets store, so a
 * rename shows without refetching.
 */
export type MadeItemDemandResponse = Omit<Schemas['MadeItemDemandResponse'], 'item'> & {
  item: MadeItemResponse | null
}

/**
 * What canceling a made item demand would take down with it. Every level
 * carries will_cancel and keep_reason, since what stays matters as much as
 * what goes.
 */
export type CancelImpactProductionOrder = Schemas['CancelImpactProductionOrderResponse']

export type CancelImpactOrderItem = Schemas['CancelImpactOrderItemResponse']

export type CancelImpactSourceItemDemand = Schemas['CancelImpactSourceItemDemandResponse']

export type CancelImpactLot = Schemas['CancelImpactLotResponse']

export type MadeItemDemandCancelImpact = Schemas['MadeItemDemandCancelImpactResponse']
