<script setup lang="ts">
import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { computed, reactive, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useSuppliersStore } from '@/features/suppliers'
import { useSourceItemTypesStore } from '@/features/source-item-types'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'
import { sourceItemsApi } from '../api/sourceItemsApi'
import { useSourceItemsStore } from '../stores/sourceItemsStore'
import { useSourceItemsCatalogueEditStore } from '../stores/sourceItemsCatalogueEditStore'
import { SOURCE_ITEM_STATUS_OPTIONS } from '../stores/sourceItemsCatalogueColumnsStore'

import type { SourceItemUpdateRequest } from '../types/sourceItemsRequest'
import type { SourceItemCatalogueStatus, SourceItemResponse } from '../types/sourceItemsResponse'
import { useSuccessorItem } from '@/shared/composables/useSuccessorItem'
import { useSelectionEdit } from '@/shared/composables/useSelectionEdit'
import {
  TOLERANCE_FIELDS,
  TOLERANCE_INPUT_PROPS,
  TOLERANCE_LABEL_KEYS,
  emptyTolerances,
  tolerancesOf,
  tolerancesToSave,
  type ToleranceValues,
} from '@/shared/utils/deliveryTolerance'
import { labelName, localizeLabel } from '@/shared/utils/localizeLabel'

const { t } = useI18n()

const sourceItemsStore = useSourceItemsStore()
const editStore = useSourceItemsCatalogueEditStore()
const suppliersStore = useSuppliersStore()
const sourceItemTypesStore = useSourceItemTypesStore()

interface SourceItemEditFormState extends ToleranceValues {
  type_id: number | null
  dimension: string
  material: string
  mass: number | null
  note: string
  order_code_1: string
  order_code_2: string
  status: SourceItemCatalogueStatus | null
  manufacturer_id: number | null
  successor_item_id: number | null
}

function createEmptyForm(): SourceItemEditFormState {
  return {
    type_id: null,
    dimension: '',
    material: '',
    mass: null,
    note: '',
    order_code_1: '',
    order_code_2: '',
    status: null,
    manufacturer_id: null,
    successor_item_id: null,
    ...emptyTolerances(),
  }
}

const form = reactive(createEmptyForm())

// Archived suppliers and types stay selectable, sorted last.
const { sortedOptions: supplierOptions, isArchived: isSupplierArchived } = useArchivableOptions(
  computed(() => suppliersStore.items),
)
const selectedSupplier = computed(
  () => suppliersStore.getById(form.manufacturer_id) ?? null,
)
const { sortedOptions: typeOptions, isArchived: isTypeArchived } = useArchivableOptions(
  computed(() => sourceItemTypesStore.items),
)
const selectedType = computed(
  () => sourceItemTypesStore.getById(form.type_id) ?? null,
)

const { mixedFields, dirtyFields, applyFieldFromSelection, markDirty, placeholderFor, clearFields } =
  useSelectionEdit<SourceItemEditFormState, SourceItemResponse>(form, () =>
    t('sourceItems.edit.multipleValues'),
  )

const { submitting, errorMessage, run } = useSubmitAction()

const {
  successorItem,
  successorSuggestions,
  resolveSuccessorItem,
  searchSuccessorItems,
} = useSuccessorItem<SourceItemResponse>({
  getById: (id) => sourceItemsStore.getById(id),
  list: (params) => sourceItemsApi.list(params),
})

const selectedItems = computed(() => editStore.selectedItems)

function onSuccessorItemSelect(item: SourceItemResponse | null): void {
  form.successor_item_id = item?.id ?? null
  markDirty('successor_item_id')
}

function resetFormFromSelection(items: SourceItemResponse[]): void {
  clearFields()
  errorMessage.value = null

  Object.assign(form, createEmptyForm())

  if (items.length === 0) {
    return
  }

  applyFieldFromSelection('type_id', items, (item) => item.type_id, null)
  applyFieldFromSelection('dimension', items, (item) => item.dimension ?? '', '')
  applyFieldFromSelection('material', items, (item) => item.material, '')
  applyFieldFromSelection('mass', items, (item) => item.mass, null)
  applyFieldFromSelection('note', items, (item) => item.note ?? '', '')
  applyFieldFromSelection('order_code_1', items, (item) => item.order_code_1 ?? '', '')
  applyFieldFromSelection('order_code_2', items, (item) => item.order_code_2 ?? '', '')
  applyFieldFromSelection('status', items, (item) => item.status, null)
  applyFieldFromSelection('manufacturer_id', items, (item) => item.manufacturer_id, null)
  applyFieldFromSelection('successor_item_id', items, (item) => item.successor_item_id, null)
  for (const field of TOLERANCE_FIELDS) {
    applyFieldFromSelection(field, items, (item) => tolerancesOf(item, field), null)
  }
  resolveSuccessorItem(mixedFields.has('successor_item_id') ? null : form.successor_item_id)
}

watch(selectedItems, (items) => resetFormFromSelection(items), { immediate: true })

