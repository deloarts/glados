import { computed } from 'vue'
import type { Ref } from 'vue'

import { groupRowsByLabel } from '@/core/utils/tableRowGrouping'

/** A grouping a demand kind adds on top of status and bucket. */
export interface DemandOwnGrouping<TRow> {
  /** Row field that carries the group label, for example `_projectGroup`. */
  field: string
  label: (row: TRow) => string
}

export interface DemandGroupingOptions<TRow, TOther extends string> {
  items: () => TRow[]
  groupBy: Ref<'status' | 'bucket' | TOther | null>
  statusLabel: (row: TRow) => string
  /**
   * Name of the row's bucket, or undefined when the row has none or the
   * bucket is not loaded yet.
   */
  bucketName: (row: TRow) => string | undefined
  unbucketedLabel: () => string
  /** The kind's own groupings, such as project or manufacturer. */
  ownGroups: Record<TOther, DemandOwnGrouping<TRow>>
}

/**
 * Subheader grouping for the demand tables. Every kind groups by status and
 * by bucket, plus groupings of its own (project, manufacturer). Rows
 * get a label field per grouping and are sorted by it, `groupRowsBy` names
 * that field for the DataTable and the shell's group header.
 */
export function useDemandGrouping<TRow extends object, TOther extends string>(
  options: DemandGroupingOptions<TRow, TOther>,
) {
  const groupRowsBy = computed<string | undefined>(() => {
    const groupBy = options.groupBy.value
    if (!groupBy) return undefined
    if (groupBy === 'status') return '_statusGroup'
    if (groupBy === 'bucket') return '_bucketGroup'
    return options.ownGroups[groupBy].field
  })

  const groupedItems = computed<TRow[]>(() => {
    const items = options.items()
    const groupBy = options.groupBy.value
    if (!groupBy) return items

    if (groupBy === 'status') {
      return groupRowsByLabel(items, '_statusGroup', options.statusLabel)
    }

    if (groupBy === 'bucket') {
      return groupRowsByLabel(
        items,
        '_bucketGroup',
        (row) => options.bucketName(row) ?? options.unbucketedLabel(),
      )
    }

    const own = options.ownGroups[groupBy]
    return groupRowsByLabel(items, own.field, own.label)
  })

  return { groupedItems, groupRowsBy }
}
