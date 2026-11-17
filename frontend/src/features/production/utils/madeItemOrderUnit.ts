import type { BoughtItemUnit } from '@/shared/utils/units'


/**
 * Unit of every purchase-order line created for a made-item lot position: always pieces;
 * documented in handbook production/manage-orders. Backend stores unit as free text, so this
 * is the one place the value lives.
 */
export const MADE_ITEM_ORDER_UNIT: BoughtItemUnit = 'PCS'
