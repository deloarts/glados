<script setup lang="ts">
import { extractApiError } from '@/core/utils/errors'
import { TABLE_DEBOUNCE_MS } from '@/core/constants/table'
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDebounceFn } from '@vueuse/core'

import { articleGroupLabel, useArticleGroupsStore } from '@/features/article-groups'
import { ProductFamilySelect } from '@/features/product-families'
import { useSuppliersStore } from '@/features/suppliers'
import { useBoughtItemsStore } from '../stores/boughtItemsStore'
import { useBoughtItemsCatalogueEditStore } from '../stores/boughtItemsCatalogueEditStore'
import { getBoughtItems } from '../api/getBoughtItems'
import { useHostStore } from '@/core/host/stores/hostStore'
import { storeToRefs } from 'pinia'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useClipboard } from '@/core/composables/useClipboard'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'
import BoughtItemFilesSection from './BoughtItemFilesSection.vue'
import BoughtItemPicturesSection from './BoughtItemPicturesSection.vue'
import BoughtItemEdpSearch from './BoughtItemEdpSearch.vue'
import EmptyState from '@/shared/components/EmptyState.vue'

import type { DataTableRowContextMenuEvent } from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'
import type { BoughtItemCreateRequest } from '../types/boughtItemsRequest'
import type { BoughtItemResponse } from '../types/boughtItemsResponse'
import type { EdpSearchHit } from '../types/boughtItemsEdpTypes'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { catalogueStatusTagSeverity } from '@/shared/utils/catalogueStatus'

const props = defineProps<{
  copyFrom?: BoughtItemResponse | null
  /**
   * Prefill from e.g. a batch import row; unlike copyFrom it needs no
   * existing item and sets only the given fields.
   */
  prefill?: Partial<BoughtItemCreateRequest> | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  created: [item: BoughtItemResponse]
}>()

const { t } = useI18n()
const { copyToClipboard } = useClipboard()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const boughtItemsStore = useBoughtItemsStore()
const editStore = useBoughtItemsCatalogueEditStore()
const suppliersStore = useSuppliersStore()
const articleGroupsStore = useArticleGroupsStore()
const hostStore = useHostStore()

// Archived suppliers and article groups stay selectable, sorted last.
const { sortedOptions: supplierOptions, isArchived: isSupplierArchived } = useArchivableOptions(
  computed(() => suppliersStore.items),
)
const selectedSupplier = computed(
  () => suppliersStore.getById(form.manufacturer_id) ?? null,
)
const { sortedOptions: articleGroupOptions, isArchived: isArticleGroupArchived } =
  useArchivableOptions(computed(() => articleGroupsStore.items))
const selectedArticleGroups = computed(() =>
  articleGroupsStore.items.filter((g) => form.article_group_ids.includes(g.id)),
)

// Only set when the item was created but some files failed to upload.
const createdItem = ref<BoughtItemResponse | null>(null)
const filesSection = ref<InstanceType<typeof BoughtItemFilesSection> | null>(null)
const picturesSection = ref<InstanceType<typeof BoughtItemPicturesSection> | null>(null)
// Remounts the files section per session, dropping unsaved staged files.
const filesSectionKey = ref(0)

interface BoughtItemCreateFormState {
  order_code_1: string
  order_code_2: string
  gtin: string
  ean: string
  tariff_number: string
  article_name: string
  article_group_ids: number[]
  part_number: string
  mass: number | null
  note: string
  weblink: string
  manufacturer_id: number | null
  product_family_id: number | null
}

function createEmptyForm(): BoughtItemCreateFormState {
  return {
    order_code_1: '',
    order_code_2: '',
    gtin: '',
    ean: '',
    tariff_number: '',
    article_name: '',
    article_group_ids: [],
    part_number: '',
    mass: null,
    note: '',
    weblink: '',
    manufacturer_id: null,
    product_family_id: null,
  }
}

const form = reactive(createEmptyForm())

// The Data Portal part the form was filled from; the create links it.
const edpPartId = ref<number | null>(null)
const edpSearch = ref<InstanceType<typeof BoughtItemEdpSearch> | null>(null)

function onEdpPick(hit: EdpSearchHit): void {
  const draft = hit.draft
  edpPartId.value = draft.edp_part_id
  form.article_name = draft.article_name ?? form.article_name
  form.order_code_1 = draft.order_code_1 ?? form.order_code_1
  form.order_code_2 = draft.order_code_2 ?? ''
  form.ean = draft.ean ?? form.ean
  form.weblink = draft.weblink ?? form.weblink
  if (draft.manufacturer_id !== null) form.manufacturer_id = draft.manufacturer_id
  if (draft.product_family_id !== null) form.product_family_id = draft.product_family_id
  if ((draft.article_group_ids ?? []).length > 0) form.article_group_ids = [...draft.article_group_ids!]
}

