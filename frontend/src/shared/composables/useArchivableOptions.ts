import { computed } from 'vue'

import type { ComputedRef, Ref } from 'vue'

export interface ArchivableItem {
  archived: boolean
}

export interface UseArchivableOptionsResult<T extends ArchivableItem> {
  /**
   * The given items, archived rows sorted after live ones (stable within
   * each group). Bind this, not the raw list, to a picker's `:options`.
   */
  sortedOptions: ComputedRef<T[]>
  /**
   * True when the current value (or, for a multi-select, any selected
   * value) is archived. Drives the Archived tag on the selection and the
   * warning line below the control.
   */
  isArchived: (value: T | T[] | null | undefined) => boolean
}

/**
 * Referencing an already-archived row is allowed. A picker over an
 * archivable resource must keep every row selectable, not just live ones,
 * while still making the distinction visible: archived rows sort after live
 * ones in the list and both the option and a selected archived value carry
 * the Archived tag. Pair this with `ArchivedOptionTag.vue` in the picker's
 * `#option`/`#value` templates and `ArchivedSelectionWarning.vue` below the
 * control. See an existing picker (e.g. CustomerSelect.vue) for the full
 * wiring.
 *
 * The source list must already include archived rows (the owning store's
 * picker fetch requests `include_archived: true`); this composable only
 * orders and inspects what it's given, it never filters archived rows out.
 */
export function useArchivableOptions<T extends ArchivableItem>(
  items: Ref<T[]> | ComputedRef<T[]>,
): UseArchivableOptionsResult<T> {
  const sortedOptions = computed(() => {
    const live: T[] = []
    const archived: T[] = []
    for (const item of items.value) {
      ;(item.archived ? archived : live).push(item)
    }
    return [...live, ...archived]
  })

  function isArchived(value: T | T[] | null | undefined): boolean {
    if (!value) return false
    if (Array.isArray(value)) return value.some((v) => !!v?.archived)
    return !!value.archived
  }

  return { sortedOptions, isArchived }
}
