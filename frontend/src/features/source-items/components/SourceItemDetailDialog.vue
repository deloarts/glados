<script setup lang="ts">
import { computed, inject, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, routerKey } from 'vue-router'
import { useDebounceFn } from '@vueuse/core'

import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import UserAvatarPreview from '@/shared/components/user/UserAvatarPreview.vue'
import { TABLE_DEBOUNCE_MS } from '@/core/constants/table'
import { useSuppliersStore } from '@/features/suppliers'
import { useSourceItemTypesStore } from '@/features/source-item-types'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'
import { sourceItemsApi } from '../api/sourceItemsApi'
import { useSourceItemsStore } from '../stores/sourceItemsStore'
import SourceItemDetailFields from './SourceItemDetailFields.vue'
import SourceItemDimensionInput from './SourceItemDimensionInput.vue'
import { SOURCE_ITEM_STATUS_OPTIONS } from '../stores/sourceItemsCatalogueColumnsStore'
import { areDimensionsEquivalent } from '../utils/dimensionSpec'
import SourceItemFilesSection from './SourceItemFilesSection.vue'
import SourceItemPicturesSection from './SourceItemPicturesSection.vue'
import { useHostStore } from '@/core/host/stores/hostStore'

import type { SourceItemUpdateRequest } from '../types/sourceItemsRequest'
import type { SourceItemCatalogueStatus, SourceItemResponse } from '../types/sourceItemsResponse'
import { useSuccessorItem } from '@/shared/composables/useSuccessorItem'
import { labelName, localizeLabel } from '@/shared/utils/localizeLabel'

const props = withDefaults(
  defineProps<{
    item: SourceItemResponse | null
    editOnOpen?: boolean
  }>(),
  { editOnOpen: false },
)

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
// Injected with a default, since the dialog also mounts without a router;
// the open-in-page link then simply does not render.
const router = inject(routerKey, null)

const sourceItemsStore = useSourceItemsStore()
const suppliersStore = useSuppliersStore()
const sourceItemTypesStore = useSourceItemTypesStore()
const hostStore = useHostStore()

const displayItem = ref<SourceItemResponse | null>(props.item)
const editing = ref(false)

watch(
  () => props.item,
  (item) => {
    displayItem.value = item
  },
)

watch(visible, (isVisible) => {
  if (!isVisible) {
    editing.value = false
    similarItems.value = []
    return
  }
  displayItem.value = props.item
  if (props.editOnOpen) onEdit()
})

function closeAndNavigate(navigate: (event: MouseEvent) => void, event: MouseEvent): void {
  visible.value = false
  navigate(event)
}

// ── Edit ────────────────────────────────────────────────────────────────

interface EditFormState {
  type_id: number | null
  dimension: string
  material: string
  mass: number | null
  manufacturer_id: number | null
  note: string
  order_code_1: string
  order_code_2: string
  status: SourceItemCatalogueStatus
  successor_item_id: number | null
}

const form = reactive<EditFormState>({
  type_id: null,
  dimension: '',
  material: '',
  mass: null,
  manufacturer_id: null,
  note: '',
  order_code_1: '',
  order_code_2: '',
  status: 'active',
  successor_item_id: null,
})

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

function onSuccessorItemSelect(selected: SourceItemResponse | null): void {
  form.successor_item_id = selected?.id ?? null
}

// ── Live duplicate detection ───────────────────────────────────────────
// Save is disabled as soon as the edited fields match another item. The
// edited item never matches itself.

const similarItems = ref<SourceItemResponse[]>([])

async function fetchSimilarItems(): Promise<void> {
  const material = form.material.trim()
  const dimension = form.dimension.trim()
  if (form.type_id === null && !material && !dimension) {
    similarItems.value = []
    return
  }

  // The list is only a hint while editing, so a failed lookup empties it
  // instead of interrupting the edit.
  try {
    const result = await sourceItemsApi.list({
      ...(form.type_id !== null ? { type_id: form.type_id } : {}),
      ...(material ? { material } : {}),
      ...(!form.type_id && !material && dimension ? { dimension } : {}),
      limit: 50,
    })
    similarItems.value = result.items
  } catch {
    similarItems.value = []
  }
}

const debouncedFetchSimilarItems = useDebounceFn(fetchSimilarItems, TABLE_DEBOUNCE_MS)

watch(
  () => [form.type_id, form.material, form.dimension, form.manufacturer_id] as const,
  () => {
    if (editing.value) void debouncedFetchSimilarItems()
  },
)