const submitting = ref(false)
const errorMessage = ref<string | null>(null)

// With auto numbering the backend generates the part number, so manual
// entry is only offered otherwise. The backend enforces this either way.
const partNumbers = computed(() => hostStore.boughtItemPartNumbers)
const partNumberEntryDisabled = computed(() => partNumbers.value.auto)
const partNumberHint = computed(() => {
  if (partNumbers.value.auto) {
    return partNumbers.value.example
      ? t('boughtItems.create.partNumber.autoWithExample', { example: partNumbers.value.example })
      : t('boughtItems.create.partNumber.auto')
  }
  return null
})

// ── Exact duplicate check (same order_code_1 + manufacturer_id) ──────────
const duplicateItem = ref<BoughtItemResponse | null>(null)

async function checkDuplicate(): Promise<void> {
  const code = form.order_code_1.trim()
  if (!code || !form.manufacturer_id) {
    duplicateItem.value = null
    return
  }

  const result = await getBoughtItems({
    order_code_1: code,
    manufacturer_id: form.manufacturer_id,
    limit: 1,
  })
  duplicateItem.value = result.items[0] ?? null
}

const debouncedCheckDuplicate = useDebounceFn(checkDuplicate, TABLE_DEBOUNCE_MS)

watch(
  () => [form.order_code_1, form.manufacturer_id] as const,
  () => debouncedCheckDuplicate(),
)

function onEditExistingItem(): void {
  if (!duplicateItem.value) return
  editStore.editMode = true
  editStore.selectedItems = [duplicateItem.value]
  visible.value = false
}

// ── Similar items search ─────────────────────────────────────────────────
const similarItems = ref<BoughtItemResponse[]>([])
const similarItemsLoading = ref(false)
const similarItemsSearched = ref(false)

watchLoadingBar(similarItemsLoading)

async function fetchSimilarItems(): Promise<void> {
  const searchText = form.order_code_1.trim() || form.article_name.trim() || form.part_number.trim()

  if (!searchText && !form.manufacturer_id) {
    similarItems.value = []
    similarItemsSearched.value = false
    return
  }

  similarItemsLoading.value = true
  similarItemsSearched.value = true

  try {
    const result = await getBoughtItems({
      search: searchText || undefined,
      manufacturer_id: form.manufacturer_id ?? undefined,
      limit: 10,
    })
    similarItems.value = result.items
  } finally {
    similarItemsLoading.value = false
  }
}

const debouncedFetchSimilarItems = useDebounceFn(fetchSimilarItems, TABLE_DEBOUNCE_MS)

watch(
  () => [form.order_code_1, form.article_name, form.part_number, form.manufacturer_id] as const,
  () => debouncedFetchSimilarItems(),
)

const pendingCopyItem = ref<BoughtItemResponse | null>(null)

function onSimilarItemClick(item: BoughtItemResponse): void {
  pendingCopyItem.value = item
}

const cm = ref()
const contextMenuItem = ref<BoughtItemResponse | null>(null)

function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
  cm.value?.show(event.originalEvent)
}

const contextMenuItems = computed<MenuItem[]>(() => {
  const item = contextMenuItem.value
  if (!item) return []

  return [
    {
      label: t('common.copyUuid'),
      icon: 'mdi mdi-content-copy',
      command: () => void copyToClipboard(item.public_id),
    },
  ]
})

function onConfirmCopy(): void {
  if (pendingCopyItem.value) {
    copyItemToForm(pendingCopyItem.value)
  }
  pendingCopyItem.value = null
}

function onCancelCopy(): void {
  pendingCopyItem.value = null
}

function copyItemToForm(item: BoughtItemResponse): void {
  form.article_name = item.article_name
  form.part_number = item.part_number ?? ''
  form.order_code_1 = item.order_code_1
  form.order_code_2 = item.order_code_2 ?? ''
  form.gtin = item.gtin ?? ''
  form.ean = item.ean ?? ''
  form.tariff_number = item.tariff_number ?? ''
  form.mass = item.mass
  form.manufacturer_id = item.manufacturer_id
  form.note = item.note ?? ''
  form.weblink = item.weblink ?? ''
  form.article_group_ids = (item.article_groups ?? []).map((g) => g.id)
  form.product_family_id = item.product_family_id ?? null
}