watch(
  () => editStore.editMode,
  (isEditMode) => {
    if (!isEditMode) {
      return
    }

    if (suppliersStore.items.length === 0) {
      void suppliersStore.refresh()
    }

    if (sourceItemTypesStore.items.length === 0) {
      void sourceItemTypesStore.refresh()
    }
  },
  { immediate: true },
)

function buildPayload(item: SourceItemResponse): SourceItemUpdateRequest {
  return {
    // The version of each item as the list showed it, so an item someone
    // changed meanwhile is refused instead of overwritten.
    expected_edit_version: item.edit_version,
    type_id: dirtyFields.has('type_id') && form.type_id !== null ? form.type_id : item.type_id,
    dimension: dirtyFields.has('dimension') ? form.dimension.trim() || null : item.dimension,
    material: dirtyFields.has('material') ? form.material.trim() : item.material,
    mass: dirtyFields.has('mass') ? form.mass : item.mass,
    note: dirtyFields.has('note') ? form.note.trim() || null : item.note,
    order_code_1: dirtyFields.has('order_code_1')
      ? form.order_code_1.trim() || null
      : item.order_code_1,
    order_code_2: dirtyFields.has('order_code_2')
      ? form.order_code_2.trim() || null
      : item.order_code_2,
    status: dirtyFields.has('status') ? (form.status ?? item.status) : item.status,
    manufacturer_id: dirtyFields.has('manufacturer_id')
      ? form.manufacturer_id
      : item.manufacturer_id,
    successor_item_id: dirtyFields.has('successor_item_id')
      ? form.successor_item_id
      : item.successor_item_id,
    ...tolerancesToSave(form, item, dirtyFields),
  }
}

async function onSubmit(): Promise<void> {
  if (selectedItems.value.length === 0) {
    return
  }

  await run(async () => {
    const updated = await Promise.all(
      selectedItems.value.map((item) => sourceItemsStore.update(item.id, buildPayload(item))),
    )

    sourceItemsStore.replaceItems(updated)
    editStore.setSelectedItems(updated)
  }, t('sourceItems.edit.errors.unknown'))
}

function onCancel(): void {
  resetFormFromSelection(selectedItems.value)
}

function onClear(): void {
  editStore.setSelectedItems([])
}
</script>

