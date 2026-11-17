/**
 * Display helpers for source item demands, which point at either a bought
 * item or a source item, never both.
 */

import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import type { SourceItemDemandResponse } from '../types/sourceItemDemandsResponse'
import { localizeLabel } from '@/shared/utils/localizeLabel'

export function itemLabel(demand: SourceItemDemandResponse): string {
  if (demand.bought_item) return demand.bought_item.article_name
  if (demand.source_item)
    return demand.source_item.dimension || `Source item #${demand.source_item.id}`
  return getEmptyPlaceholder()
}

export function itemSublabel(demand: SourceItemDemandResponse): string {
  if (demand.bought_item) return demand.bought_item.order_code_1
  if (demand.source_item) {
    return [demand.source_item.material, localizeLabel(demand.source_item.type_name)].filter(Boolean).join(' | ')
  }
  return ''
}

export function itemOrderCode1(demand: SourceItemDemandResponse): string {
  return demand.bought_item?.order_code_1 || demand.source_item?.order_code_1 || ''
}

export function itemOrderCode2(demand: SourceItemDemandResponse): string {
  return demand.bought_item?.order_code_2 || demand.source_item?.order_code_2 || ''
}

export function itemManufacturer(demand: SourceItemDemandResponse): string {
  return (
    demand.bought_item?.manufacturer_name ||
    demand.source_item?.manufacturer_name ||
    getEmptyPlaceholder()
  )
}

/** Which side a demand sits on; picks the detail dialog and thumbnail. */
export function itemKind(demand: SourceItemDemandResponse): 'bought' | 'source' | 'none' {
  if (demand.bought_item_id != null) return 'bought'
  if (demand.source_item_id != null) return 'source'
  return 'none'
}
