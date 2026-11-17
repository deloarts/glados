<script setup lang="ts">
import { computed, useId } from 'vue'
import { useI18n } from 'vue-i18n'

import { useEntityFormDialog } from '@/shared/composables/useEntityFormDialog'
import LocalizedTextInput from '@/shared/components/forms/LocalizedTextInput.vue'
import { cleanLocalizedText, type LocalizedText } from '@/shared/utils/localizedText'
import { createProductDeviceKind, updateProductDeviceKind } from '../api/productDeviceResourcesApi'
import { useProductDeviceResourcesStore } from '../stores/productDeviceResourcesStore'
import {
  PARAMETER_TYPES,
  SIGNAL_TYPES,
  type ProductDeviceKind,
  type ProductDeviceParameterType,
  type ProductDeviceSignalType,
} from '../types/productDevice'

/**
 * Creates or edits a device kind together with its positions, parameters
 * and signals. A signal is one its devices typically have besides the
 * positions, such as a fault input; a device signal that picks it takes its
 * type, and its PLC name ends the tag. A row taken out of a list is
 * archived by the backend, never deleted, so devices that use it keep
 * resolving it.
 */
const props = defineProps<{ kind?: ProductDeviceKind }>()

const emit = defineEmits<{ saved: [kind: ProductDeviceKind] }>()
const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
// Prefixes the ids that tie each row input to its label.
const uid = useId()
const store = useProductDeviceResourcesStore()

interface PositionForm {
  key: number
  id: number | null
  label: LocalizedText
  takes_value: boolean
  unit: string
  plc_state_name: string
  plc_command_name: string
}

interface ParameterRow {
  key: number
  id: number | null
  label: LocalizedText
  unit: string
  value_type: ProductDeviceParameterType
}

interface SignalRow {
  key: number
  id: number | null
  label: LocalizedText
  signal_type: ProductDeviceSignalType
  plc_name: string
}

interface FormState {
  label: LocalizedText
  without_driving_medium: boolean
  positions: PositionForm[]
  parameters: ParameterRow[]
  signals: SignalRow[]
}

let nextKey = 0

function formFromKind(kind: ProductDeviceKind): FormState {
  return {
    label: { ...kind.label },
    without_driving_medium: kind.without_driving_medium,
    positions: kind.positions
      .filter((p) => !p.archived)
      .map((p) => ({
        key: nextKey++,
        id: p.id,
        label: { ...p.label },
        takes_value: p.takes_value,
        unit: p.unit ?? '',
        plc_state_name: p.plc_state_name ?? '',
        plc_command_name: p.plc_command_name ?? '',
      })),
    parameters: kind.parameters
      .filter((p) => !p.archived)
      .map((p) => ({
        key: nextKey++,
        id: p.id,
        label: { ...p.label },
        unit: p.unit ?? '',
        value_type: p.value_type,
      })),
    signals: kind.signals
      .filter((s) => !s.archived)
      .map((s) => ({
        key: nextKey++,
        id: s.id,
        label: { ...s.label },
        signal_type: s.signal_type,
        plc_name: s.plc_name,
      })),
  }
}

const { form, submitting, errorMessage, isEditMode, onSubmit, onCancel } = useEntityFormDialog<
  ProductDeviceKind,
  FormState
