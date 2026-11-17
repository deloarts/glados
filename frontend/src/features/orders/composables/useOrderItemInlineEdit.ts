import { ref, computed, type ComputedRef, type Ref } from 'vue'

import { extractApiError } from '@/core/utils/errors'
import { dateToParam, toLocalDayStart } from '@/core/utils/dates'
import type { ProjectRef } from '@/core/types/projectRef'
import type { BoughtItemResponse } from '@/features/bought-items'

import type { OrderItemResponse } from '../types/ordersResponse'
import type { OrderItemUpdateRequest } from '../types/ordersRequest'

export interface EditingItemState {
  position: number
  quantity: number
  unit: string
  items_per_unit: number
  price: number | null // euros
  expected_delivery_date: Date | null
  expected_pickup_date: Date | null
  note: string
  // item substitution
  selectedItem: BoughtItemResponse | null // current or newly chosen catalogue item
  originalItemId: number | null // used to detect whether item was changed
  virtualName: string // editable name for virtual (non-catalogue) items
  substituteReason: string
  // project reassignment
  selectedProject: ProjectRef | null
  originalProjectId: number | null
  saving: boolean
  error: string | null
}

export interface UseOrderItemInlineEditOptions {
  /**
   * The rows a save's error list is derived from: every row the table
   * currently renders, edited or not.
   */
  items: ComputedRef<OrderItemResponse[]> | Ref<OrderItemResponse[]>
  updateItem(itemId: number, payload: OrderItemUpdateRequest): Promise<void>
  /** Called after a save commits. */
  onSaved(): void
  /** Shown when the API error carries no usable message. */
  defaultErrorMessage: string
}

/**
 * Inline edit state for order lines. Not OpenVue's editMode="row", since
 * almost nothing edited is a row value: price is cents on the wire and euros
 * in the input, dates need conversion, and item and project changes are
 * selections.
 */
export function useOrderItemInlineEdit(options: UseOrderItemInlineEditOptions) {
  const editingItems = ref<Record<number, EditingItemState>>({})

  function startEdit(item: OrderItemResponse): void {
    editingItems.value[item.id] = {
      position: item.position,
      quantity: item.quantity,
      unit: item.unit,
      items_per_unit: item.items_per_unit,
      price: item.price !== null ? item.price / 100 : null,
      expected_delivery_date: item.expected_delivery_date
        ? toLocalDayStart(item.expected_delivery_date)
        : null,
      expected_pickup_date: item.expected_pickup_date
        ? toLocalDayStart(item.expected_pickup_date)
        : null,
      note: item.note ?? '',
      selectedItem:
        item.bought_item_id !== null
          ? ({
              id: item.bought_item_id,
              order_code_1: item.item_order_code_1,
              article_name: item.item_article_name,
            } as BoughtItemResponse)
          : null,
      originalItemId: item.bought_item_id,
      virtualName: item.virtual_name ?? '',
      substituteReason: '',
      selectedProject:
        item.project_id !== null
          ? {
              id: item.project_id,
              project_number: item.project_number,
              customer: { name: item.project_customer },
              description: item.project_description,
            }
          : null,
      originalProjectId: item.project_id,
      saving: false,
      error: null,
    }
  }

  function cancelEdit(itemId: number): void {
    delete editingItems.value[itemId]
  }

  function isEditing(itemId: number): boolean {
    return itemId in editingItems.value
  }

  function editState(itemId: number): EditingItemState {
    return editingItems.value[itemId] as EditingItemState
  }

  /** Rows whose save failed, surfaced above the table. */
  const editErrors = computed(() =>
    options.items.value
      .filter((item) => editingItems.value[item.id]?.error)
      .map((item) => ({ id: item.id, position: item.position, error: editState(item.id).error })),
  )

  async function saveItemEdit(item: OrderItemResponse): Promise<void> {
    const state = editingItems.value[item.id]
    if (!state) return
    state.saving = true
    state.error = null
    const itemChanged = state.selectedItem !== null && state.selectedItem.id !== state.originalItemId
    const projectChanged =
      state.selectedProject !== null && state.selectedProject.id !== state.originalProjectId
    // Only a VIRTUAL line carries its own name; every other line type
    // resolves it from its catalogue entry, and the API rejects the field.
    const virtualNameChanged =
      item.line_type === 'VIRTUAL' &&
      !itemChanged &&
      state.virtualName.trim() !== (item.virtual_name ?? '')
    const payload: OrderItemUpdateRequest = {
      quantity: state.quantity,
      unit: state.unit,
      items_per_unit: state.items_per_unit,
      price: state.price !== null ? Math.round(state.price * 100) : null,
      expected_delivery_date: dateToParam(state.expected_delivery_date),
      expected_pickup_date: dateToParam(state.expected_pickup_date),
      note: state.note.trim() || null,
      expected_edit_version: item.edit_version,
      ...(state.position !== item.position ? { position: state.position } : {}),
      ...(itemChanged
        ? {
            bought_item_id: state.selectedItem!.id,
            substitute_reason: state.substituteReason.trim() || null,
          }
        : {}),
      ...(virtualNameChanged ? { virtual_name: state.virtualName.trim() } : {}),
      ...(projectChanged ? { project_id: state.selectedProject!.id } : {}),
    }
    try {
      await options.updateItem(item.id, payload)
      cancelEdit(item.id)
      options.onSaved()
    } catch (e) {
      state.error = extractApiError(e) ?? options.defaultErrorMessage
      state.saving = false
    }
  }

  return {
    editingItems,
    startEdit,
    cancelEdit,
    isEditing,
    editState,
    editErrors,
    saveItemEdit,
  }
}
