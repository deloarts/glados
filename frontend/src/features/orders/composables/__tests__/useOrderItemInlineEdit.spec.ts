import { describe, it, expect, vi } from 'vitest'
import { ref } from 'vue'

import { useOrderItemInlineEdit } from '../useOrderItemInlineEdit'
import { makeOrderItemResponse } from '@/test-utils/factories'
import type { OrderItemResponse } from '../../types/ordersResponse'
import type { OrderItemUpdateRequest } from '../../types/ordersRequest'

// OrderItemsTable.vue's inline-edit state machine (edit-state map +
// save/cancel + payload building), kept out of the table's large template.

function setup(items: OrderItemResponse[], updateItem = vi.fn<(itemId: number, payload: OrderItemUpdateRequest) => Promise<void>>().mockResolvedValue(undefined)) {
  const onSaved = vi.fn<() => void>()
  const api = useOrderItemInlineEdit({
    items: ref(items),
    updateItem,
    onSaved,
    defaultErrorMessage: 'Something went wrong.',
  })
  return { ...api, updateItem, onSaved }
}

describe('useOrderItemInlineEdit', () => {
  it('starts with no rows being edited', () => {
    const { isEditing } = setup([makeOrderItemResponse()])
    expect(isEditing(1)).toBe(false)
  })

  it('startEdit() seeds edit state from the item, converting price to euros and dates to Date objects', () => {
    const item = makeOrderItemResponse({ price: 1250, expected_delivery_date: '2026-03-01' })
    const { startEdit, isEditing, editState } = setup([item])

    startEdit(item)

    expect(isEditing(1)).toBe(true)
    expect(editState(1).price).toBe(12.5)
    expect(editState(1).expected_delivery_date).toBeInstanceOf(Date)
    expect(editState(1).saving).toBe(false)
    expect(editState(1).error).toBeNull()
  })

  it('cancelEdit() removes the row from edit state', () => {
    const item = makeOrderItemResponse()
    const { startEdit, cancelEdit, isEditing } = setup([item])

    startEdit(item)
    cancelEdit(item.id)

    expect(isEditing(item.id)).toBe(false)
  })

  it('editErrors lists only rows with a saved error, in item order', () => {
    const a = makeOrderItemResponse({ id: 1, position: 1 })
    const b = makeOrderItemResponse({ id: 2, position: 2 })
    const updateItem = vi
      .fn<(itemId: number, payload: OrderItemUpdateRequest) => Promise<void>>()
      .mockRejectedValue(new Error('boom'))
    const { startEdit, saveItemEdit, editErrors } = setup([a, b], updateItem)

    startEdit(a)
    startEdit(b)

    return saveItemEdit(a).then(() => {
      expect(editErrors.value).toEqual([{ id: 1, position: 1, error: 'Something went wrong.' }])
    })
  })

  it('saveItemEdit() sends a minimal payload when nothing but the base fields changed', async () => {
    const item = makeOrderItemResponse({
      id: 1,
      quantity: 4,
      unit: 'ST',
      items_per_unit: 1,
      price: 1250,
    })
    const updateItem = vi
      .fn<(itemId: number, payload: OrderItemUpdateRequest) => Promise<void>>()
      .mockResolvedValue(undefined)
    const { startEdit, saveItemEdit } = setup([item], updateItem)

    startEdit(item)
    await saveItemEdit(item)

    expect(updateItem).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ quantity: 4, unit: 'ST', items_per_unit: 1, price: 1250 }),
    )
    const payload = updateItem.mock.calls[0]![1]
    expect(payload).not.toHaveProperty('bought_item_id')
    expect(payload).not.toHaveProperty('project_id')
    expect(payload).not.toHaveProperty('virtual_name')
  })

  it('saveItemEdit() clears edit state and calls onSaved on success', async () => {
    const item = makeOrderItemResponse()
    const { startEdit, saveItemEdit, isEditing, onSaved } = setup([item])

    startEdit(item)
    await saveItemEdit(item)

    expect(isEditing(item.id)).toBe(false)
    expect(onSaved).toHaveBeenCalledTimes(1)
  })

  it('saveItemEdit() keeps the row in edit state and records the error on failure', async () => {
    const item = makeOrderItemResponse()
    const updateItem = vi
      .fn<(itemId: number, payload: OrderItemUpdateRequest) => Promise<void>>()
      .mockRejectedValue(new Error('nope'))
    const { startEdit, saveItemEdit, isEditing, editState, onSaved } = setup([item], updateItem)

    startEdit(item)
    await saveItemEdit(item)

    expect(isEditing(item.id)).toBe(true)
    expect(editState(item.id).saving).toBe(false)
    expect(editState(item.id).error).toBe('Something went wrong.')
    expect(onSaved).not.toHaveBeenCalled()
  })

  it('saveItemEdit() is a no-op for a row that was never put into edit state', async () => {
    const item = makeOrderItemResponse()
    const { saveItemEdit, updateItem } = setup([item])

    await saveItemEdit(item)

    expect(updateItem).not.toHaveBeenCalled()
  })

  it('saveItemEdit() includes bought_item_id and substitute_reason only when the item was substituted', async () => {
    const item = makeOrderItemResponse({ bought_item_id: 10 })
    const updateItem = vi
      .fn<(itemId: number, payload: OrderItemUpdateRequest) => Promise<void>>()
      .mockResolvedValue(undefined)
    const { startEdit, editState, saveItemEdit } = setup([item], updateItem)

    startEdit(item)
    editState(item.id).selectedItem = { id: 20, order_code_1: 'OC-2', article_name: 'New' } as never
    editState(item.id).substituteReason = 'Out of stock'

    await saveItemEdit(item)

    const payload = updateItem.mock.calls[0]![1]
    expect(payload.bought_item_id).toBe(20)
    expect(payload.substitute_reason).toBe('Out of stock')
  })

  it('saveItemEdit() includes project_id only when the project changed', async () => {
    const item = makeOrderItemResponse({ project_id: 7 })
    const updateItem = vi
      .fn<(itemId: number, payload: OrderItemUpdateRequest) => Promise<void>>()
      .mockResolvedValue(undefined)
    const { startEdit, editState, saveItemEdit } = setup([item], updateItem)

    startEdit(item)
    editState(item.id).selectedProject = {
      id: 8,
      project_number: 'P-008',
      customer: { name: 'Other' },
      description: null,
    } as never

    await saveItemEdit(item)

    const payload = updateItem.mock.calls[0]![1]
    expect(payload.project_id).toBe(8)
  })

  it('saveItemEdit() includes virtual_name only for a changed VIRTUAL line', async () => {
    const item = makeOrderItemResponse({
      line_type: 'VIRTUAL',
      virtual_name: 'Old name',
      bought_item_id: null,
    })
    const updateItem = vi
      .fn<(itemId: number, payload: OrderItemUpdateRequest) => Promise<void>>()
      .mockResolvedValue(undefined)
    const { startEdit, editState, saveItemEdit } = setup([item], updateItem)

    startEdit(item)
    editState(item.id).virtualName = 'New name'

    await saveItemEdit(item)

    const payload = updateItem.mock.calls[0]![1]
    expect(payload.virtual_name).toBe('New name')
  })
})
