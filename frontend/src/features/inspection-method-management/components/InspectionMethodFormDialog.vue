<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { API_MAX_PAGE_SIZE } from '@/core/constants/table'
import { useErrorToast } from '@/core/composables/useErrorToast'

import { useEntityFormDialog } from '@/shared/composables/useEntityFormDialog'
import LabelColorPairField from '@/shared/components/forms/LabelColorPairField.vue'
import LocalizedTextInput from '@/shared/components/forms/LocalizedTextInput.vue'
import { useLocalizedText } from '@/shared/composables/useLocalizedText'
import { getProductionMachines } from '@/features/production-machines'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'
import { DEFAULT_LABEL_COLOR, DEFAULT_LABEL_FONT_COLOR } from '@/shared/utils/labelColors'
import { cleanLocalizedText, type LocalizedText } from '@/shared/utils/localizedText'
import { useHostStore } from '@/core/host/stores/hostStore'
import type { ProductionMachineResponse } from '@/features/production-machines'
import { useInspectionMethodsStore } from '@/features/inspection-methods'
import type { InspectionMethodResponse } from '@/features/inspection-methods'

interface Props {
  method?: InspectionMethodResponse
}

const props = defineProps<Props>()

const emit = defineEmits<{
  saved: [method: InspectionMethodResponse]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const host = useHostStore()
const { localize } = useLocalizedText()
const { toastOnError } = useErrorToast()
const store = useInspectionMethodsStore()

interface FormState {
  name: LocalizedText
  description: LocalizedText
  label_color: string
  label_font_color: string
  // null means no default; a step then starts without an estimate.
  default_setup_minutes: number | null
  default_minutes_per_piece: number | null
  requires_evidence: boolean
  // null means manual QA work without a machine.
  default_machine_id: number | null
}

function createEmptyForm(): FormState {
  return {
    name: {},
    description: {},
    label_color: DEFAULT_LABEL_COLOR,
    label_font_color: DEFAULT_LABEL_FONT_COLOR,
    default_setup_minutes: null,
    default_minutes_per_piece: null,
    requires_evidence: false,
    default_machine_id: null,
  }
}

function formFromMethod(method: InspectionMethodResponse): FormState {
  return {
    name: { ...method.name },
    description: { ...method.description },
    label_color: method.label_color ?? DEFAULT_LABEL_COLOR,
    label_font_color: method.label_font_color ?? DEFAULT_LABEL_FONT_COLOR,
    default_setup_minutes: method.default_setup_minutes,
    default_minutes_per_piece: method.default_minutes_per_piece,
    requires_evidence: method.requires_evidence,
    default_machine_id: method.default_machine_id,
  }
}

// There is no server-side QA machine filter, so the full page is fetched
// once and narrowed client-side.
const machines = ref<ProductionMachineResponse[]>([])
const loadingMachines = ref(false)

async function loadMachines(): Promise<void> {
  loadingMachines.value = true
  try {
    const result = await getProductionMachines({ limit: API_MAX_PAGE_SIZE, include_archived: true })
    machines.value = result.items
  } finally {
    loadingMachines.value = false
  }
}

const qaMachines = computed(() => machines.value.filter((m) => m.is_qa_machine))

// Archived machines stay selectable, sorted last.
const { sortedOptions: qaMachineOptions, isArchived } = useArchivableOptions(qaMachines)

onMounted(() => {
  loadMachines().catch(toastOnError())
})

const { form, submitting, errorMessage, isEditMode, onSubmit, onCancel } = useEntityFormDialog<
  InspectionMethodResponse,
  FormState
>({
  visible,
  entity: () => props.method,
  emptyForm: createEmptyForm,
  formFromEntity: formFromMethod,
  validate: (form) =>
    form.name[host.defaultLanguage]?.trim() ? null : t('resources.inspectionMethods.errors.required'),
  save: (form, isEditMode, method) => {
    const payload = {
      name: cleanLocalizedText(form.name),
      description: cleanLocalizedText(form.description),
      label_color: form.label_color,
      label_font_color: form.label_font_color,
      default_setup_minutes: form.default_setup_minutes,
      default_minutes_per_piece: form.default_minutes_per_piece,
      requires_evidence: form.requires_evidence,
      default_machine_id: form.default_machine_id,
    }
    return isEditMode && method
      ? store.update(method.id, payload)
      : store.create(payload)
  },
  onSaved: (saved) => emit('saved', saved),
  unknownErrorMessage: t('resources.inspectionMethods.errors.unknown'),
})

const selectedMachine = computed<ProductionMachineResponse | null>(
  () => qaMachineOptions.value.find((m) => m.id === form.default_machine_id) ?? null,
)
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="
      isEditMode
        ? t('resources.inspectionMethods.editMethod')
        : t('resources.inspectionMethods.createMethod')
    "
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <form class="method-form" @submit.prevent="onSubmit">
      <div class="form-fields">
        <div class="field field-wide">
          <LocalizedTextInput
            v-model="form.name"
            :label="`${t('resources.inspectionMethods.fields.name')} *`"
            :maxlength="200"
            required
          />
        </div>

        <div class="field field-wide">
          <LocalizedTextInput
            v-model="form.description"
            :label="t('resources.inspectionMethods.fields.description')"
            :maxlength="4000"
            multiline
          />
        </div>

        <LabelColorPairField
          v-model:color="form.label_color"
          v-model:font-color="form.label_font_color"
          color-id="im-label-color"
          font-color-id="im-font-color"
          :color-label="t('resources.inspectionMethods.fields.labelColor')"
          :font-color-label="t('resources.inspectionMethods.fields.labelFontColor')"
          :preview-label="t('resources.inspectionMethods.fields.preview')"
          :preview-text="localize(form.name) || t('resources.inspectionMethods.fields.previewPlaceholder')"
        />

        <div class="field">
          <label for="im-setup-minutes">{{
            t('resources.inspectionMethods.fields.defaultSetupMinutes')
          }}</label>
          <InputNumber
            input-id="im-setup-minutes"
            v-model="form.default_setup_minutes"
            :min="0"
            fluid
          />
        </div>

        <div class="field">
          <label for="im-per-piece-minutes">{{
            t('resources.inspectionMethods.fields.defaultMinutesPerPiece')
          }}</label>
          <InputNumber
            input-id="im-per-piece-minutes"
            v-model="form.default_minutes_per_piece"
            :min="0"
            :min-fraction-digits="0"
            :max-fraction-digits="2"
            fluid
          />
        </div>

        <div class="field field-wide">
          <small class="hint">{{
            t('resources.inspectionMethods.fields.defaultDurationsHint')
          }}</small>
        </div>

        <div class="field field-wide">
          <label id="im-default-machine-label" for="im-default-machine">{{
            t('resources.inspectionMethods.fields.defaultMachine')
          }}</label>
          <Select
            input-id="im-default-machine"
            aria-labelledby="im-default-machine-label"
            v-model="form.default_machine_id"
            :options="qaMachineOptions"
            option-label="internal_name"
            option-value="id"
            show-clear
            :loading="loadingMachines"
            :placeholder="t('resources.inspectionMethods.fields.defaultMachinePlaceholder')"
            fluid
          >
            <template #option="{ option }">
              <span>{{ option.internal_name }}</span>
              <ArchivedOptionTag v-if="option.archived" />
            </template>
            <template #value>
              <span v-if="selectedMachine">{{ selectedMachine.internal_name }}</span>
              <ArchivedOptionTag v-if="selectedMachine?.archived" />
            </template>
          </Select>
          <ArchivedSelectionWarning v-if="isArchived(selectedMachine)" />
          <small class="hint">{{
            t('resources.inspectionMethods.fields.defaultMachineHint')
          }}</small>
        </div>

        <div class="field field-wide">
          <label class="checkbox-label">
            <Checkbox v-model="form.requires_evidence" binary input-id="im-requires-evidence" />
            <label for="im-requires-evidence">{{
              t('resources.inspectionMethods.fields.requiresEvidence')
            }}</label>
          </label>
          <small class="hint">{{
            t('resources.inspectionMethods.fields.requiresEvidenceHint')
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
