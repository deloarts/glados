// The made item label itself lives in shared/utils, since screens of every
// context show it, including the platform's PDM settings.
import type { MadeItemResponse } from '../types/madeItemsResponse'
import { localizeLabel } from '@/shared/utils/localizeLabel'

export { formatMadeItemNumber, useMadeItemLabel } from '@/shared/utils/madeItemLabel'

/**
 * The label of the bought or source item a made item is made from: the
 * article name with its order codes for a bought item, the type name or else
 * the material for a source item, and "-" when neither is linked.
 */
export function sourceItemDisplayLabel(item: Pick<MadeItemResponse, 'bought_item' | 'source_item'>): string {
  if (item.bought_item) {
    const orderCode = item.bought_item.order_code_2
      ? `${item.bought_item.order_code_1} / ${item.bought_item.order_code_2}`
      : item.bought_item.order_code_1
    return `${item.bought_item.article_name} (${orderCode})`
  }
  if (item.source_item) {
    return localizeLabel(item.source_item.type_name) || item.source_item.material
  }
  return '-'
}