watch(visible, (isVisible) => {
  if (!isVisible) {
    return
  }

  Object.assign(form, createEmptyForm())
  edpPartId.value = null
  edpSearch.value?.reset()
  errorMessage.value = null
  duplicateItem.value = null
  similarItems.value = []
  similarItemsSearched.value = false
  pendingCopyItem.value = null
  createdItem.value = null
  filesSectionKey.value += 1

  if (props.copyFrom) {
    copyItemToForm(props.copyFrom)
    form.article_name = `${props.copyFrom.article_name} ${t('boughtItems.create.copySuffix')}`
  } else if (props.prefill) {
    if (props.prefill.article_name !== undefined) form.article_name = props.prefill.article_name
    if (props.prefill.order_code_1 !== undefined) form.order_code_1 = props.prefill.order_code_1
    if (props.prefill.part_number) form.part_number = props.prefill.part_number
    if (props.prefill.manufacturer_id) form.manufacturer_id = props.prefill.manufacturer_id
    if (props.prefill.article_group_ids) form.article_group_ids = props.prefill.article_group_ids
    if (props.prefill.product_family_id) form.product_family_id = props.prefill.product_family_id
    if (props.prefill.note) form.note = props.prefill.note
    if (props.prefill.weblink) form.weblink = props.prefill.weblink
  }

  if (suppliersStore.items.length === 0) {
    void suppliersStore.refresh()
  }
  if (articleGroupsStore.items.length === 0) {
    void articleGroupsStore.refresh()
  }
})

function isFormValid(): boolean {
  return (
    form.order_code_1.trim().length > 0 &&
    form.article_name.trim().length > 0 &&
    !!form.manufacturer_id &&
    form.manufacturer_id > 0
  )
}

async function onSubmit(): Promise<void> {
  if (!isFormValid()) {
    errorMessage.value = t('boughtItems.create.errors.required')

    return
  }

  submitting.value = true
  errorMessage.value = null

  const payload: BoughtItemCreateRequest = {
    status: 'active',
    order_code_1: form.order_code_1.trim(),
    order_code_2: form.order_code_2.trim() || null,
    gtin: form.gtin.trim() || null,
    ean: form.ean.trim() || null,
    tariff_number: form.tariff_number.trim() || null,
    article_name: form.article_name.trim(),
    article_group_ids: form.article_group_ids,
    part_number: form.part_number.trim() || null,
    mass: form.mass,
    note: form.note.trim() || null,
    weblink: form.weblink.trim() || null,
    manufacturer_id: form.manufacturer_id as number,
    product_family_id: form.product_family_id,
    edp_part_id: edpPartId.value,
  }

  try {
    const created = await boughtItemsStore.create(payload)

    emit('created', created)

    if (hostStore.storageEnabled) {
      const pictureUploaded = (await picturesSection.value?.flushPendingUpload(created.id)) ?? true
      const filesUploaded = (await filesSection.value?.flushPendingUploads(created.id)) ?? true
      const uploaded = pictureUploaded && filesUploaded
      if (!uploaded) {
        // Keeps the dialog open with a real itemId so failed files can be retried
        // without creating a duplicate item.
        createdItem.value = created
        errorMessage.value = t('boughtItems.create.errors.fileUpload')

        return
      }
    }

    visible.value = false
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t('boughtItems.create.errors.unknown')
  } finally {
    submitting.value = false
  }
}

function onCancel(): void {
  visible.value = false
}

