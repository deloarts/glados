import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { DataTableRowReorderEvent } from 'openvue/datatable'

import { useErrorToast } from '@/core/composables/useErrorToast'
import type { ListPlaceTarget } from '@/shared/types/listOrder'

/**
 * Where the dropped row now sits, named by a neighbour rather than a
 * position, so the order stays right on any page: after the row above it,
 * or before the row below it when it was dropped at the top of the page.
 */
export function dropTarget<T extends { id: number }>(page: T[], index: number): ListPlaceTarget {
  const above = page[index - 1]
  if (above) return { after_id: above.id }
  const below = page[index + 1]
  return below ? { before_id: below.id } : {}
}

/**
 * Reordering a hand-ordered table by dragging the grip in its first column,
 * the same grip as on the production queue cards. `rows` is the page the
 * table shows and `place` sends the drop to the backend, getting the page
 * in its new order so the row stays where it was dropped while the list
 * reloads. The caller decides when the grip shows: only to users who may
 * reorder, and only while the table shows the hand-kept order, since a
 * sorted, searched or filtered page has other neighbours than the order a
 * drop would change.
 */
export function useRowDragReorder<T extends { id: number }>(
  rows: () => T[],
  place: (id: number, target: ListPlaceTarget, droppedPage: T[]) => Promise<unknown>,
) {
  const { t } = useI18n()
  const { toastOnError } = useErrorToast()

  // Pass-through for the `row-reorder` column: the grip's class, which
  // main.scss styles, its tooltip and a hook for the specs.
  const handlePt = computed(() => ({
    reorderableRowHandle: {
      class: 'row-drag-handle',
      title: t('common.dragToReorder'),
      'data-testid': 'row-drag-handle',
    },
  }))

  function onRowReorder(event: DataTableRowReorderEvent): void {
    if (event.dragIndex === event.dropIndex) return
    // The event's own reordered list assumes the whole list is loaded, which
    // a paged table never has, so the page is reordered here from the indexes.
    const page = [...rows()]
    const [moved] = page.splice(event.dragIndex, 1)
    if (!moved) return
    page.splice(event.dropIndex, 0, moved)
    place(moved.id, dropTarget(page, event.dropIndex), page).catch(toastOnError())
  }

  return { handlePt, onRowReorder }
}

/**
 * The whole list after a drop, the same as the backend orders it: the entry
 * directly after `after_id`, or before `before_id`, or first with neither.
 * For a list held whole on the client, where the table may hide some of its
 * entries, such as the archived ones, so the dropped page alone is not the
 * new list.
 */
export function placeInList<T extends { id: number }>(
  list: T[],
  id: number,
  target: ListPlaceTarget,
): T[] {
  const moved = list.find((entry) => entry.id === id)
  if (!moved) return list
  const rest = list.filter((entry) => entry.id !== id)
  const anchorId = target.after_id ?? target.before_id
  const anchor = rest.findIndex((entry) => entry.id === anchorId)
  const index = anchor === -1 ? 0 : target.after_id != null ? anchor + 1 : anchor
  rest.splice(index, 0, moved)
  return rest
}
