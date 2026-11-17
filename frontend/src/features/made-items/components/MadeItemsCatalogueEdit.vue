<script setup lang="ts">
import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { computed, reactive, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useArticleGroupsStore } from '@/features/article-groups'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'
import { getMadeItems } from '../api/getMadeItems'
import { useMadeItemsStore } from '../stores/madeItemsStore'
import { useMadeItemsCatalogueEditStore } from '../stores/madeItemsCatalogueEditStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import MaterialSourceSelect from './MaterialSourceSelect.vue'

import type { MadeItemDataSource, MadeItemUpdateRequest } from '../types/madeItemsRequest'
import type { MadeItemCatalogueStatus, MadeItemResponse } from '../types/madeItemsResponse'
import type { MaterialSource } from '../types/materialSource'
import { useSuccessorItem } from '@/shared/composables/useSuccessorItem'
import { useCadClaimGuard } from '@/shared/composables/useCadClaimGuard'
import CadClaimDialog from '@/shared/components/items/CadClaimDialog.vue'
import { labelName, localizeLabel } from '@/shared/utils/localizeLabel'

const { t } = useI18n()

const madeItemsStore = useMadeItemsStore()
const editStore = useMadeItemsCatalogueEditStore()
const articleGroupsStore = useArticleGroupsStore()
const hostStore = useHostStore()

// Archived article groups stay selectable, sorted last.
const { sortedOptions: articleGroupOptions, isArchived: isArticleGroupArchived } =
  useArchivableOptions(computed(() => articleGroupsStore.items))
const selectedArticleGroups = computed(() =>
  articleGroupsStore.items.filter((g) => form.article_group_ids.includes(g.id)),
)

const DATA_SOURCE_OPTIONS: MadeItemDataSource[] = ['WEB', 'CAD']
const STATUS_OPTIONS: MadeItemCatalogueStatus[] = ['active', 'inactive', 'replaced']

interface MadeItemEditFormState {
  article_name: string
  article_group_ids: number[]
  data_source: MadeItemDataSource | null
  status: MadeItemCatalogueStatus | null
  part_number: string
  material: string
  mass: number | null
  base_size: string
  note: string
  weblink: string
  materialSource: MaterialSource
  successor_item_id: number | null
}

type EditFieldKey = keyof MadeItemEditFormState

function createEmptyForm(): MadeItemEditFormState {
  return {
    article_name: '',
    article_group_ids: [],
    data_source: null,
    status: null,
    part_number: '',
    material: '',
    mass: null,
    base_size: '',
    note: '',
    weblink: '',
    materialSource: { bought_item_id: null, source_item_id: null, made_item_id: null },
    successor_item_id: null,
  }
}

const form = reactive(createEmptyForm())

// Fields with differing values across the selection that the user has not
// edited yet.
const mixedFields = reactive(new Set<EditFieldKey>())

// Only edited fields overwrite the selected items.
const dirtyFields = reactive(new Set<EditFieldKey>())

const { submitting, errorMessage, run } = useSubmitAction()

const {
  successorItem,
  successorSuggestions,
  resolveSuccessorItem,
  searchSuccessorItems,
} = useSuccessorItem<MadeItemResponse>({
  getById: (id) => madeItemsStore.getById(id),
  list: (params) => getMadeItems(params),
})

const selectedItems = computed(() => editStore.selectedItems)

function articleGroupIds(item: MadeItemResponse): number[] {
  return (item.article_groups ?? []).map((group) => group.id).sort((a, b) => a - b)
}

function arraysEqual(a: number[], b: number[]): boolean {
  return a.length === b.length && a.every((value, index) => value === b[index])
}

function onSuccessorItemSelect(item: MadeItemResponse | null): void {
  form.successor_item_id = item?.id ?? null
  markDirty('successor_item_id')
}

function applyFieldFromSelection<K extends EditFieldKey>(
  field: K,
  items: MadeItemResponse[],
  getter: (item: MadeItemResponse) => MadeItemEditFormState[K],
  emptyValue: MadeItemEditFormState[K],
): void {
  const first = getter(items[0]!)
  const allSame = items.every((item) => getter(item) === first)

  if (allSame) {
    form[field] = first
  } else {
    form[field] = emptyValue
    mixedFields.add(field)
  }
}