>({
  visible,
  entity: () => props.kind,
  emptyForm: () => ({ label: {}, without_driving_medium: false, positions: [], parameters: [], signals: [] }),
  formFromEntity: formFromKind,
  validate: (form) => {
    if (form.positions.some((p) => !plcNameValid(p.plc_state_name) || !plcNameValid(p.plc_command_name))) {
      return t('productDevices.resources.errors.plcName')
    }
    if (form.signals.some((s) => s.plc_name.trim() === '' || !plcNameValid(s.plc_name))) {
      return t('productDevices.resources.errors.signalPlcName')
    }
    const labels = [
      form.label,
      ...form.positions.map((p) => p.label),
      ...form.parameters.map((p) => p.label),
      ...form.signals.map((s) => s.label),
    ]
    return labels.some((label) => Object.keys(cleanLocalizedText(label)).length === 0)
      ? t('productDevices.resources.errors.labelRequired')
      : null
  },
  save: async (form, isEdit, kind) => {
    const body = {
      label: cleanLocalizedText(form.label),
      without_driving_medium: form.without_driving_medium,
      positions: form.positions.map((p) => ({
        id: p.id,
        label: cleanLocalizedText(p.label),
        takes_value: p.takes_value,
        unit: p.takes_value ? p.unit.trim() || null : null,
        plc_state_name: p.plc_state_name.trim() || null,
        plc_command_name: p.plc_command_name.trim() || null,
      })),
      parameters: form.parameters.map((p) => ({
        id: p.id,
        label: cleanLocalizedText(p.label),
        unit: p.unit.trim() || null,
        value_type: p.value_type,
      })),
      signals: form.signals.map((s) => ({
        id: s.id,
        label: cleanLocalizedText(s.label),
        signal_type: s.signal_type,
        plc_name: s.plc_name.trim(),
      })),
    }
    const saved =
      isEdit && kind ? await updateProductDeviceKind(kind.id, body) : await createProductDeviceKind(body)
    store.upsertKind(saved)
    return saved
  },
  onSaved: (saved) => emit('saved', saved),
  unknownErrorMessage: t('productDevices.resources.errors.unknown'),
})

const typeOptions = computed(() =>
  PARAMETER_TYPES.map((value) => ({
    value,
    label: t(`productDevices.resources.parameterTypes.${value}`),
  })),
)

function addPosition(): void {
  form.positions.push({
    key: nextKey++,
    id: null,
    label: {},
    takes_value: false,
    unit: '',
    plc_state_name: '',
    plc_command_name: '',
  })
}

/** A state or command name goes into PLC tags unchanged, so it holds only letters, digits and underscores. */
function plcNameValid(name: string): boolean {
  return name.trim() === '' || /^[A-Za-z0-9_]+$/.test(name.trim())
}

const signalTypeOptions = SIGNAL_TYPES.map((value) => ({
  value,
  label: t(`productDevices.devices.signalTypes.${value}`),
}))

function addSignal(): void {
  form.signals.push({ key: nextKey++, id: null, label: {}, signal_type: 'di', plc_name: '' })
}

function addParameter(): void {
  form.parameters.push({ key: nextKey++, id: null, label: {}, unit: '', value_type: 'number' })
}

