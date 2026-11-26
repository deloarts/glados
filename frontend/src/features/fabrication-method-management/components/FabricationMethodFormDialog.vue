<script setup lang="ts">
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useSuppliersStore } from '@/features/suppliers'
import { useEntityFormDialog } from '@/shared/composables/useEntityFormDialog'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'
import LabelColorPairField from '@/shared/components/forms/LabelColorPairField.vue'
import LocalizedTextInput from '@/shared/components/forms/LocalizedTextInput.vue'
import { useLocalizedText } from '@/shared/composables/useLocalizedText'
import { DEFAULT_LABEL_COLOR, DEFAULT_LABEL_FONT_COLOR } from '@/shared/utils/labelColors'
import { cleanLocalizedText, type LocalizedText } from '@/shared/utils/localizedText'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useFabricationMethodsStore } from '@/features/fabrication-methods'
import type { FabricationMethodResponse } from '@/features/fabrication-methods'

interface Props {
  method?: FabricationMethodResponse
}

const props = defineProps<Props>()

const emit = defineEmits<{
  saved: [method: FabricationMethodResponse]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const host = useHostStore()
const { localize } = useLocalizedText()
const store = useFabricationMethodsStore()
const suppliersStore = useSuppliersStore()

interface FormState {
  name: LocalizedText
  description: LocalizedText
  label_color: string
  label_font_color: string
  requires_machine: boolean
  required_external: boolean
  default_supplier_id: number | null
  lead_time_days: number | null
  // null means the pieces wait nothing after the step.
  wait_after_minutes: number | null
  default_for_assemblies: boolean
}

function createEmptyForm(): FormState {
  return {
    name: {},
    description: {},
    label_color: DEFAULT_LABEL_COLOR,
    label_font_color: DEFAULT_LABEL_FONT_COLOR,
    requires_machine: true,
    required_external: false,
    default_supplier_id: null,
    lead_time_days: null,
    wait_after_minutes: null,
    default_for_assemblies: false,
  }
}

function formFromMethod(method: FabricationMethodResponse): FormState {
  return {
    name: { ...method.name },
    description: { ...method.description },
    label_color: method.label_color ?? DEFAULT_LABEL_COLOR,
    label_font_color: method.label_font_color ?? DEFAULT_LABEL_FONT_COLOR,
    requires_machine: method.requires_machine,
    required_external: method.required_external,
    default_supplier_id: method.default_supplier_id ?? null,
    lead_time_days: method.lead_time_days ?? null,
    wait_after_minutes: method.wait_after_minutes ?? null,
    default_for_assemblies: method.default_for_assemblies,
  }
}

const { form, submitting, errorMessage, isEditMode, onSubmit, onCancel } = useEntityFormDialog<
  FabricationMethodResponse,
  FormState
>({
  visible,
  entity: () => props.method,
  emptyForm: createEmptyForm,
  formFromEntity: formFromMethod,
  validate: (form) =>
    form.name[host.defaultLanguage]?.trim() ? null : t('resources.fabricationMethods.errors.required'),
  save: (form, isEditMode, method) => {
    const payload = {
      name: cleanLocalizedText(form.name),
      description: cleanLocalizedText(form.description),
      label_color: form.label_color,
      label_font_color: form.label_font_color,
      requires_machine: form.requires_machine,
      required_external: form.required_external,
      default_supplier_id: form.default_supplier_id,
      lead_time_days: form.lead_time_days,
      wait_after_minutes: form.wait_after_minutes,
      default_for_assemblies: form.default_for_assemblies,
    }
    return isEditMode && method
      ? store.update(method.id, payload)
      : store.create(payload)
  },
  onSaved: (saved) => emit('saved', saved),
  unknownErrorMessage: t('resources.fabricationMethods.errors.unknown'),
})

// Only for external work, but kept visible once a value is set, so
// unchecking required_external never hides it.
const showLeadTimeField = computed(
  () => form.required_external || form.lead_time_days !== null,
)

// The backend rejects an archived method as the default for assemblies.
const isArchivedMethod = computed(() => isEditMode.value && props.method?.archived === true)

// Archived suppliers stay selectable, sorted last.
const { sortedOptions: supplierOptions, isArchived: isSupplierArchived } = useArchivableOptions(
  computed(() => suppliersStore.items),
)
const selectedSupplier = computed(
  () => suppliersStore.getById(form.default_supplier_id) ?? null,
)

// Runs once, on the first open.
watch(visible, (isVisible) => {
  if (isVisible && suppliersStore.items.length === 0) {
    void suppliersStore.refresh()
  }
})
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="
      isEditMode
        ? t('resources.fabricationMethods.editMethod')
        : t('resources.fabricationMethods.createMethod')
    "
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <form class="method-form" @submit.prevent="onSubmit">
      <div class="form-fields">
        <div class="field field-wide">
          <LocalizedTextInput
            v-model="form.name"
            :label="`${t('resources.fabricationMethods.fields.name')} *`"
            :maxlength="200"
            required
          />
        </div>

        <div class="field field-wide">
          <LocalizedTextInput
            v-model="form.description"
            :label="t('resources.fabricationMethods.fields.description')"
            :maxlength="4000"
            multiline
          />
        </div>

        <LabelColorPairField
          v-model:color="form.label_color"
          v-model:font-color="form.label_font_color"
          color-id="fm-label-color"
          font-color-id="fm-font-color"
          :color-label="t('resources.fabricationMethods.fields.labelColor')"
          :font-color-label="t('resources.fabricationMethods.fields.labelFontColor')"
          :preview-label="t('resources.fabricationMethods.fields.preview')"
          :preview-text="localize(form.name) || t('resources.fabricationMethods.fields.previewPlaceholder')"
        />

        <div class="field field-wide">
          <label class="checkbox-label">
            <Checkbox v-model="form.requires_machine" binary input-id="fm-requires-machine" />
            <label for="fm-requires-machine">{{
              t('resources.fabricationMethods.fields.requiresMachine')
            }}</label>
          </label>
          <small class="hint">{{
            t('resources.fabricationMethods.fields.requiresMachineHint')
          }}</small>
        </div>

        <div class="field field-wide">
          <label class="checkbox-label">
            <Checkbox v-model="form.required_external" binary input-id="fm-required-external" />
            <label for="fm-required-external">{{
              t('resources.fabricationMethods.fields.requiredExternal')
            }}</label>
          </label>
          <small class="hint">{{
            t('resources.fabricationMethods.fields.requiredExternalHint')
          }}</small>
        </div>

        <div v-if="showLeadTimeField" class="field">
          <label for="fm-lead-time-days">{{
            t('resources.fabricationMethods.fields.leadTimeDays')
          }}</label>
          <InputNumber
            input-id="fm-lead-time-days"
            v-model="form.lead_time_days"
            :min="0"
            show-buttons
            fluid
          />
          <small class="hint">{{
            t('resources.fabricationMethods.fields.leadTimeDaysHint')
          }}</small>
        </div>

        <div class="field">
          <label for="fm-wait-after-minutes">{{
            t('resources.fabricationMethods.fields.waitAfterMinutes')
          }}</label>
          <InputNumber
            input-id="fm-wait-after-minutes"
            v-model="form.wait_after_minutes"
            :min="0"
            show-buttons
            fluid
          />
          <small class="hint">{{
            t('resources.fabricationMethods.fields.waitAfterMinutesHint')
          }}</small>
        </div>

        <div class="field field-wide">
          <label id="fm-default-supplier-label" for="fm-default-supplier">{{
            t('resources.fabricationMethods.fields.defaultSupplier')
          }}</label>
          <Select
            id="fm-default-supplier"
            aria-labelledby="fm-default-supplier-label"
            v-model="form.default_supplier_id"
            :options="supplierOptions"
            option-label="name"
            option-value="id"
            :loading="suppliersStore.loading"
            :placeholder="t('resources.fabricationMethods.fields.defaultSupplierPlaceholder')"
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
          <small class="hint">{{
            t('resources.fabricationMethods.fields.defaultSupplierHint')
          }}</small>
        </div>

        <div class="field field-wide">
          <label class="checkbox-label">
            <Checkbox
              v-model="form.default_for_assemblies"
              binary
              input-id="fm-default-for-assemblies"
              :disabled="isArchivedMethod"
            />
            <label for="fm-default-for-assemblies">{{
              t('resources.fabricationMethods.fields.defaultForAssemblies')
            }}</label>
          </label>
          <small class="hint">{{
            t('resources.fabricationMethods.fields.defaultForAssembliesHint')
          }}</small>
        </div>
      </div>

      <Message v-if="errorMessage" severity="error" class="mt-2">{{ errorMessage }}</Message>

      <div class="form-footer">
        <Button
          type="button"
          :label="t('common.cancel')"
          severity="secondary"
          @click="onCancel"
          :disabled="submitting"
        />
        <Button type="submit" :label="t('common.save')" :loading="submitting" />
      </div>
    </form>
  </Dialog>
</template>

<style scoped lang="scss">
.method-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.form-fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3) var(--space-4);
}

.field {
  label {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}

.field-wide {
  grid-column: 1 / -1;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
</style>
