<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { useLayoutStore } from '@/core/stores/layoutStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useSuppliersStore } from '@/features/suppliers'
import { useSourceItemTypesStore } from '@/features/source-item-types'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'
import SourceItemDimensionInput from './SourceItemDimensionInput.vue'
import { useSourceItemsCatalogueEditStore } from '../stores/sourceItemsCatalogueEditStore'
import { useSourceItemCreateForm } from '../composables/useSourceItemCreateForm'
import EmptyState from '@/shared/components/EmptyState.vue'

import type { SourceItemResponse } from '../types/sourceItemsResponse'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { catalogueStatusTagSeverity } from '@/shared/utils/catalogueStatus'
import { labelName, localizeLabel } from '@/shared/utils/localizeLabel'

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  created: [item: SourceItemResponse]
}>()

const { t } = useI18n()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const editStore = useSourceItemsCatalogueEditStore()
const suppliersStore = useSuppliersStore()
const sourceItemTypesStore = useSourceItemTypesStore()

const dimensionInput = ref<InstanceType<typeof SourceItemDimensionInput> | null>(null)

const {
  form,
  submitting,
  errorMessage,
  similarItemsLoading,
  similarItemsSearched,
  duplicateItem,
  sortedSimilarItems,
  resetForm,
  submit,
} = useSourceItemCreateForm()

// Referencing an already-archived supplier/source item type is allowed:
// the picker keeps archived rows selectable, sorted after live ones, each
// tagged (see useArchivableOptions.ts).
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

watchLoadingBar(similarItemsLoading)

function onEditExistingItem(): void {
  if (!duplicateItem.value) return
  editStore.editMode = true
  editStore.setSelectedItems([duplicateItem.value])
  visible.value = false
}

watch(visible, (isVisible) => {
  if (!isVisible) {
    return
  }

  resetForm()
  dimensionInput.value?.reset()

  if (suppliersStore.items.length === 0) {
    void suppliersStore.refresh()
  }

  if (sourceItemTypesStore.items.length === 0) {
    void sourceItemTypesStore.refresh()
  }
})

async function onSubmit(): Promise<void> {
  const created = await submit()
  if (!created) return

  emit('created', created)
  visible.value = false
}

