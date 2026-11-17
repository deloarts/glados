import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'

import { useProductionLotsFiltersStore } from '../../stores/productionLotsFiltersStore'

/**
 * The filter cards of the lots table's item and source columns. Each cell
 * shows two lines, and its card searches each line on its own: the item's
 * part number and article name, the source's dimension and type. The cards
 * bind one record per column, mapped onto the filters store's own fields.
 */
export function useLotsTableFilterCards() {
  const { t } = useI18n()
  const { itemPartNumber, itemArticleName, sourceDimension, sourceType } = storeToRefs(
    useProductionLotsFiltersStore(),
  )

  const itemFilterFields = computed(() => [
    { key: 'partNumber', label: t('production.lots.filters.partNumber') },
    { key: 'articleName', label: t('production.lots.filters.articleName') },
  ])
  const itemFilter = computed({
    get: () => ({ partNumber: itemPartNumber.value, articleName: itemArticleName.value }),
    set: (value: Record<string, string>) => {
      itemPartNumber.value = value.partNumber ?? ''
      itemArticleName.value = value.articleName ?? ''
    },
  })

  const sourceFilterFields = computed(() => [
    { key: 'dimension', label: t('production.lots.filters.dimension') },
    { key: 'type', label: t('production.lots.filters.type') },
  ])
  const sourceFilter = computed({
    get: () => ({ dimension: sourceDimension.value, type: sourceType.value }),
    set: (value: Record<string, string>) => {
      sourceDimension.value = value.dimension ?? ''
      sourceType.value = value.type ?? ''
    },
  })

  return { itemFilterFields, itemFilter, sourceFilterFields, sourceFilter }
}