const duplicateItem = computed<SourceItemResponse | null>(() => {
  const material = form.material.trim()
  if (form.type_id === null || !material) return null
  const currentId = displayItem.value?.id

  return (
    similarItems.value.find(
      (item) =>
        item.id !== currentId &&
        item.type_id === form.type_id &&
        item.material === material &&
        item.manufacturer_id === (form.manufacturer_id ?? null) &&
        areDimensionsEquivalent(item.dimension, form.dimension),
    ) ?? null
  )
})

function onEdit(): void {
  const item = displayItem.value
  if (!item) return

  form.type_id = item.type_id
  form.dimension = item.dimension ?? ''
  form.material = item.material
  form.mass = item.mass
  form.manufacturer_id = item.manufacturer_id
  form.note = item.note ?? ''
  form.order_code_1 = item.order_code_1 ?? ''
  form.order_code_2 = item.order_code_2 ?? ''
  form.status = item.status
  form.successor_item_id = item.successor_item_id
  resolveSuccessorItem(item.successor_item_id)

  errorMessage.value = null
  if (suppliersStore.items.length === 0) void suppliersStore.refresh()
  if (sourceItemTypesStore.items.length === 0) void sourceItemTypesStore.refresh()
  editing.value = true
}

function onCancelEdit(): void {
  editing.value = false
  errorMessage.value = null
  similarItems.value = []
}

function buildPayload(item: SourceItemResponse): SourceItemUpdateRequest {
  return {
    expected_edit_version: item.edit_version,
    status: form.status,
    note: form.note.trim() || null,
    type_id: form.type_id!,
    dimension: form.dimension.trim() || null,
    material: form.material.trim(),
    mass: form.mass,
    manufacturer_id: form.manufacturer_id,
    order_code_1: form.order_code_1.trim() || null,
    order_code_2: form.order_code_2.trim() || null,
    successor_item_id: form.successor_item_id,
  }
}

