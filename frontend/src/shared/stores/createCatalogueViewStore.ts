import { ref } from 'vue'
import { defineStore } from 'pinia'

/**
 * The row-grouping/sort/actions-column display state every catalogue table
 * (source/made/bought items) carries. `TGroupBy` is each feature's own
 * non-null grouping-field union (the store adds the `| null` "no grouping"
 * state itself); `TSortBy` is each feature's own sortable-field union.
 * `SortDir` is `'asc' | 'desc'` everywhere, so it isn't a type parameter.
 */
export function createCatalogueViewStore<TGroupBy extends string, TSortBy extends string>(
  id: string,
) {
  return defineStore(id, () => {
    const groupBy = ref<TGroupBy | null>(null)
    const showActions = ref(false)
    const sortBy = ref<TSortBy | null>(null)
    const sortDir = ref<'asc' | 'desc'>('asc')

    function setGroupBy(value: TGroupBy): void {
      groupBy.value = groupBy.value === value ? null : value
    }

    function clearGroupBy(): void {
      groupBy.value = null
    }

    function toggleShowActions(): void {
      showActions.value = !showActions.value
    }

    function setSort(field: TSortBy, dir: 'asc' | 'desc'): void {
      sortBy.value = field
      sortDir.value = dir
    }

    function clearSort(): void {
      sortBy.value = null
      sortDir.value = 'asc'
    }

    return {
      groupBy,
      setGroupBy,
      clearGroupBy,
      showActions,
      toggleShowActions,
      sortBy,
      sortDir,
      setSort,
      clearSort,
    }
  })
}
