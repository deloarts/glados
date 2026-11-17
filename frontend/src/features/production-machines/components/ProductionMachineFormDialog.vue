<script setup lang="ts">
import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { computed, onMounted, reactive, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useFabricationMethodsStore } from '@/features/fabrication-methods'
import { useProductionMachinesStore } from '../stores/productionMachinesStore'

import type { ProductionMachineResponse } from '../types/productionMachinesResponse'
import { labelName } from '@/shared/utils/localizeLabel'

interface Props {
  machine?: ProductionMachineResponse | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  saved: [machine: ProductionMachineResponse]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const store = useProductionMachinesStore()
const fabricationMethodsStore = useFabricationMethodsStore()

const isEditMode = computed(() => !!props.machine)

interface FormState {
  internal_name: string
  vendor: string
  model: string
  fabrication_method_ids: number[]
  max_part_dimension: string
  note: string
  is_qa_machine: boolean
}

function createEmptyForm(): FormState {
  return {
    internal_name: '',
    vendor: '',
    model: '',
    fabrication_method_ids: [],
    max_part_dimension: '',
    note: '',
    is_qa_machine: false,
  }
}

function formFromMachine(machine: ProductionMachineResponse): FormState {
  return {
    internal_name: machine.internal_name,
    vendor: machine.vendor,
    model: machine.model,
    fabrication_method_ids: [...machine.fabrication_method_ids],
    max_part_dimension: machine.max_part_dimension ?? '',
    note: machine.note ?? '',
    is_qa_machine: machine.is_qa_machine,
  }
}

const form = reactive<FormState>(createEmptyForm())
const { submitting, errorMessage, run } = useSubmitAction()

onMounted(() => {
  if (fabricationMethodsStore.items.length === 0) {
    void fabricationMethodsStore.refresh()
  }
})

watch(visible, (isVisible) => {
  if (!isVisible) return
  errorMessage.value = null
  if (props.machine) {
    Object.assign(form, formFromMachine(props.machine))
  } else {
    Object.assign(form, createEmptyForm())
  }
})

// A QA machine never does fabrication, so ticking the box clears and
// disables the capabilities.
watch(
  () => form.is_qa_machine,
  (isQaMachine) => {
    if (isQaMachine) {
      form.fabrication_method_ids = []
    }
  },
)

function isFormValid(): boolean {
  return (
    form.internal_name.trim().length > 0 &&
    form.vendor.trim().length > 0 &&
    form.model.trim().length > 0
  )
}

async function onSubmit(): Promise<void> {
  if (!isFormValid()) {
    errorMessage.value = t('productionMachines.create.errors.required')
    return
  }

  await run(async () => {
    let saved: ProductionMachineResponse

    const payload = {
      internal_name: form.internal_name.trim(),
      vendor: form.vendor.trim(),
      model: form.model.trim(),
      // A QA machine never persists capabilities, whatever the form holds.
      fabrication_method_ids: form.is_qa_machine ? [] : form.fabrication_method_ids,
      max_part_dimension: form.max_part_dimension.trim() || null,
      note: form.note.trim() || null,
      is_qa_machine: form.is_qa_machine,
    }

    if (isEditMode.value && props.machine) {
      saved = await store.update(props.machine.id, payload)
    } else {
      saved = await store.create(payload)
    }

    visible.value = false
    emit('saved', saved)
  }, t('productionMachines.create.errors.unknown'))
}

function onCancel(): void {
  visible.value = false
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="
      isEditMode
        ? t('productionMachines.create.editTitle')
        : t('productionMachines.create.createTitle')
    "
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <form class="machine-form" @submit.prevent="onSubmit">
      <div class="form-fields">
        <div class="field field-wide">
          <label for="pm-internal-name"
            >{{ t('productionMachines.create.fields.internalName') }} *</label
          >
          <InputText id="pm-internal-name" v-model="form.internal_name" fluid autocomplete="off" />
        </div>

        <div class="field">
          <label for="pm-vendor">{{ t('productionMachines.create.fields.vendor') }} *</label>
          <InputText id="pm-vendor" v-model="form.vendor" fluid autocomplete="off" />
        </div>

        <div class="field">
          <label for="pm-model">{{ t('productionMachines.create.fields.model') }} *</label>
          <InputText id="pm-model" v-model="form.model" fluid autocomplete="off" />
        </div>

        <div class="field field-wide">
          <label id="pm-capabilities-label" for="pm-capabilities">{{
            t('productionMachines.create.fields.capabilities')
          }}</label>
          <MultiSelect
            id="pm-capabilities"
            aria-labelledby="pm-capabilities-label"
            v-model="form.fabrication_method_ids"
            :options="fabricationMethodsStore.items"
            :option-label="labelName"
            option-value="id"
            :loading="fabricationMethodsStore.loading"
            :disabled="form.is_qa_machine"
            :placeholder="t('productionMachines.create.fields.capabilitiesPlaceholder')"
            display="chip"
            filter
            fluid
          />
          <span class="field-hint">{{
            form.is_qa_machine
              ? t('productionMachines.create.fields.capabilitiesQaDisabledHint')
              : t('productionMachines.create.fields.capabilitiesHint')
          }}</span>
        </div>

        <div class="field">
          <label for="pm-max-part-dimension">
            {{ t('productionMachines.create.fields.maxPartDimension') }}
          </label>
          <InputText
            id="pm-max-part-dimension"
            v-model="form.max_part_dimension"
            fluid
            autocomplete="off"
          />
        </div>

        <div class="field field-wide">
          <div class="checkbox-row">
            <Checkbox v-model="form.is_qa_machine" input-id="pm-is-qa-machine" binary />
            <label for="pm-is-qa-machine">{{
              t('productionMachines.create.fields.isQaMachine')
            }}</label>
          </div>
          <span class="field-hint">{{
            t('productionMachines.create.fields.isQaMachineHint')
          }}</span>
        </div>

        <div class="field field-wide">
          <label for="pm-note">{{ t('productionMachines.create.fields.note') }}</label>
          <Textarea id="pm-note" v-model="form.note" rows="3" fluid auto-resize />
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
.machine-form {
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

.checkbox-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);

  label {
    font-size: var(--font-size-sm);
    font-weight: 500;
    cursor: pointer;
  }
}
</style>