function resetFormFromSelection(items: MadeItemResponse[]): void {
  dirtyFields.clear()
  mixedFields.clear()
  errorMessage.value = null

  Object.assign(form, createEmptyForm())

  if (items.length === 0) {
    return
  }

  applyFieldFromSelection('article_name', items, (item) => item.article_name, '')
  applyFieldFromSelection(
    'data_source',
    items,
    (item) => item.data_source as MadeItemDataSource,
    null,
  )
  applyFieldFromSelection('status', items, (item) => item.status, null)
  applyFieldFromSelection('part_number', items, (item) => item.part_number ?? '', '')
  applyFieldFromSelection('material', items, (item) => item.material ?? '', '')
  applyFieldFromSelection('mass', items, (item) => item.mass, null)
  applyFieldFromSelection('base_size', items, (item) => item.base_size ?? '', '')
  applyFieldFromSelection('note', items, (item) => item.note ?? '', '')
  applyFieldFromSelection('weblink', items, (item) => item.weblink ?? '', '')
  applyFieldFromSelection('successor_item_id', items, (item) => item.successor_item_id, null)
  resolveSuccessorItem(mixedFields.has('successor_item_id') ? null : form.successor_item_id)

  const allSameMaterialSource = items.every(
    (item) =>
      item.bought_item_id === items[0]!.bought_item_id &&
      item.source_item_id === items[0]!.source_item_id,
  )
  if (allSameMaterialSource) {
    form.materialSource = {
      bought_item_id: items[0]!.bought_item_id,
      source_item_id: items[0]!.source_item_id,
      made_item_id: null,
    }
  } else {
    form.materialSource = { bought_item_id: null, source_item_id: null, made_item_id: null }
    mixedFields.add('materialSource')
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

watch(selectedItems, (items) => resetFormFromSelection(items), { immediate: true })

const cadClaim = useCadClaimGuard()
cadClaim.guardSelection(editStore)

watch(
  () => editStore.editMode,
  (isEditMode) => {
    if (!isEditMode) {
      return
    }

    if (articleGroupsStore.items.length === 0) {
      void articleGroupsStore.refresh()
    }
  },
  { immediate: true },
)

function markDirty(field: EditFieldKey): void {
  dirtyFields.add(field)
  mixedFields.delete(field)
}

function placeholderFor(field: EditFieldKey, fallback?: string): string | undefined {
  if (mixedFields.has(field) && !dirtyFields.has(field)) {
    return t('madeItems.edit.multipleValues')
  }

  return fallback
}

function isRequiredTextValid(field: 'article_name'): boolean {
  if (mixedFields.has(field) && !dirtyFields.has(field)) {
    return true
  }

  return form[field].trim().length > 0
}

function isFormValid(): boolean {
  return isRequiredTextValid('article_name')
}

// A field locks for the whole batch when any selected WEB item needs a new
// revision for it, since submitting it would 409 for those rows.
const fieldPolicyMap = computed(() => {
  const map = new Map<string, boolean>()
  for (const entry of hostStore.madeItemPartNumbers.revision.field_policy) {
    map.set(entry.field, entry.web_requires_revision)
  }
  return map
})

const selectionHasWebItem = computed(() =>
  selectedItems.value.some((item) => item.data_source === 'WEB'),
)

function isFieldLocked(field: string): boolean {
  if (!selectionHasWebItem.value) return false
  return fieldPolicyMap.value.get(field) === true
}

// Per-item variant for the mixed-selection check and the save backstop.
function itemFieldLocked(item: MadeItemResponse, field: string): boolean {
  if (item.data_source !== 'WEB') return false
  return fieldPolicyMap.value.get(field) === true
}

// MaterialSourceSelect handles a single locked field itself. This lock
// covers both fields locked, and mixed selections where the shared value is
// blank and hides the per-item values; then it locks whenever any item has
// a locked kind set.
const selectionHasSetFlaggedMaterialSource = computed(() =>
  selectedItems.value.some(
    (item) =>
      (itemFieldLocked(item, 'bought_item_id') && item.bought_item_id !== null) ||
      (itemFieldLocked(item, 'source_item_id') && item.source_item_id !== null),
  ),
)

const materialSourceLocked = computed(() => {
  if (isFieldLocked('bought_item_id') && isFieldLocked('source_item_id')) return true
  return mixedFields.has('materialSource') && selectionHasSetFlaggedMaterialSource.value
})

const materialSourceFieldLocks = computed(() => ({
  bought: isFieldLocked('bought_item_id'),
  source: isFieldLocked('source_item_id'),
}))

const MAPPED_POLICY_FIELDS = [
  'article_name',
  'material',
  'mass',
  'base_size',
  'note',
  'weblink',
  'article_group_ids',
] as const

const anyFieldLocked = computed(
  () => MAPPED_POLICY_FIELDS.some((field) => isFieldLocked(field)) || materialSourceLocked.value,
)

function buildPayload(item: MadeItemResponse): MadeItemUpdateRequest {
  return {
    // The version of each item as the list showed it, so an item someone
    // changed meanwhile is refused instead of overwritten.
    expected_edit_version: item.edit_version,
    article_name: dirtyFields.has('article_name') ? form.article_name.trim() : item.article_name,
    article_group_ids: dirtyFields.has('article_group_ids')
      ? form.article_group_ids
      : articleGroupIds(item),
    status: dirtyFields.has('status') ? (form.status ?? item.status) : item.status,
    part_number: dirtyFields.has('part_number')
      ? form.part_number.trim() || null
      : item.part_number,
    material: dirtyFields.has('material') ? form.material.trim() || null : item.material,
    mass: dirtyFields.has('mass') ? form.mass : item.mass,
    base_size: dirtyFields.has('base_size') ? form.base_size.trim() || null : item.base_size,
    note: dirtyFields.has('note') ? form.note.trim() || null : item.note,
    weblink: dirtyFields.has('weblink') ? form.weblink.trim() || null : item.weblink,
    bought_item_id: dirtyFields.has('materialSource')
      ? form.materialSource.bought_item_id
      : item.bought_item_id,
    source_item_id: dirtyFields.has('materialSource')
      ? form.materialSource.source_item_id
      : item.source_item_id,
    successor_item_id: dirtyFields.has('successor_item_id')
      ? form.successor_item_id
      : item.successor_item_id,
    // Customer data is per item, so a bulk edit carries it through unchanged.
    customer_id: item.customer_id,
    customer_part_number: item.customer_part_number,
    customer_revision: item.customer_revision,
  }
}

// Save backstop, only relevant when a new material source is staged. Checked
// per item, since only WEB items with the field locked are protected.
function materialSourceViolatesPolicyFor(item: MadeItemResponse): boolean {
  if (!dirtyFields.has('materialSource')) return false
  if (itemFieldLocked(item, 'bought_item_id') && item.bought_item_id !== form.materialSource.bought_item_id) {
    return true
  }
  if (itemFieldLocked(item, 'source_item_id') && item.source_item_id !== form.materialSource.source_item_id) {
    return true
  }
  return false
}

async function onSubmit(): Promise<void> {
  if (selectedItems.value.length === 0) {
    return
  }

  if (!isFormValid()) {
    errorMessage.value = t('madeItems.edit.errors.required')

    return
  }

  if (selectedItems.value.some((item) => materialSourceViolatesPolicyFor(item))) {
    errorMessage.value = t('madeItems.edit.fieldPolicy.hint')

    return
  }

  if (!(await cadClaim.confirmSave(selectedItems.value, getMadeItems))) return

  await run(async () => {
    const updated = await Promise.all(
      selectedItems.value.map((item) => madeItemsStore.update(item.id, buildPayload(item))),
    )

    madeItemsStore.replaceItems(updated)
    editStore.setSelectedItems(updated)
  }, t('madeItems.edit.errors.unknown'))
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
        <span class="panel-title">{{ t('madeItems.edit.title') }}</span>
        <Tag
          v-if="selectedItems.length > 0"
          :value="t('madeItems.edit.selectionSummary', { count: selectedItems.length })"
          severity="secondary"
        />
      </div>
    </template>

    <Message v-if="selectedItems.length === 0" severity="info" :closable="false">
      {{ t('madeItems.edit.noSelection') }}
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

      <!-- Bulk edit has no single item to make a revision from, so no button. -->
      <Message v-if="anyFieldLocked" severity="info" :closable="false">
        {{ t('madeItems.edit.fieldPolicy.hint') }}
      </Message>

      <div class="form-fields">
        <div class="field">
          <label id="mie-status-label" for="mie-status">{{ t('madeItems.edit.fields.status') }}</label>
          <Select
            id="mie-status"
            aria-labelledby="mie-status-label"
            v-model="form.status"
            :options="STATUS_OPTIONS"
            :option-label="(s) => t(`madeItems.catalogue.status.${s}`)"
            :placeholder="placeholderFor('status')"
            fluid
            @update:model-value="markDirty('status')"
          />
        </div>

        <div v-if="form.status === 'replaced'" class="field">
          <label for="mie-successor-item">
            {{ t('madeItems.edit.fields.successorItemId') }}
          </label>
          <AutoComplete
            id="mie-successor-item"
            v-model="successorItem"
            :suggestions="successorSuggestions"
            :option-label="(item) => `#${item.id}: ${item.article_name}`"
            :placeholder="
              placeholderFor(
                'successor_item_id',
                t('madeItems.edit.fields.successorItemPlaceholder'),
              )
            "
            force-selection
            fluid
            @complete="searchSuccessorItems"
            @update:model-value="onSuccessorItemSelect"
          />
        </div>

        <div class="field">
          <label for="mie-article-name">{{ t('madeItems.edit.fields.articleName') }} *</label>
          <InputText
            id="mie-article-name"
            v-model="form.article_name"
            :placeholder="placeholderFor('article_name')"
            fluid
            :disabled="isFieldLocked('article_name')"
            @update:model-value="markDirty('article_name')"
          />
        </div>

        <div class="field">
          <label for="mie-part-number">{{ t('madeItems.edit.fields.partNumber') }}</label>
          <InputText
            id="mie-part-number"
            v-model="form.part_number"
            :placeholder="placeholderFor('part_number')"
            fluid
            @update:model-value="markDirty('part_number')"
          />
        </div>

        <div class="field">
          <label for="mie-material">{{ t('madeItems.edit.fields.material') }}</label>
          <InputText
            id="mie-material"
            v-model="form.material"
            :placeholder="placeholderFor('material')"
            fluid
            :disabled="isFieldLocked('material')"
            @update:model-value="markDirty('material')"
          />
        </div>

        <div class="field">
          <label id="mie-article-groups-label" for="mie-article-groups">{{ t('madeItems.edit.fields.articleGroups') }}</label>
          <MultiSelect
            id="mie-article-groups"
            aria-labelledby="mie-article-groups-label"
            v-model="form.article_group_ids"
            :options="articleGroupOptions"
            :option-label="labelName"
            option-value="id"
            :loading="articleGroupsStore.loading"
            :placeholder="
              placeholderFor(
                'article_group_ids',
                t('madeItems.edit.fields.articleGroupsPlaceholder'),
              )
            "
            display="chip"
            filter
            fluid
            :disabled="isFieldLocked('article_group_ids')"
            @update:model-value="markDirty('article_group_ids')"
          >
            <template #option="{ option }">
              <span>{{ localizeLabel(option.name) }}</span>
              <ArchivedOptionTag v-if="option.archived" />
            </template>
          </MultiSelect>
          <ArchivedSelectionWarning v-if="isArticleGroupArchived(selectedArticleGroups)" />
        </div>

        <div class="field">
          <label for="mie-base-size">{{ t('madeItems.edit.fields.baseSize') }}</label>
          <InputText
            id="mie-base-size"
            v-model="form.base_size"
            :placeholder="placeholderFor('base_size')"
            fluid
            :disabled="isFieldLocked('base_size')"
            @update:model-value="markDirty('base_size')"
          />
        </div>

        <div class="field">
          <label for="mie-source-item">{{ t('madeItems.edit.fields.sourceItem') }}</label>
          <div :class="{ 'field-locked': materialSourceLocked }">
            <MaterialSourceSelect
              id="mie-source-item"
              v-model="form.materialSource"
              :locked-fields="materialSourceFieldLocks"
              @update:model-value="markDirty('materialSource')"
            />
          </div>
        </div>

        <div class="field">
          <label for="mie-mass">{{ t('madeItems.edit.fields.mass') }}</label>
          <InputNumber
            id="mie-mass"
            v-model="form.mass"
            :min="0"
            :placeholder="placeholderFor('mass')"
            fluid
            :disabled="isFieldLocked('mass')"
            @update:model-value="markDirty('mass')"
          />
        </div>

        <div class="field">
          <label for="mie-weblink">{{ t('madeItems.edit.fields.weblink') }}</label>
          <InputText
            id="mie-weblink"
            v-model="form.weblink"
            type="url"
            :placeholder="placeholderFor('weblink')"
            fluid
            :disabled="isFieldLocked('weblink')"
            @update:model-value="markDirty('weblink')"
          />
        </div>

        <div class="field">
          <label for="mie-note">{{ t('madeItems.edit.fields.note') }}</label>
          <Textarea
            id="mie-note"
            v-model="form.note"
            rows="3"
            auto-resize
            :placeholder="placeholderFor('note')"
            fluid
            :disabled="isFieldLocked('note')"
            @update:model-value="markDirty('note')"
          />
        </div>

        <div class="field">
          <label id="mie-data-source-label" for="mie-data-source">{{ t('madeItems.edit.fields.dataSource') }}</label>
          <Select
            id="mie-data-source"
            aria-labelledby="mie-data-source-label"
            v-model="form.data_source"
            :options="DATA_SOURCE_OPTIONS"
            :option-label="(source) => t(`madeItems.catalogue.dataSources.${source}`)"
            :placeholder="placeholderFor('data_source')"
            fluid
            disabled
          />
        </div>
      </div>
    </form>

    <CadClaimDialog :guard="cadClaim" />
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

.field-locked {
  opacity: 0.6;
  pointer-events: none;
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