<template>
  <Panel v-if="editStore.editMode" class="edit-panel">
    <template #header>
      <div class="panel-header-row">
        <span class="panel-title">{{ t('sourceItems.edit.title') }}</span>
        <Tag
          v-if="selectedItems.length > 0"
          :value="t('sourceItems.edit.selectionSummary', { count: selectedItems.length })"
          severity="secondary"
        />
      </div>
    </template>

    <Message v-if="selectedItems.length === 0" severity="info" :closable="false">
      {{ t('sourceItems.edit.noSelection') }}
    </Message>

    <form v-else class="edit-form" @submit.prevent="onSubmit">
      <div class="form-actions">
        <Button type="submit" :label="t('common.save')" :loading="submitting" />
        <Button
          type="button"
          :label="t('common.cancel')"
          severity="secondary"
          outlined
          :disabled="submitting"
          @click="onCancel"
        />
        <Button
          type="button"
          :label="t('common.clearSelection')"
          severity="secondary"
          outlined
          :disabled="submitting"
          @click="onClear"
        />
      </div>

      <Message v-if="errorMessage" severity="error" :closable="false">
        {{ errorMessage }}
      </Message>

      <div class="form-fields">
        <div class="field">
          <label id="bie-status-label" for="bie-status">{{ t('sourceItems.edit.fields.status') }}</label>
          <Select
            id="bie-status"
            aria-labelledby="bie-status-label"
            v-model="form.status"
            :options="SOURCE_ITEM_STATUS_OPTIONS"
            :option-label="(s) => t(`sourceItems.catalogue.status.${s}`)"
            :placeholder="placeholderFor('status')"
            fluid
            @update:model-value="markDirty('status')"
          />
        </div>

        <div v-if="form.status === 'replaced'" class="field">
          <label for="bie-successor-item">{{ t('sourceItems.edit.fields.successorItemId') }}</label>
          <AutoComplete
            id="bie-successor-item"
            v-model="successorItem"
            :suggestions="successorSuggestions"
            :option-label="(item) => `#${item.id}`"
            :placeholder="
              placeholderFor(
                'successor_item_id',
                t('sourceItems.edit.fields.successorItemPlaceholder'),
              )
            "
            force-selection
            fluid
            @complete="searchSuccessorItems"
            @update:model-value="onSuccessorItemSelect"
          />
        </div>

        <div class="field">
          <label id="bie-type-label" for="bie-type">{{ t('sourceItems.edit.fields.type') }}</label>
          <Select
            id="bie-type"
            aria-labelledby="bie-type-label"
            v-model="form.type_id"
            :options="typeOptions"
            :option-label="labelName"
            option-value="id"
            :loading="sourceItemTypesStore.loading"
            :placeholder="placeholderFor('type_id', t('sourceItems.edit.fields.typePlaceholder'))"
            filter
            fluid
            @update:model-value="markDirty('type_id')"
          >
            <template #option="{ option }">
              <span>{{ localizeLabel(option.name) }}</span>
              <ArchivedOptionTag v-if="option.archived" />
            </template>
            <template #value="{ value }">
              <span v-if="value">{{ localizeLabel(selectedType?.name) }}</span>
              <ArchivedOptionTag v-if="selectedType?.archived" />
            </template>
          </Select>
          <ArchivedSelectionWarning v-if="isTypeArchived(selectedType)" />
        </div>

        <div class="field">
          <label for="bie-dimension">{{ t('sourceItems.edit.fields.dimension') }}</label>
          <InputText
            id="bie-dimension"
            v-model="form.dimension"
            :placeholder="placeholderFor('dimension')"
            fluid
            @update:model-value="markDirty('dimension')"
          />
        </div>

        <div class="field">
          <label for="bie-material">{{ t('sourceItems.edit.fields.material') }}</label>
          <InputText
            id="bie-material"
            v-model="form.material"
            :placeholder="placeholderFor('material')"
            fluid
            @update:model-value="markDirty('material')"
          />
        </div>

        <div class="field">
          <label for="bie-mass">{{ t('sourceItems.edit.fields.mass') }}</label>
          <InputNumber
            id="bie-mass"
            v-model="form.mass"
            :min="0"
            :placeholder="placeholderFor('mass')"
            fluid
            @update:model-value="markDirty('mass')"
          />
        </div>

        <div v-for="field in TOLERANCE_FIELDS" :key="field" class="field">
          <label :for="`sie-${field}`">{{ t(TOLERANCE_LABEL_KEYS[field]) }}</label>
          <InputNumber
            :id="`sie-${field}`"
            v-model="form[field]"
            v-bind="TOLERANCE_INPUT_PROPS"
            :placeholder="placeholderFor(field, t('common.deliveryTolerance.global'))"
            fluid
            @update:model-value="markDirty(field)"
          />
        </div>

        <div class="field">
          <label for="bie-order-code-1">{{ t('sourceItems.edit.fields.orderCode1') }}</label>
          <InputText
            id="bie-order-code-1"
            v-model="form.order_code_1"
            :placeholder="placeholderFor('order_code_1')"
            fluid
            @update:model-value="markDirty('order_code_1')"
          />
        </div>

        <div class="field">
          <label for="bie-order-code-2">{{ t('sourceItems.edit.fields.orderCode2') }}</label>
          <InputText
            id="bie-order-code-2"
            v-model="form.order_code_2"
            :placeholder="placeholderFor('order_code_2')"
            fluid
            @update:model-value="markDirty('order_code_2')"
          />
        </div>

        <div class="field">
          <label id="bie-manufacturer-label" for="bie-manufacturer">{{ t('sourceItems.edit.fields.manufacturer') }}</label>
          <Select
            id="bie-manufacturer"
            aria-labelledby="bie-manufacturer-label"
            v-model="form.manufacturer_id"
            :options="supplierOptions"
            option-label="name"
            option-value="id"
            :loading="suppliersStore.loading"
            :placeholder="
              placeholderFor(
                'manufacturer_id',
                t('sourceItems.edit.fields.manufacturerPlaceholder'),
              )
            "
            filter
            show-clear
            fluid
            @update:model-value="markDirty('manufacturer_id')"
          >
            <template #option="{ option }">
              <span>{{ option.name }}</span>
              <ArchivedOptionTag v-if="option.archived" />
            </template>
            <template #value="{ value }">
              <span v-if="value">{{ selectedSupplier?.name }}</span>
              <ArchivedOptionTag v-if="selectedSupplier?.archived" />
            </template>
          </Select>
          <ArchivedSelectionWarning v-if="isSupplierArchived(selectedSupplier)" />
        </div>

        <div class="field">
          <label for="bie-note">{{ t('sourceItems.edit.fields.note') }}</label>
          <Textarea
            id="bie-note"
            v-model="form.note"
            rows="3"
            auto-resize
            :placeholder="placeholderFor('note')"
            fluid
            @update:model-value="markDirty('note')"
          />
        </div>
      </div>
    </form>
  </Panel>
</template>

<style scoped lang="scss">
.edit-panel {
  flex: 0 0 auto;
  min-width: 28rem;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

:deep(.p-panel-content-container) {
  flex: 1;
  min-height: 0;
}

:deep(.p-panel-content) {
  height: 100%;
  box-sizing: border-box;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
}

.panel-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: var(--space-2);
}

.edit-form {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-width: 0;
}

.form-fields {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-width: 0;
  overflow-y: auto;
  overflow-x: hidden;
}

.field {
  flex-shrink: 0;
  min-width: 0;
  overflow: hidden;
}

.field label {
  color: var(--p-text-color);
}

.field > :deep(.p-component) {
  min-width: 0;
  max-width: 100%;
}

.field :deep(.p-select-label) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.form-actions {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-start;
  gap: var(--space-2);
}
</style>
