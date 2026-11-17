import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDebounceFn } from '@vueuse/core'

import { extractApiError } from '@/core/utils/errors'
import { TABLE_DEBOUNCE_MS } from '@/core/constants/table'
import { useSourceItemsStore } from '../stores/sourceItemsStore'
import { sourceItemsApi } from '../api/sourceItemsApi'
import { areDimensionsEquivalent } from '../utils/dimensionSpec'

import type { SourceItemResponse } from '../types/sourceItemsResponse'

export interface SourceItemCreateFormState {
  type_id: number | null
  dimension: string
  material: string
  mass: number | null
  manufacturer_id: number | null
  note: string
  order_code_1: string
  order_code_2: string
}

function createEmptyForm(): SourceItemCreateFormState {
  return {
    type_id: null,
    dimension: '',
    material: '',
    mass: null,
    manufacturer_id: null,
    note: '',
    order_code_1: '',
    order_code_2: '',
  }
}

/**
 * Form state and live duplicate detection for creating a source item, shared
 * by the catalogue create dialog and the inline create pane.
 */
export function useSourceItemCreateForm() {
  const { t } = useI18n()
  const sourceItemsStore = useSourceItemsStore()

  const form = reactive(createEmptyForm())
  const submitting = ref(false)
  const errorMessage = ref<string | null>(null)

  // ── Similar items ────────────────────────────────────────────────────
  // A broad live search, unlike the exact duplicate check below.

  const similarItems = ref<SourceItemResponse[]>([])
  const similarItemsLoading = ref(false)
  const similarItemsSearched = ref(false)

  async function fetchSimilarItems(): Promise<void> {
    const material = form.material.trim()
    const dimension = form.dimension.trim()
    if (form.type_id === null && !material && !dimension) {
      similarItems.value = []
      similarItemsSearched.value = false
      return
    }

    similarItemsLoading.value = true
    similarItemsSearched.value = true

    try {
      const result = await sourceItemsApi.list({
        ...(form.type_id !== null ? { type_id: form.type_id } : {}),
        ...(material ? { material } : {}),
        // Dimension filters the request only without type and material. Otherwise
        // every candidate is needed so duplicateItem can catch a permuted dimension
        // that a substring match would miss.
        ...(!form.type_id && !material && dimension ? { dimension } : {}),
        limit: 50,
      })
      similarItems.value = result.items
    } finally {
      similarItemsLoading.value = false
    }
  }

  const debouncedFetchSimilarItems = useDebounceFn(fetchSimilarItems, TABLE_DEBOUNCE_MS)

  // Every field re-runs the search so typing visibly searches, although only
  // type and material change the request.
  watch(
    () => [form.type_id, form.material, form.dimension, form.manufacturer_id] as const,
    () => debouncedFetchSimilarItems(),
  )

  // Exact match on every spec field, computed client-side.
  const duplicateItem = computed<SourceItemResponse | null>(() => {
    const material = form.material.trim()
    if (form.type_id === null || !material) return null

    return (
      similarItems.value.find(
        (item) =>
          item.type_id === form.type_id &&
          item.material === material &&
          item.manufacturer_id === (form.manufacturer_id ?? null) &&
          areDimensionsEquivalent(item.dimension, form.dimension),
      ) ?? null
    )
  })

  const sortedSimilarItems = computed<SourceItemResponse[]>(() => {
    const duplicateId = duplicateItem.value?.id
    if (duplicateId === undefined) return similarItems.value
    return [...similarItems.value].sort((a, b) =>
      a.id === duplicateId ? -1 : b.id === duplicateId ? 1 : 0,
    )
  })

  function resetForm(): void {
    Object.assign(form, createEmptyForm())
    errorMessage.value = null
    similarItems.value = []
    similarItemsSearched.value = false
  }

  function isFormValid(): boolean {
    return (
      form.dimension.trim().length > 0 && form.type_id !== null && form.material.trim().length > 0
    )
  }

  async function submit(): Promise<SourceItemResponse | null> {
    if (duplicateItem.value) return null

    if (!isFormValid() || form.type_id === null) {
      errorMessage.value = t('sourceItems.create.errors.required')
      return null
    }

    submitting.value = true
    errorMessage.value = null

    try {
      return await sourceItemsStore.create({
        status: 'active',
        note: form.note.trim() || null,
        type_id: form.type_id,
        dimension: form.dimension.trim() || null,
        material: form.material.trim(),
        mass: form.mass,
        manufacturer_id: form.manufacturer_id,
        order_code_1: form.order_code_1.trim() || null,
        order_code_2: form.order_code_2.trim() || null,
      })
    } catch (e) {
      errorMessage.value = extractApiError(e) ?? t('sourceItems.create.errors.unknown')
      return null
    } finally {
      submitting.value = false
    }
  }

  return {
    form,
    submitting,
    errorMessage,
    similarItems,
    similarItemsLoading,
    similarItemsSearched,
    duplicateItem,
    sortedSimilarItems,
    resetForm,
    isFormValid,
    submit,
  }
}