function move<T>(list: T[], index: number, delta: number): void {
  const target = index + delta
  if (target < 0 || target >= list.length) return
  const [row] = list.splice(index, 1)
  if (row !== undefined) list.splice(target, 0, row)
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="
      isEditMode ? t('productDevices.resources.editKind') : t('productDevices.resources.createKind')
    "
    :style="{ width: 'var(--dialog-width-lg)' }"
  >
    <form class="kind-form" @submit.prevent="onSubmit">
      <LocalizedTextInput
        v-model="form.label"
        :label="t('productDevices.resources.fields.label')"
        :maxlength="200"
        required
      />
      <label class="row-check">
        <Checkbox v-model="form.without_driving_medium" binary data-testid="kind-without-medium" />
        {{ t('productDevices.resources.fields.withoutDrivingMedium') }}
      </label>
      <p class="hint">{{ t('productDevices.resources.withoutDrivingMediumHint') }}</p>

      <fieldset class="dialog-section">
        <legend>{{ t('productDevices.resources.positions') }}</legend>
        <p class="hint">{{ t('productDevices.resources.positionsHint') }}</p>
        <div v-for="(row, index) in form.positions" :key="row.key" class="row" data-testid="kind-position-row">
          <LocalizedTextInput
            v-model="row.label"
            class="row-label"
            :label="t('productDevices.resources.fields.positionLabel')"
            :maxlength="200"
            compact
            required
          />
          <label class="row-check">
            <Checkbox v-model="row.takes_value" binary />
            {{ t('productDevices.resources.fields.takesValue') }}
          </label>
          <div class="row-unit">
            <FloatLabel variant="on">
              <InputText
                :id="`${uid}-${row.key}-unit`"
                v-model="row.unit"
                size="small"
                :maxlength="20"
                :disabled="!row.takes_value"
                fluid
              />
              <label class="float-label" :for="`${uid}-${row.key}-unit`">{{ t('productDevices.resources.fields.unit') }}</label>
            </FloatLabel>
          </div>
          <div class="row-plc">
            <FloatLabel variant="on">
              <InputText
                :id="`${uid}-${row.key}-state`"
                v-model="row.plc_state_name"
                v-tooltip.bottom="t('productDevices.resources.plcStateNameHint')"
                size="small"
                :maxlength="40"
                :invalid="!plcNameValid(row.plc_state_name)"
                fluid
                data-testid="kind-position-state"
              />
              <label class="float-label" :for="`${uid}-${row.key}-state`">{{ t('productDevices.resources.fields.plcStateName') }}</label>
            </FloatLabel>
          </div>
          <div class="row-plc">
            <FloatLabel variant="on">
              <InputText
                :id="`${uid}-${row.key}-command`"
                v-model="row.plc_command_name"
                v-tooltip.bottom="t('productDevices.resources.plcCommandNameHint')"
                size="small"
                :maxlength="40"
                :invalid="!plcNameValid(row.plc_command_name)"
                fluid
                data-testid="kind-position-command"
              />
              <label class="float-label" :for="`${uid}-${row.key}-command`">{{ t('productDevices.resources.fields.plcCommandName') }}</label>
            </FloatLabel>
          </div>
          <div class="row-actions">
            <Button
              type="button"
              icon="mdi mdi-arrow-up"
              size="small"
              text
              severity="secondary"
              :disabled="index === 0"
              :aria-label="t('productDevices.resources.moveUp')"
              @click="move(form.positions, index, -1)"
            />
            <Button
              type="button"
              icon="mdi mdi-arrow-down"
              size="small"
              text
              severity="secondary"
              :disabled="index === form.positions.length - 1"
              :aria-label="t('productDevices.resources.moveDown')"
              @click="move(form.positions, index, 1)"
            />
            <Button
              type="button"
              icon="mdi mdi-close"
              size="small"
              text
              severity="danger"
              :aria-label="t('productDevices.resources.removeRow')"
              @click="form.positions.splice(index, 1)"
            />
          </div>
        </div>
        <Button
          type="button"
          icon="mdi mdi-plus"
          :label="t('productDevices.resources.addPosition')"
          size="small"
          text
          class="add-row"
          @click="addPosition"
        />
      </fieldset>

      <fieldset class="dialog-section">
        <legend>{{ t('productDevices.resources.signals') }}</legend>
        <p class="hint">{{ t('productDevices.resources.signalsHint') }}</p>
        <div v-for="(row, index) in form.signals" :key="row.key" class="row" data-testid="kind-signal-row">
          <LocalizedTextInput
            v-model="row.label"
            class="row-label"
            :label="t('productDevices.resources.fields.signalLabel')"
            :maxlength="200"
            compact
            required
          />
          <div class="row-signal-type">
            <FloatLabel variant="on">
              <Select
                v-model="row.signal_type"
                :input-id="`${uid}-${row.key}-type`"
                :aria-labelledby="`${uid}-${row.key}-type-label`"
                size="small"
                :options="signalTypeOptions"
                option-label="label"
                option-value="value"
                fluid
              />
              <label class="float-label" :id="`${uid}-${row.key}-type-label`" :for="`${uid}-${row.key}-type`">
                {{ t('productDevices.devices.fields.signalType') }}
              </label>
            </FloatLabel>
          </div>
          <div class="row-plc">
            <FloatLabel variant="on">
              <InputText
                :id="`${uid}-${row.key}-plc`"
                v-model="row.plc_name"
                v-tooltip.bottom="t('productDevices.resources.signalPlcNameHint')"
                size="small"
                :maxlength="40"
                :invalid="!plcNameValid(row.plc_name)"
                fluid
                data-testid="kind-signal-plc-name"
              />
              <label class="float-label" :for="`${uid}-${row.key}-plc`">{{ t('productDevices.resources.fields.signalPlcName') }}</label>
            </FloatLabel>
          </div>
          <div class="row-actions">
            <Button
              type="button"
              icon="mdi mdi-arrow-up"
              size="small"
              text
              severity="secondary"
              :disabled="index === 0"
              :aria-label="t('productDevices.resources.moveUp')"
              @click="move(form.signals, index, -1)"
            />
            <Button
              type="button"
              icon="mdi mdi-arrow-down"
              size="small"
              text
              severity="secondary"
              :disabled="index === form.signals.length - 1"
              :aria-label="t('productDevices.resources.moveDown')"
              @click="move(form.signals, index, 1)"
            />
            <Button
              type="button"
              icon="mdi mdi-close"
              size="small"
              text
              severity="danger"
              :aria-label="t('productDevices.resources.removeRow')"
              @click="form.signals.splice(index, 1)"
            />
          </div>
        </div>
        <Button
          type="button"
          icon="mdi mdi-plus"
          :label="t('productDevices.resources.addSignal')"
          size="small"
          text
          class="add-row"
          data-testid="kind-add-signal"
          @click="addSignal"
        />
      </fieldset>

      <fieldset class="dialog-section">
        <legend>{{ t('productDevices.resources.parameters') }}</legend>
        <div v-for="(row, index) in form.parameters" :key="row.key" class="row">
          <LocalizedTextInput
            v-model="row.label"
            class="row-label"
            :label="t('productDevices.resources.fields.parameterLabel')"
            :maxlength="200"
            compact
            required
          />
          <div class="row-type">
            <FloatLabel variant="on">
              <Select
                v-model="row.value_type"
                :input-id="`${uid}-${row.key}-value-type`"
                :aria-labelledby="`${uid}-${row.key}-value-type-label`"
                size="small"
                :options="typeOptions"
                option-label="label"
                option-value="value"
                fluid
              />
              <label class="float-label" :id="`${uid}-${row.key}-value-type-label`" :for="`${uid}-${row.key}-value-type`">
                {{ t('productDevices.resources.fields.valueType') }}
              </label>
            </FloatLabel>
          </div>
          <div class="row-unit">
            <FloatLabel variant="on">
              <InputText
                :id="`${uid}-${row.key}-unit`"
                v-model="row.unit"
                size="small"
                :maxlength="20"
                :disabled="row.value_type !== 'number'"
                fluid
              />
              <label class="float-label" :for="`${uid}-${row.key}-unit`">{{ t('productDevices.resources.fields.unit') }}</label>
            </FloatLabel>
          </div>
          <div class="row-actions">
            <Button
              type="button"
              icon="mdi mdi-arrow-up"
              size="small"
              text
              severity="secondary"
              :disabled="index === 0"
              :aria-label="t('productDevices.resources.moveUp')"
              @click="move(form.parameters, index, -1)"
            />
            <Button
              type="button"
              icon="mdi mdi-arrow-down"
              size="small"
              text
              severity="secondary"
              :disabled="index === form.parameters.length - 1"
              :aria-label="t('productDevices.resources.moveDown')"
              @click="move(form.parameters, index, 1)"
            />
            <Button
              type="button"
              icon="mdi mdi-close"
              size="small"
              text
              severity="danger"
              :aria-label="t('productDevices.resources.removeRow')"
              @click="form.parameters.splice(index, 1)"
            />
          </div>
        </div>
        <Button
          type="button"
          icon="mdi mdi-plus"
          :label="t('productDevices.resources.addParameter')"
          size="small"
          text
          class="add-row"
          @click="addParameter"
        />
      </fieldset>
    </form>

    <template #footer>
      <Message v-if="errorMessage" severity="error" size="small" class="footer-error">{{ errorMessage }}</Message>
      <Button
        type="button"
        :label="t('common.cancel')"
        severity="secondary"
        text
        :disabled="submitting"
        @click="onCancel"
      />
      <Button :label="t('common.save')" icon="mdi mdi-content-save-outline" :loading="submitting" @click="onSubmit" />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.kind-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

// The error sits left of the buttons, so it shows however far the form is scrolled.
.footer-error {
  flex: 1 1 auto;
  align-self: center;
}

.add-row {
  align-self: flex-start;
}

.row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.row-label {
  flex: 1;
  min-width: 0;
}

.row-plc {
  width: 7.5rem;
}

.row-check {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  white-space: nowrap;
}

.row-type {
  width: 9rem;
}

.row-signal-type {
  width: 8rem;
}

.row-unit {
  width: 6rem;
}

// A label on the border stays on one line and is cut short when the input is narrow.
.float-label {
  max-width: calc(100% - 1rem);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hint {
  margin: 0;
}
</style>
