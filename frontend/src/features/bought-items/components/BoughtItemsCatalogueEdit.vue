<script setup lang="ts">
import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useArticleGroupsStore } from '@/features/article-groups'
import { ProductFamilySelect } from '@/features/product-families'
import { useSuppliersStore } from '@/features/suppliers'
import { getBoughtItems } from '../api/getBoughtItems'
import { useBoughtItemsStore } from '../stores/boughtItemsStore'
import { useBoughtItemsCatalogueEditStore } from '../stores/boughtItemsCatalogueEditStore'
import { useBoughtItemsCatalogueEditForm } from '../composables/useBoughtItemsCatalogueEditForm'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'

import type { BoughtItemDataSource } from '../types/boughtItemsRequest'
import type { BoughtItemCatalogueStatus, BoughtItemResponse } from '../types/boughtItemsResponse'
import { useSuccessorItem } from '@/shared/composables/useSuccessorItem'
import { useCadClaimGuard } from '@/shared/composables/useCadClaimGuard'
import CadClaimDialog from '@/shared/components/items/CadClaimDialog.vue'
import {
  TOLERANCE_FIELDS,
  TOLERANCE_INPUT_PROPS,
  TOLERANCE_LABEL_KEYS,
} from '@/shared/utils/deliveryTolerance'
import { labelName, localizeLabel } from '@/shared/utils/localizeLabel'

const { t } = useI18n()

const boughtItemsStore = useBoughtItemsStore()
const editStore = useBoughtItemsCatalogueEditStore()
const suppliersStore = useSuppliersStore()
const articleGroupsStore = useArticleGroupsStore()

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

const DATA_SOURCE_OPTIONS: BoughtItemDataSource[] = ['WEB', 'CAD']
const STATUS_OPTIONS: BoughtItemCatalogueStatus[] = ['active', 'inactive', 'replaced']

const { form, mixedFields, markDirty, placeholderFor, fillFromSelection, isFormValid, buildPayload } =
  useBoughtItemsCatalogueEditForm(() => t('boughtItems.edit.multipleValues'))

const { submitting, errorMessage, run } = useSubmitAction()

const {
  successorItem,
  successorSuggestions,
  resolveSuccessorItem,
  searchSuccessorItems,
} = useSuccessorItem<BoughtItemResponse>({
  getById: (id) => boughtItemsStore.getById(id),
  list: (params) => getBoughtItems(params),
})

const selectedItems = computed(() => editStore.selectedItems)

function onSuccessorItemSelect(item: BoughtItemResponse | null): void {
  form.successor_item_id = item?.id ?? null
  markDirty('successor_item_id')
}

function resetFormFromSelection(items: BoughtItemResponse[]): void {
  errorMessage.value = null
  fillFromSelection(items)
  if (items.length === 0) {
    return
  }
  resolveSuccessorItem(mixedFields.has('successor_item_id') ? null : form.successor_item_id)
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

    if (suppliersStore.items.length === 0) {
      void suppliersStore.refresh()
    }
    if (articleGroupsStore.items.length === 0) {
      void articleGroupsStore.refresh()
    }
  },
  { immediate: true },
)

