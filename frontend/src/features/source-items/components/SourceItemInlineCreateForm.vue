<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useSuppliersStore } from '@/features/suppliers'
import { useSourceItemTypesStore } from '@/features/source-item-types'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'
import SourceItemDimensionInput from './SourceItemDimensionInput.vue'
import { useSourceItemCreateForm } from '../composables/useSourceItemCreateForm'

import type { SourceItemResponse } from '../types/sourceItemsResponse'
import { labelName, localizeLabel } from '@/shared/utils/localizeLabel'

const { t } = useI18n()

const suppliersStore = useSuppliersStore()
const sourceItemTypesStore = useSourceItemTypesStore()

if (suppliersStore.items.length === 0) void suppliersStore.refresh()
if (sourceItemTypesStore.items.length === 0) void sourceItemTypesStore.refresh()

const dimensionInput = ref<InstanceType<typeof SourceItemDimensionInput> | null>(null)

const { form, submitting, errorMessage, duplicateItem, resetForm, submit } =
  useSourceItemCreateForm()

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

function reset(): void {
  resetForm()
  dimensionInput.value?.reset()
}

// A duplicate is reused instead of blocked, since the caller only needs a
// source item with these specs.
const willReuseExisting = computed(() => !!duplicateItem.value)

async function resolveOrCreate(): Promise<SourceItemResponse | null> {
  if (duplicateItem.value) return duplicateItem.value
  return submit()
}

defineExpose({ submit: resolveOrCreate, reset, submitting, willReuseExisting })
</script>

<template>
  <div class="inline-create">
    <Message
      v-if="duplicateItem"
      severity="info"
      :closable="false"
      data-testid="inline-create-duplicate-notice"
    >
      {{
        t('sourceItems.select.createInline.duplicateNotice', {
          type: localizeLabel(duplicateItem.type_name),
          dimension: duplicateItem.dimension,
          material: duplicateItem.material,
          id: duplicateItem.id,
        })
      }}
    </Message>

    <div class="field">
      <label for="msc-dimension">{{ t('sourceItems.create.fields.dimension') }} *</label>
      <SourceItemDimensionInput id="msc-dimension" ref="dimensionInput" v-model="form.dimension" />
    </div>

    <div class="field">
      <label id="msc-type-label" for="msc-type">{{ t('sourceItems.create.fields.type') }} *</label>
      <Select
        id="msc-type"
        aria-labelledby="msc-type-label"
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

    <div class="field-row">
      <div class="field">
        <label for="msc-material">{{ t('sourceItems.create.fields.material') }} *</label>
        <InputText id="msc-material" v-model="form.material" fluid />
      </div>
      <div class="field">
        <label for="msc-mass">{{ t('sourceItems.create.fields.mass') }}</label>
        <InputNumber id="msc-mass" v-model="form.mass" :min="0" fluid />
      </div>
    </div>

    <div class="field">
      <label id="msc-manufacturer-label" for="msc-manufacturer">{{ t('sourceItems.create.fields.manufacturer') }}</label>
      <Select
        id="msc-manufacturer"
        aria-labelledby="msc-manufacturer-label"
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

    <div class="field-row">
      <div class="field">
        <label for="msc-order-code-1">{{ t('sourceItems.create.fields.orderCode1') }}</label>
        <InputText id="msc-order-code-1" v-model="form.order_code_1" fluid />
      </div>
      <div class="field">
        <label for="msc-order-code-2">{{ t('sourceItems.create.fields.orderCode2') }}</label>
        <InputText id="msc-order-code-2" v-model="form.order_code_2" fluid />
      </div>
    </div>

    <div class="field">
      <label for="msc-note">{{ t('sourceItems.create.fields.note') }}</label>
      <Textarea id="msc-note" v-model="form.note" rows="2" auto-resize fluid />
    </div>

    <Message v-if="errorMessage" severity="error" :closable="false">
      {{ errorMessage }}
    </Message>
  </div>
</template>

<style scoped lang="scss">
.inline-create {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  background: var(--p-content-hover-background);
}

.field {
  min-width: 0;
}

.field label {
  font-size: var(--font-size-sm);
  color: var(--p-text-color);
}

.field-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2);
}
</style>