async function onSave(): Promise<void> {
  const item = displayItem.value
  if (!item || duplicateItem.value) return

  await run(async () => {
    const updated = await sourceItemsStore.update(item.id, buildPayload(item))
    sourceItemsStore.replaceItems([updated])
    displayItem.value = updated
    editing.value = false
    similarItems.value = []
  }, t('sourceItems.edit.errors.unknown'))
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="displayItem ? `#${displayItem.id}` : ''"
    :style="{ width: 'var(--dialog-width-lg)' }"
  >
    <!-- Replaces the native close button, since OpenVue has no slot for an
         extra header icon. RouterLink is imported explicitly so router-less
         mounts do not warn about an unresolved component. -->
    <template #closebutton="{ closeCallback }">
      <RouterLink
        v-if="router && displayItem"
        v-slot="{ navigate }"
        :to="`/catalogue/source-items/${displayItem.id}`"
        custom
      >
        <Button
          icon="mdi mdi-open-in-new"
          size="small"
          severity="secondary"
          text
          rounded
          v-tooltip.bottom.focus="t('sourceItems.catalogue.page.open')"
          :aria-label="t('sourceItems.catalogue.page.open')"
          @click="closeAndNavigate(navigate, $event)"
        />
      </RouterLink>
      <Button
        icon="mdi mdi-close"
        size="small"
        severity="secondary"
        text
        rounded
        v-tooltip.bottom.focus="t('common.close')"
        :aria-label="t('common.close')"
        @click="closeCallback"
      />
    </template>

    <div v-if="displayItem" class="detail-layout">
      <template v-if="!editing">
        <SourceItemDetailFields :item="displayItem" :show-meta="false" />

        <template v-if="hostStore.storageEnabled && displayItem">
          <Divider />
          <SourceItemPicturesSection :item-id="displayItem.id" readonly />
          <SourceItemFilesSection :item-id="displayItem.id" readonly />
        </template>
      </template>

      <form v-else class="edit-form" @submit.prevent="onSave">
        <Message v-if="errorMessage" severity="error" :closable="false">
          {{ errorMessage }}
        </Message>

        <Message v-if="duplicateItem" severity="warn" :closable="false">
          {{
            t('sourceItems.edit.warnings.duplicateExists', {
              type: localizeLabel(duplicateItem.type_name),
              dimension: duplicateItem.dimension,
              material: duplicateItem.material,
              id: duplicateItem.id,
            })
          }}
        </Message>

        <div class="edit-grid">
          <div class="field">
            <label id="bid-status-label" for="bid-status">{{ t('sourceItems.edit.fields.status') }}</label>
            <Select
              id="bid-status"
              aria-labelledby="bid-status-label"
              v-model="form.status"
              :options="SOURCE_ITEM_STATUS_OPTIONS"
              :option-label="(s) => t(`sourceItems.catalogue.status.${s}`)"
              fluid
            />
          </div>

          <div v-if="form.status === 'replaced'" class="field field-wide">
            <label for="bid-successor-item">{{
              t('sourceItems.edit.fields.successorItemId')
            }}</label>
            <AutoComplete
              id="bid-successor-item"
              v-model="successorItem"
              :suggestions="successorSuggestions"
              :option-label="(i) => `#${i.id}`"
              :placeholder="t('sourceItems.edit.fields.successorItemPlaceholder')"
              force-selection
              fluid
              @complete="searchSuccessorItems"
              @update:model-value="onSuccessorItemSelect"
            />
          </div>

          <div class="field field-wide">
            <label for="bid-dimension">{{ t('sourceItems.edit.fields.dimension') }}</label>
            <SourceItemDimensionInput id="bid-dimension" v-model="form.dimension" />
          </div>
          <div class="field field-wide">
            <label id="bid-type-label" for="bid-type">{{ t('sourceItems.edit.fields.type') }}</label>
            <Select
              id="bid-type"
              aria-labelledby="bid-type-label"
              v-model="form.type_id"
              :options="typeOptions"
              :option-label="labelName"
              option-value="id"
              :loading="sourceItemTypesStore.loading"
              :placeholder="t('sourceItems.create.fields.typePlaceholder')"
              filter
              fluid
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
            <label for="bid-material">{{ t('sourceItems.edit.fields.material') }}</label>
            <InputText id="bid-material" v-model="form.material" fluid />
          </div>
          <div class="field">
            <label for="bid-mass">{{ t('sourceItems.edit.fields.mass') }}</label>
            <InputNumber id="bid-mass" v-model="form.mass" :min="0" fluid />
          </div>
          <div class="field field-wide">
            <label id="bid-manufacturer-label" for="bid-manufacturer">{{ t('sourceItems.edit.fields.manufacturer') }}</label>
            <Select
              id="bid-manufacturer"
              aria-labelledby="bid-manufacturer-label"
              v-model="form.manufacturer_id"
              :options="supplierOptions"
              option-label="name"
              option-value="id"
              :loading="suppliersStore.loading"
              :placeholder="t('sourceItems.edit.fields.manufacturerPlaceholder')"
              filter
              show-clear
              fluid
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
            <label for="bid-order-code-1">{{ t('sourceItems.edit.fields.orderCode1') }}</label>
            <InputText id="bid-order-code-1" v-model="form.order_code_1" fluid />
          </div>
          <div class="field">
            <label for="bid-order-code-2">{{ t('sourceItems.edit.fields.orderCode2') }}</label>
            <InputText id="bid-order-code-2" v-model="form.order_code_2" fluid />
          </div>

          <div class="field field-wide">
            <label for="bid-note">{{ t('sourceItems.edit.fields.note') }}</label>
            <Textarea id="bid-note" v-model="form.note" rows="3" auto-resize fluid />
          </div>
        </div>

        <template v-if="hostStore.storageEnabled && displayItem">
          <SourceItemPicturesSection :item-id="displayItem.id" />
          <SourceItemFilesSection :item-id="displayItem.id" />
        </template>
      </form>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <div v-if="displayItem" class="detail-footer-meta">
          <div class="meta-item">
            <UserAvatarPreview :user="displayItem.creator" />
          </div>
          <div class="meta-item">
            <span class="field-label">{{ t('sourceItems.catalogue.columns.created') }}</span>
            <span class="field-value">{{ displayItem.created }}</span>
          </div>
          <div v-if="displayItem.changed" class="meta-item">
            <span class="field-label">{{ t('sourceItems.catalogue.columns.changed') }}</span>
            <span class="field-value">{{ displayItem.changed }}</span>
          </div>
        </div>
        <div class="footer-actions">
          <template v-if="!editing">
            <Button
              :label="t('common.close')"
              severity="secondary"
              outlined
              @click="visible = false"
            />
            <Button
              :label="t('sourceItems.catalogue.controls.edit')"
              icon="mdi mdi-pencil"
              @click="onEdit"
            />
          </template>
          <template v-else>
            <Button
              :label="t('common.cancel')"
              severity="secondary"
              outlined
              :disabled="submitting"
              @click="onCancelEdit"
            />
            <Button
              :label="t('common.save')"
              :loading="submitting"
              :disabled="!!duplicateItem"
              @click="onSave"
            />
          </template>
        </div>
      </div>
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.detail-layout {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.field-wide {
  grid-column: 1 / -1;
}

.field-value {
  font-size: var(--font-size-sm);
}

.dialog-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: var(--space-4);
}

.footer-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.detail-footer-meta {
  display: flex;
  align-items: center;
  gap: var(--space-5);
  flex-wrap: wrap;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.edit-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.edit-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-3) var(--space-5);
}

.edit-grid .field label {
  font-size: var(--font-size-sm);
  color: var(--p-text-color);
}
</style>