async function onSubmit(): Promise<void> {
  if (selectedItems.value.length === 0) {
    return
  }

  if (!isFormValid()) {
    errorMessage.value = t('boughtItems.edit.errors.required')

    return
  }

  if (!(await cadClaim.confirmSave(selectedItems.value, getBoughtItems))) return

  await run(async () => {
    const updated = await Promise.all(
      selectedItems.value.map((item) => boughtItemsStore.update(item.id, buildPayload(item))),
    )

    boughtItemsStore.replaceItems(updated)
    editStore.setSelectedItems(updated)
  }, t('boughtItems.edit.errors.unknown'))
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
        <span class="panel-title">{{ t('boughtItems.edit.title') }}</span>
        <Tag
          v-if="selectedItems.length > 0"
          :value="t('boughtItems.edit.selectionSummary', { count: selectedItems.length })"
          severity="secondary"
        />
      </div>
    </template>

    <Message v-if="selectedItems.length === 0" severity="info" :closable="false">
      {{ t('boughtItems.edit.noSelection') }}
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
          <label id="bie-status-label" for="bie-status">{{ t('boughtItems.edit.fields.status') }}</label>
          <Select
            id="bie-status"
            aria-labelledby="bie-status-label"
            v-model="form.status"
            :options="STATUS_OPTIONS"
            :option-label="(s) => t(`boughtItems.catalogue.status.${s}`)"
            :placeholder="placeholderFor('status')"
            fluid
            @update:model-value="markDirty('status')"
          />
        </div>

        <div v-if="form.status === 'replaced'" class="field">
          <label for="bie-successor-item">
            {{ t('boughtItems.edit.fields.successorItemId') }}
          </label>
          <AutoComplete
            id="bie-successor-item"
            v-model="successorItem"
            :suggestions="successorSuggestions"
            :option-label="(item) => `#${item.id}: ${item.order_code_1} – ${item.article_name}`"
            :placeholder="
              placeholderFor(
                'successor_item_id',
                t('boughtItems.edit.fields.successorItemPlaceholder'),
              )
            "
            force-selection
            fluid
            @complete="searchSuccessorItems"
            @update:model-value="onSuccessorItemSelect"
          />
        </div>

        <div class="field">
          <label for="bie-article-name">{{ t('boughtItems.edit.fields.articleName') }} *</label>
          <InputText
            id="bie-article-name"
            v-model="form.article_name"
            :placeholder="placeholderFor('article_name')"
            fluid
            @update:model-value="markDirty('article_name')"
          />
        </div>

        <div class="field">
          <label for="bie-part-number">{{ t('boughtItems.edit.fields.partNumber') }}</label>
          <InputText
            id="bie-part-number"
            v-model="form.part_number"
            :placeholder="placeholderFor('part_number')"
            fluid
            disabled
            @update:model-value="markDirty('part_number')"
          />
        </div>

        <div class="field">
          <label for="bie-order-code-1">{{ t('boughtItems.edit.fields.orderCode1') }} *</label>
          <InputText
            id="bie-order-code-1"
            v-model="form.order_code_1"
            :placeholder="placeholderFor('order_code_1')"
            fluid
            @update:model-value="markDirty('order_code_1')"
          />
        </div>

        <div class="field">
          <label for="bie-order-code-2">{{ t('boughtItems.edit.fields.orderCode2') }}</label>
          <InputText
            id="bie-order-code-2"
            v-model="form.order_code_2"
            :placeholder="placeholderFor('order_code_2')"
            fluid
            @update:model-value="markDirty('order_code_2')"
          />
        </div>

        <div class="field">
          <label id="bie-manufacturer-label" for="bie-manufacturer">{{ t('boughtItems.edit.fields.manufacturer') }} *</label>
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
                t('boughtItems.edit.fields.manufacturerPlaceholder'),
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
          <label id="bie-article-groups-label" for="bie-article-groups">{{ t('boughtItems.edit.fields.articleGroups') }}</label>
          <MultiSelect
            id="bie-article-groups"
            aria-labelledby="bie-article-groups-label"
            v-model="form.article_group_ids"
            :options="articleGroupOptions"
            :option-label="labelName"
            option-value="id"
            :loading="articleGroupsStore.loading"
            :placeholder="
              placeholderFor(
                'article_group_ids',
                t('boughtItems.edit.fields.articleGroupsPlaceholder'),
              )
            "
            display="chip"
            filter
            fluid
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
          <label id="bie-product-family-label" for="bie-product-family">{{ t('boughtItems.edit.fields.productFamily') }}</label>
          <ProductFamilySelect
            v-model="form.product_family_id"
            input-id="bie-product-family"
            aria-labelledby="bie-product-family-label"
            :placeholder="
              placeholderFor('product_family_id', t('settings.productFamilies.selectPlaceholder'))
            "
            @update:model-value="markDirty('product_family_id')"
          />
        </div>

        <div class="field">
          <label for="bie-mass">{{ t('boughtItems.edit.fields.mass') }}</label>
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
          <label :for="`bie-${field}`">{{ t(TOLERANCE_LABEL_KEYS[field]) }}</label>
          <InputNumber
            :id="`bie-${field}`"
            v-model="form[field]"
            v-bind="TOLERANCE_INPUT_PROPS"
            :placeholder="placeholderFor(field, t('common.deliveryTolerance.global'))"
            fluid
            @update:model-value="markDirty(field)"
          />
        </div>

        <div class="field">
          <label for="bie-weblink">{{ t('boughtItems.edit.fields.weblink') }}</label>
          <InputText
            id="bie-weblink"
            v-model="form.weblink"
            type="url"
            :placeholder="placeholderFor('weblink')"
            fluid
            @update:model-value="markDirty('weblink')"
          />
        </div>

        <div class="field">
          <label for="bie-note">{{ t('boughtItems.edit.fields.note') }}</label>
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

        <div class="field">
          <label for="bie-gtin">{{ t('boughtItems.edit.fields.gtin') }}</label>
          <InputText
            id="bie-gtin"
            v-model="form.gtin"
            :placeholder="placeholderFor('gtin')"
            fluid
            @update:model-value="markDirty('gtin')"
          />
        </div>

        <div class="field">
          <label for="bie-ean">{{ t('boughtItems.edit.fields.ean') }}</label>
          <InputText
            id="bie-ean"
            v-model="form.ean"
            :placeholder="placeholderFor('ean')"
            fluid
            @update:model-value="markDirty('ean')"
          />
        </div>

        <div class="field">
          <label for="bie-tariff-number">{{ t('boughtItems.edit.fields.tariffNumber') }}</label>
          <InputText
            id="bie-tariff-number"
            v-model="form.tariff_number"
            :placeholder="placeholderFor('tariff_number')"
            fluid
            @update:model-value="markDirty('tariff_number')"
          />
        </div>

        <div class="field">
          <label id="bie-data-source-label" for="bie-data-source">{{ t('boughtItems.edit.fields.dataSource') }}</label>
          <Select
            id="bie-data-source"
            aria-labelledby="bie-data-source-label"
            v-model="form.data_source"
            :options="DATA_SOURCE_OPTIONS"
            :option-label="(source) => t(`boughtItems.catalogue.dataSources.${source}`)"
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
  // Thread height down through OpenVue Panel's DOM structure
  display: flex;
  flex-direction: column;
}

// The content container is a flex item, so min-height: 0 constrains it and
// the content's height: 100% resolves against it.
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
