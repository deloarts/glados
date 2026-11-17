import { reactive } from 'vue'

import { useSelectionEdit } from '@/shared/composables/useSelectionEdit'
import {
  TOLERANCE_FIELDS,
  emptyTolerances,
  tolerancesOf,
  tolerancesToSave,
  type ToleranceValues,
} from '@/shared/utils/deliveryTolerance'

import type { BoughtItemDataSource, BoughtItemUpdateRequest } from '../types/boughtItemsRequest'
import type { BoughtItemCatalogueStatus, BoughtItemResponse } from '../types/boughtItemsResponse'

export interface BoughtItemEditFormState extends ToleranceValues {
  order_code_1: string
  order_code_2: string
  gtin: string
  ean: string
  tariff_number: string
  article_name: string
  article_group_ids: number[]
  data_source: BoughtItemDataSource | null
  status: BoughtItemCatalogueStatus | null
  part_number: string
  mass: number | null
  note: string
  weblink: string
  manufacturer_id: number | null
  product_family_id: number | null
  successor_item_id: number | null
}

function createEmptyForm(): BoughtItemEditFormState {
  return {
    order_code_1: '',
    order_code_2: '',
    gtin: '',
    ean: '',
    tariff_number: '',
    article_name: '',
    article_group_ids: [],
    data_source: null,
    status: null,
    part_number: '',
    mass: null,
    note: '',
    weblink: '',
    manufacturer_id: null,
    product_family_id: null,
    successor_item_id: null,
    ...emptyTolerances(),
  }
}

function articleGroupIds(item: BoughtItemResponse): number[] {
  return (item.article_groups ?? []).map((group) => group.id).sort((a, b) => a - b)
}

function arraysEqual(a: number[], b: number[]): boolean {
  return a.length === b.length && a.every((value, index) => value === b[index])
}

/**
 * The form model of the bought items edit panel: one form over the whole
 * selection, where a field the selected items disagree on stays mixed until
 * the user types into it, and only the touched fields overwrite each item on
 * save.
 */
export function useBoughtItemsCatalogueEditForm(multipleValuesLabel: () => string) {
  const form = reactive(createEmptyForm())

  const { mixedFields, dirtyFields, applyFieldFromSelection, markDirty, placeholderFor, clearFields } =
    useSelectionEdit<BoughtItemEditFormState, BoughtItemResponse>(form, multipleValuesLabel)

  // Empties the form and fills it from the selection, marking the fields the
  // items disagree on as mixed.
  function fillFromSelection(items: BoughtItemResponse[]): void {
    clearFields()
    Object.assign(form, createEmptyForm())

    if (items.length === 0) {
      return
    }

    applyFieldFromSelection('order_code_1', items, (item) => item.order_code_1, '')
    applyFieldFromSelection('order_code_2', items, (item) => item.order_code_2 ?? '', '')
    applyFieldFromSelection('gtin', items, (item) => item.gtin ?? '', '')
    applyFieldFromSelection('ean', items, (item) => item.ean ?? '', '')
    applyFieldFromSelection('tariff_number', items, (item) => item.tariff_number ?? '', '')
    applyFieldFromSelection('article_name', items, (item) => item.article_name, '')
    applyFieldFromSelection(
      'data_source',
      items,
      (item) => item.data_source as BoughtItemDataSource,
      null,
    )
    applyFieldFromSelection('status', items, (item) => item.status, null)
    applyFieldFromSelection('part_number', items, (item) => item.part_number ?? '', '')
    applyFieldFromSelection('mass', items, (item) => item.mass, null)
    applyFieldFromSelection('note', items, (item) => item.note ?? '', '')
    applyFieldFromSelection('weblink', items, (item) => item.weblink ?? '', '')
    applyFieldFromSelection('manufacturer_id', items, (item) => item.manufacturer_id, null)
    applyFieldFromSelection(
      'product_family_id',
      items,
      (item) => item.product_family_id ?? null,
      null,
    )
    applyFieldFromSelection('successor_item_id', items, (item) => item.successor_item_id, null)
    for (const field of TOLERANCE_FIELDS) {
      applyFieldFromSelection(field, items, (item) => tolerancesOf(item, field), null)
    }

    const groupIdsList = items.map((item) => articleGroupIds(item))
    const firstGroupIds = groupIdsList[0]!
    const allGroupsSame = groupIdsList.every((ids) => arraysEqual(ids, firstGroupIds))

    if (allGroupsSame) {
      form.article_group_ids = [...firstGroupIds]
    } else {
      mixedFields.add('article_group_ids')
    }
  }

  // A mixed field nobody touched keeps each item's own value, so it passes.
  function isRequiredTextValid(field: 'order_code_1' | 'article_name'): boolean {
    if (mixedFields.has(field) && !dirtyFields.has(field)) {
      return true
    }

    return form[field].trim().length > 0
  }

  function isManufacturerValid(): boolean {
    if (mixedFields.has('manufacturer_id') && !dirtyFields.has('manufacturer_id')) {
      return true
    }

    return !!form.manufacturer_id && form.manufacturer_id > 0
  }

  function isFormValid(): boolean {
    return (
      isRequiredTextValid('order_code_1') &&
      isRequiredTextValid('article_name') &&
      isManufacturerValid()
    )
  }

  function buildPayload(item: BoughtItemResponse): BoughtItemUpdateRequest {
    return {
      // The version of each item as the list showed it, so an item someone
      // changed meanwhile is refused instead of overwritten.
      expected_edit_version: item.edit_version,
      order_code_1: dirtyFields.has('order_code_1') ? form.order_code_1.trim() : item.order_code_1,
      order_code_2: dirtyFields.has('order_code_2')
        ? form.order_code_2.trim() || null
        : item.order_code_2,
      gtin: dirtyFields.has('gtin') ? form.gtin.trim() || null : item.gtin,
      ean: dirtyFields.has('ean') ? form.ean.trim() || null : item.ean,
      tariff_number: dirtyFields.has('tariff_number')
        ? form.tariff_number.trim() || null
        : item.tariff_number,
      article_name: dirtyFields.has('article_name') ? form.article_name.trim() : item.article_name,
      article_group_ids: dirtyFields.has('article_group_ids')
        ? form.article_group_ids
        : articleGroupIds(item),
      status: dirtyFields.has('status') ? (form.status ?? item.status) : item.status,
      part_number: dirtyFields.has('part_number')
        ? form.part_number.trim() || null
        : item.part_number,
      mass: dirtyFields.has('mass') ? form.mass : item.mass,
      note: dirtyFields.has('note') ? form.note.trim() || null : item.note,
      weblink: dirtyFields.has('weblink') ? form.weblink.trim() || null : item.weblink,
      manufacturer_id: dirtyFields.has('manufacturer_id')
        ? (form.manufacturer_id as number)
        : item.manufacturer_id,
      product_family_id: dirtyFields.has('product_family_id')
        ? form.product_family_id
        : (item.product_family_id ?? null),
      successor_item_id: dirtyFields.has('successor_item_id')
        ? form.successor_item_id
        : item.successor_item_id,
      ...tolerancesToSave(form, item, dirtyFields),
    }
  }

  return {
    form,
    mixedFields,
    dirtyFields,
    markDirty,
    placeholderFor,
    fillFromSelection,
    isFormValid,
    buildPayload,
  }
}