function onDone(): void {
  visible.value = false
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('boughtItems.create.title')"
    :style="{ width: 'var(--dialog-width-full)', maxWidth: '1400px' }"
  >
    <div class="dialog-body">
      <div class="top-row">
        <form class="create-form" @submit.prevent="onSubmit">
          <BoughtItemEdpSearch v-if="hostStore.edpEnabled" ref="edpSearch" @pick="onEdpPick" />
          <Message v-if="duplicateItem" severity="warn" :closable="false">
            <div class="duplicate-warning">
              <span>{{
                t('boughtItems.create.warnings.duplicateExists', {
                  name: duplicateItem.article_name,
                  id: duplicateItem.id,
                })
              }}</span>
              <Button
                :label="t('boughtItems.create.warnings.editExisting')"
                severity="warn"
                size="small"
                icon="mdi mdi-pencil"
                style="width: 17rem"
                @click="onEditExistingItem"
              />
            </div>
          </Message>

          <div class="form-grid">
            <div class="field field-wide">
              <label for="bi-article-name"
                >{{ t('boughtItems.create.fields.articleName') }} *</label
              >
              <InputText id="bi-article-name" v-model="form.article_name" fluid />
            </div>

            <div class="field">
              <label for="bi-order-code-1">{{ t('boughtItems.create.fields.orderCode1') }} *</label>
              <InputText id="bi-order-code-1" v-model="form.order_code_1" fluid />
            </div>

            <div class="field">
              <label for="bi-order-code-2">{{ t('boughtItems.create.fields.orderCode2') }}</label>
              <InputText id="bi-order-code-2" v-model="form.order_code_2" fluid />
            </div>

            <div class="field">
              <label id="bi-manufacturer-label" for="bi-manufacturer"
                >{{ t('boughtItems.create.fields.manufacturer') }} *</label
              >
              <Select
                id="bi-manufacturer"
                aria-labelledby="bi-manufacturer-label"
                v-model="form.manufacturer_id"
                :options="supplierOptions"
                option-label="name"
                option-value="id"
                :loading="suppliersStore.loading"
                :placeholder="t('boughtItems.create.fields.manufacturerPlaceholder')"
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
              <label for="bi-part-number">{{ t('boughtItems.create.fields.partNumber') }}</label>
              <InputText
                id="bi-part-number"
                v-model="form.part_number"
                fluid
                :disabled="partNumberEntryDisabled"
              />
              <small v-if="partNumberHint" class="field-hint">{{ partNumberHint }}</small>
            </div>

            <div class="field field-wide">
              <label id="bi-article-groups-label" for="bi-article-groups">{{
                t('boughtItems.create.fields.articleGroups')
              }}</label>
              <MultiSelect
                id="bi-article-groups"
                aria-labelledby="bi-article-groups-label"
                v-model="form.article_group_ids"
                :options="articleGroupOptions"
                :option-label="articleGroupLabel"
                option-value="id"
                :loading="articleGroupsStore.loading"
                :placeholder="t('boughtItems.create.fields.articleGroupsPlaceholder')"
                display="chip"
                filter
                fluid
              >
                <template #option="{ option }">
                  <span>{{ articleGroupLabel(option) }}</span>
                  <ArchivedOptionTag v-if="option.archived" />
                </template>
              </MultiSelect>
              <ArchivedSelectionWarning v-if="isArticleGroupArchived(selectedArticleGroups)" />
            </div>

            <div class="field">
              <label id="bi-product-family-label" for="bi-product-family">{{
                t('boughtItems.create.fields.productFamily')
              }}</label>
              <ProductFamilySelect v-model="form.product_family_id" input-id="bi-product-family" aria-labelledby="bi-product-family-label" />
            </div>

            <div class="field field-wide">
              <label for="bi-weblink">{{ t('boughtItems.create.fields.weblink') }}</label>
              <InputText id="bi-weblink" v-model="form.weblink" type="url" fluid />
            </div>

            <div class="field field-wide">
              <label for="bi-note">{{ t('boughtItems.create.fields.note') }}</label>
              <Textarea id="bi-note" v-model="form.note" rows="3" auto-resize fluid />
            </div>

            <div class="field">
              <label for="bi-gtin">{{ t('boughtItems.create.fields.gtin') }}</label>
              <InputText id="bi-gtin" v-model="form.gtin" fluid />
            </div>

            <div class="field">
              <label for="bi-ean">{{ t('boughtItems.create.fields.ean') }}</label>
              <InputText id="bi-ean" v-model="form.ean" fluid />
            </div>

            <div class="field">
              <label for="bi-tariff-number">{{
                t('boughtItems.create.fields.tariffNumber')
              }}</label>
              <InputText id="bi-tariff-number" v-model="form.tariff_number" fluid />
            </div>

            <div class="field">
              <label for="bi-mass">{{ t('boughtItems.create.fields.mass') }}</label>
              <InputNumber id="bi-mass" v-model="form.mass" :min="0" fluid />
            </div>
          </div>

          <Message v-if="errorMessage" severity="error" :closable="false">
            {{ errorMessage }}
          </Message>
        </form>

        <div class="right-panel">
          <div class="similar-items-header">
            <span class="similar-items-title">{{
              t('boughtItems.create.similarItems.title')
            }}</span>
            <span class="similar-items-subtitle">{{
              t('boughtItems.create.similarItems.subtitle')
            }}</span>
          </div>

          <DataTable
            :value="similarItems"
            v-model:context-menu-selection="contextMenuItem"
            :row-class="
              (row) =>
                (row as BoughtItemResponse).id === pendingCopyItem?.id ? 'row-pending-copy' : ''
            "
            size="small"
            :show-gridlines="isTableGridlinesEnabled"
            :striped-rows="isTableStripedEnabled"
            scrollable
            scroll-height="flex"
            class="similar-items-table"
            @row-click="(e) => onSimilarItemClick(e.data as BoughtItemResponse)"
            @row-contextmenu="onRowContextMenu"
          >
            <template #empty>
              <EmptyState
                :message="
                  similarItemsSearched
                    ? t('boughtItems.create.similarItems.empty')
                    : t('boughtItems.create.similarItems.hint')
                "
              />
            </template>

            <Column
              field="article_name"
              :header="t('boughtItems.catalogue.columns.articleName')"
              style="min-width: 10rem"
            />
            <Column
              field="order_code_1"
              :header="t('boughtItems.catalogue.columns.orderCode1')"
              style="min-width: 8rem"
            />
            <Column
              field="manufacturer_name"
              :header="t('boughtItems.catalogue.columns.manufacturer')"
              style="min-width: 8rem"
            />
            <Column
              field="part_number"
              :header="t('boughtItems.catalogue.columns.partNumber')"
              style="min-width: 7rem"
            >
              <template #body="{ data }">{{
                (data as BoughtItemResponse).part_number ?? getEmptyPlaceholder()
              }}</template>
            </Column>
            <Column :header="t('boughtItems.catalogue.columns.status')" style="min-width: 6rem">
              <template #body="{ data }">
                <Tag
                  :value="t(`boughtItems.catalogue.status.${(data as BoughtItemResponse).status}`)"
                  :severity="catalogueStatusTagSeverity((data as BoughtItemResponse).status)"
                />
              </template>
            </Column>
          </DataTable>

          <ContextMenu ref="cm" :model="contextMenuItems" @hide="contextMenuItem = null" />

          <div v-if="pendingCopyItem" class="copy-confirm-strip">
            <span class="copy-confirm-message">{{
              t('boughtItems.create.similarItems.copyMessage')
            }}</span>
            <div class="copy-confirm-actions">
              <Button
                :label="t('common.cancel')"
                severity="secondary"
                outlined
                size="small"
                @click="onCancelCopy"
              />
              <Button
                :label="t('boughtItems.create.similarItems.copyButton')"
                size="small"
                icon="mdi mdi-content-copy"
                @click="onConfirmCopy"
              />
            </div>
          </div>
        </div>
      </div>

      <template v-if="hostStore.storageEnabled">
        <Divider />
        <BoughtItemPicturesSection
          ref="picturesSection"
          :key="`pictures-${filesSectionKey}`"
          :item-id="createdItem?.id ?? null"
        />
        <BoughtItemFilesSection
          ref="filesSection"
          :key="filesSectionKey"
          :item-id="createdItem?.id ?? null"
        />
      </template>
    </div>

    <template #footer>
      <Button
        v-if="!createdItem"
        :label="t('common.cancel')"
        severity="secondary"
        outlined
        :disabled="submitting"
        @click="onCancel"
      />
      <Button
        v-if="!createdItem"
        :label="t('common.save')"
        :loading="submitting"
        @click="onSubmit"
      />
      <Button v-if="createdItem" :label="t('common.close')" @click="onDone" />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.dialog-body {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.top-row {
  display: flex;
  gap: var(--space-5);
  min-height: 0;
}

.create-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  flex-shrink: 0;
  width: 40rem;
  padding-top: var(--space-1);
}

.field label {
  color: var(--p-text-color);
}

.field-wide {
  grid-column: 1 / -1;
}

.right-panel {
  flex: 1 1 0%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  border-left: 1px solid var(--p-content-border-color);
  padding-left: var(--space-5);
  overflow-y: auto;
}

.similar-items-header {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.similar-items-title {
  font-weight: 600;
  font-size: var(--font-size-md);
}

.similar-items-subtitle {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.similar-items-table {
  flex: 1 1 0%;
  min-height: 0;
  cursor: pointer;
}

.duplicate-warning {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

.copy-confirm-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--p-border-radius-sm, 4px);
  background: var(--p-highlight-bg);
  border: 1px solid var(--p-primary-color);
}

.copy-confirm-message {
  font-size: var(--font-size-sm);
}

.copy-confirm-actions {
  display: flex;
  gap: var(--space-2);
  flex-shrink: 0;
}

:deep(.row-pending-copy) {
  background: var(--p-highlight-bg) !important;
}

:deep(.similar-items-table tr) {
  cursor: pointer;
}
</style>