function onCancel(): void {
  visible.value = false
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('sourceItems.create.title')"
    :style="{ width: 'var(--dialog-width-full)', maxWidth: '1400px' }"
  >
    <div class="dialog-body">
      <div class="top-row">
        <form class="create-form" @submit.prevent="onSubmit">
          <Message
            v-if="duplicateItem"
            severity="warn"
            :closable="false"
            data-testid="source-item-duplicate-warning"
          >
            <div class="duplicate-warning">
              <span>{{
                t('sourceItems.create.warnings.duplicateExists', {
                  type: localizeLabel(duplicateItem.type_name),
                  dimension: duplicateItem.dimension,
                  material: duplicateItem.material,
                  id: duplicateItem.id,
                })
              }}</span>
              <Button
                :label="t('sourceItems.create.warnings.editExisting')"
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
              <label for="bi-dimension-shape"
                >{{ t('sourceItems.create.fields.dimension') }} *</label
              >
              <SourceItemDimensionInput
                id="bi-dimension-shape"
                ref="dimensionInput"
                v-model="form.dimension"
              />
            </div>
            <div class="field field-wide">
              <label id="bi-type-label" for="bi-type">{{ t('sourceItems.create.fields.type') }} *</label>
              <Select
                id="bi-type"
                aria-labelledby="bi-type-label"
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
              <label for="bi-material">{{ t('sourceItems.create.fields.material') }} *</label>
              <InputText id="bi-material" v-model="form.material" fluid />
            </div>
            <div class="field">
              <label for="bi-mass">{{ t('sourceItems.create.fields.mass') }}</label>
              <InputNumber id="bi-mass" v-model="form.mass" :min="0" fluid />
            </div>
            <div class="field field-wide">
              <label id="bi-manufacturer-label" for="bi-manufacturer">{{ t('sourceItems.create.fields.manufacturer') }}</label>
              <Select
                id="bi-manufacturer"
                aria-labelledby="bi-manufacturer-label"
                v-model="form.manufacturer_id"
                :options="supplierOptions"
                option-label="name"
                option-value="id"
                :loading="suppliersStore.loading"
                :placeholder="t('sourceItems.create.fields.manufacturerPlaceholder')"
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
              <label for="bi-order-code-1">{{ t('sourceItems.create.fields.orderCode1') }}</label>
              <InputText id="bi-order-code-1" v-model="form.order_code_1" fluid />
            </div>
            <div class="field">
              <label for="bi-order-code-2">{{ t('sourceItems.create.fields.orderCode2') }}</label>
              <InputText id="bi-order-code-2" v-model="form.order_code_2" fluid />
            </div>
          </div>

          <div class="field">
            <label for="bi-note">{{ t('sourceItems.create.fields.note') }}</label>
            <Textarea id="bi-note" v-model="form.note" rows="3" auto-resize fluid />
          </div>

          <Message v-if="errorMessage" severity="error" :closable="false">
            {{ errorMessage }}
          </Message>
        </form>

        <div class="right-panel">
          <div class="similar-items-header">
            <span class="similar-items-title">{{
              t('sourceItems.create.similarItems.title')
            }}</span>
            <span class="similar-items-subtitle">{{
              t('sourceItems.create.similarItems.subtitle')
            }}</span>
          </div>

          <DataTable
            :value="sortedSimilarItems"
            :row-class="
              (row) => ((row as SourceItemResponse).id === duplicateItem?.id ? 'row-duplicate' : '')
            "
            size="small"
            :show-gridlines="isTableGridlinesEnabled"
            :striped-rows="isTableStripedEnabled"
            scrollable
            scroll-height="flex"
            class="similar-items-table"
          >
            <template #empty>
              <EmptyState
                :message="
                  similarItemsSearched
                    ? t('sourceItems.create.similarItems.empty')
                    : t('sourceItems.create.similarItems.hint')
                "
              />
            </template>

            <Column
              field="type_name"
              :header="t('sourceItems.catalogue.columns.type')"
              style="min-width: 8rem"
            >
              <template #body="{ data }">{{ localizeLabel(data.type_name) }}</template>
            </Column>
            <Column
              field="dimension"
              :header="t('sourceItems.catalogue.columns.dimension')"
              style="min-width: 8rem"
            >
              <template #body="{ data }">{{
                (data as SourceItemResponse).dimension ?? getEmptyPlaceholder()
              }}</template>
            </Column>
            <Column
              field="material"
              :header="t('sourceItems.catalogue.columns.material')"
              style="min-width: 7rem"
            />
            <Column
              field="manufacturer_name"
              :header="t('sourceItems.catalogue.columns.manufacturer')"
              style="min-width: 8rem"
            >
              <template #body="{ data }">{{
                (data as SourceItemResponse).manufacturer_name || getEmptyPlaceholder()
              }}</template>
            </Column>
            <Column :header="t('sourceItems.catalogue.columns.status')" style="min-width: 6rem">
              <template #body="{ data }">
                <Tag
                  :value="t(`sourceItems.catalogue.status.${(data as SourceItemResponse).status}`)"
                  :severity="catalogueStatusTagSeverity((data as SourceItemResponse).status)"
                />
              </template>
            </Column>
          </DataTable>
        </div>
      </div>
    </div>

    <template #footer>
      <Button
        :label="t('common.cancel')"
        severity="secondary"
        outlined
        :disabled="submitting"
        @click="onCancel"
      />
      <Button
        :label="t('common.save')"
        :loading="submitting"
        :disabled="!!duplicateItem"
        @click="onSubmit"
      />
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
  width: 46rem;
  padding-top: var(--space-1);
}

.field label {
  color: var(--p-text-color);
}

.field-wide {
  grid-column: 1 / -1;
}

.duplicate-warning {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
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
}
:deep(.row-duplicate) {
  background: var(--p-highlight-bg) !important;
}
</style>
