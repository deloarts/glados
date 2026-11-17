<script setup lang="ts">
// Logs a machine going down: opened from the machine table's row context
// menu ("Add downtime"), always for one already-known machine, so the
// machine itself is shown read-only rather than picked from a list.
import { computed, reactive, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { instantToPickerDate, pickerDateToInstant } from '@/core/utils/dates'
import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { HelpDrawer } from '@/shared/help'
import { addMachineDowntime } from '../api/addMachineDowntime'

import type { ProductionMachineResponse } from '../types/productionMachinesResponse'
import type { MachineDowntimeReason, MachineDowntimeResponse } from '../types/machineDowntimeResponse'

interface Props {
  machine: ProductionMachineResponse | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  saved: [downtime: MachineDowntimeResponse]
}>()

const visible = defineModel<boolean>('visible', { default: false })
const explainVisible = ref(false)

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()

const REASONS: MachineDowntimeReason[] = [
  'breakdown',
  'maintenance',
  'tooling',
  'no_operator',
  'no_material',
  'other',
]

const reasonOptions = computed(() =>
  REASONS.map((value) => ({ value, label: t(`productionMachines.downtime.reasons.${value}`) })),
)

// The pickers show the tenant's wall clock, so their values go through
// instantToPickerDate and pickerDateToInstant rather than straight to ISO.
interface FormState {
  started_at: Date | null
  ended_at: Date | null
  reason: MachineDowntimeReason | null
  note: string
}

function createEmptyForm(): FormState {
  return { started_at: instantToPickerDate(new Date()), ended_at: null, reason: null, note: '' }
}

const form = reactive<FormState>(createEmptyForm())
const { submitting, errorMessage, run } = useSubmitAction()

watch(visible, (isVisible) => {
  if (!isVisible) return
  errorMessage.value = null
  Object.assign(form, createEmptyForm())
})

function isFormValid(): boolean {
  return form.started_at !== null && form.reason !== null
}

async function onSubmit(): Promise<void> {
  const machine = props.machine
  if (!machine) return
  if (!isFormValid()) {
    errorMessage.value = t('productionMachines.downtime.form.errors.required')
    return
  }

  await run(async () => {
    const saved = await addMachineDowntime({
      machine_id: machine.id,
      started_at: pickerDateToInstant(form.started_at!).toISOString(),
      ended_at: form.ended_at ? pickerDateToInstant(form.ended_at).toISOString() : null,
      reason: form.reason!,
      note: form.note.trim() || null,
    })

    visible.value = false
    emit('saved', saved)
  }, t('productionMachines.downtime.form.errors.unknown'))
}

function onCancel(): void {
  visible.value = false
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <template #header>
      <div class="downtime-form-dialog-header">
        <span class="p-dialog-title">{{ t('productionMachines.downtime.form.addTitle') }}</span>
        <Button
          type="button"
          class="downtime-form-dialog-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('productionMachines.downtime.form.explain')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('productionMachines.downtime.form.explain')"
          data-testid="downtime-form-dialog-explain"
          @click="explainVisible = true"
        />
      </div>
    </template>
    <form class="downtime-form" @submit.prevent="onSubmit">
      <div class="form-fields">
        <div class="field field-wide">
          <label :for="`${uid}-machine`">{{ t('productionMachines.downtime.form.fields.machine') }}</label>
          <InputText :id="`${uid}-machine`" :model-value="machine?.internal_name ?? ''" disabled fluid />
        </div>

        <div class="field">
          <label for="dt-started-at"
            >{{ t('productionMachines.downtime.form.fields.startedAt') }} *</label
          >
          <DatePicker
            id="dt-started-at"
            v-model="form.started_at"
            show-time
            hour-format="24"
            show-icon
            fluid
          />
        </div>

        <div class="field">
          <label for="dt-ended-at">{{
            t('productionMachines.downtime.form.fields.endedAt')
          }}</label>
          <DatePicker
            id="dt-ended-at"
            v-model="form.ended_at"
            show-time
            hour-format="24"
            show-icon
            show-button-bar
            fluid
          />
          <span class="field-hint">{{
            t('productionMachines.downtime.form.fields.endedAtHint')
          }}</span>
        </div>

        <div class="field field-wide">
          <label id="dt-reason-label" for="dt-reason">{{ t('productionMachines.downtime.form.fields.reason') }} *</label>
          <Select
            id="dt-reason"
            aria-labelledby="dt-reason-label"
            v-model="form.reason"
            :options="reasonOptions"
            option-label="label"
            option-value="value"
            :placeholder="t('productionMachines.downtime.form.fields.reasonPlaceholder')"
            fluid
          />
        </div>

        <div class="field field-wide">
          <label for="dt-note">{{ t('productionMachines.downtime.form.fields.note') }}</label>
          <Textarea id="dt-note" v-model="form.note" rows="3" fluid auto-resize />
        </div>
      </div>

      <Message v-if="errorMessage" severity="error" class="mt-2">{{ errorMessage }}</Message>

      <div class="form-footer">
        <Button
          type="button"
          :label="t('common.cancel')"
          severity="secondary"
          :disabled="submitting"
          @click="onCancel"
        />
        <Button type="submit" :label="t('common.save')" :loading="submitting" />
      </div>
    </form>
  </Dialog>
  <HelpDrawer v-model:visible="explainVisible" slug="resources/machines" anchor="downtimes" />
</template>

<style scoped lang="scss">
.downtime-form-dialog-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.downtime-form-dialog-explain-button :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.downtime-form {
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

.form-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}
</style>
