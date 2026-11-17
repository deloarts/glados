<script setup lang="ts">
import { computed, reactive, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useErrorToast } from '@/core/composables/useErrorToast'
import { BoughtItemSelect, getBoughtItems } from '@/features/bought-items'
import type { BoughtItemResponse } from '@/features/bought-items'
import { useLocalizedText } from '@/shared/composables/useLocalizedText'
import { useProductDeviceResourcesStore } from '../stores/productDeviceResourcesStore'
import type { ProductDeviceComponentForm, SignalForm } from '../utils/deviceForm'
import { INPUT_SIGNAL_TYPES, newComponentForm, newSignal, OUTPUT_SIGNAL_TYPES } from '../utils/deviceForm'
import { SIGNAL_TYPES, type ProductDeviceKind, type ProductDeviceSignalType } from '../types/productDevice'

/**
 * The optional parts of a device: valve, sensors and the actuator itself.
 * A part has no name of its own; it has a role, an optional catalogue item,
 * an optional EPLAN tag, ISO 13849-1 reliability data and its PLC signals.
 * Each input signal may confirm a position of the device's kind, so one part
 * can confirm both end positions, and each output may name the position it
 * drives to. A signal may instead be one of the kind's signals, such as a
 * fault input, which sets its type; one picker offers both. Its meaning is
 * then optional. A signal carries its PLC address, an optional tag suffix
 * that replaces the PLC name, and a safety flag; a new signal of a
 * safety-relevant device starts as a safety signal.
 */
const props = defineProps<{
  kind?: ProductDeviceKind
  disabled?: boolean
  safetyRelevant?: boolean
}>()

const rows = defineModel<ProductDeviceComponentForm[]>({ required: true })

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const { toastOnError } = useErrorToast()
const { localize } = useLocalizedText()
const resources = useProductDeviceResourcesStore()

function roleOptions(currentId: number | null) {
  return resources
    .optionsOf('component_role', true)
    .filter((role) => !role.archived || role.id === currentId)
    .map((role) => ({ value: role.id, label: localize(role.label) }))
}

/** What the position field means for a signal type: confirmed for an input, driven to for an output. */
function positionPlaceholder(type: ProductDeviceSignalType): string {
  if (INPUT_SIGNAL_TYPES.includes(type)) return t('productDevices.devices.fields.confirmsPosition')
  if (OUTPUT_SIGNAL_TYPES.includes(type)) return t('productDevices.devices.fields.drivesPosition')
  return t('productDevices.devices.fields.noPosition')
}

// Archived positions and kind signals stay offered while a signal still names one.
const signals = computed(() => rows.value.flatMap((row) => row.signals))
const positions = computed(() =>
  (props.kind?.positions ?? []).filter((p) => !p.archived || signals.value.some((s) => s.position_id === p.id)),
)
const kindSignals = computed(() =>
  (props.kind?.signals ?? []).filter((k) => !k.archived || signals.value.some((s) => s.kind_signal_id === k.id)),
)

/** The picker's choices: the positions for an input or output, then every kind signal with its type. */
function pickOptions(type: ProductDeviceSignalType) {
  const groups = []
  if (type !== 'bus' && positions.value.length) {
    groups.push({
      label: t('productDevices.devices.fields.positionsGroup'),
      items: positions.value.map((p) => ({ value: `position:${p.id}`, label: localize(p.label) })),
    })
  }
  if (kindSignals.value.length) {
    groups.push({
      label: t('productDevices.devices.fields.kindSignalsGroup'),
      items: kindSignals.value.map((k) => ({
        value: `signal:${k.id}`,
        label: `${localize(k.label)} · ${t(`productDevices.devices.signalTypes.${k.signal_type}`)}`,
      })),
    })
  }
  return groups
}

function picked(signal: SignalForm): string | null {
  if (signal.kind_signal_id !== null) return `signal:${signal.kind_signal_id}`
  return signal.position_id !== null ? `position:${signal.position_id}` : null
}

// A kind signal brings its type and names no position.
function pick(signal: SignalForm, value: string | null): void {
  const [what, id] = (value ?? '').split(':')
  signal.position_id = what === 'position' ? Number(id) : null
  signal.kind_signal_id = what === 'signal' ? Number(id) : null
  const kindSignal = kindSignals.value.find((k) => k.id === signal.kind_signal_id)
  if (kindSignal) signal.signal_type = kindSignal.signal_type
}

// Another type drops a kind signal of a different type, and a bus signal names no position.
function setType(signal: SignalForm, type: ProductDeviceSignalType): void {
  signal.signal_type = type
  const kindSignal = kindSignals.value.find((k) => k.id === signal.kind_signal_id)
  if (kindSignal && kindSignal.signal_type !== type) signal.kind_signal_id = null
  if (type === 'bus') signal.position_id = null
}

function pickPlaceholder(type: ProductDeviceSignalType): string {
  return kindSignals.value.length ? t('productDevices.devices.fields.positionOrSignal') : positionPlaceholder(type)
}

const signalTypeOptions = SIGNAL_TYPES.map((value) => ({
  value,
  label: t(`productDevices.devices.signalTypes.${value}`),
}))

function addComponent(): void {
  rows.value = [...rows.value, newComponentForm()]
}

function removeComponent(index: number): void {
  rows.value = rows.value.filter((_, i) => i !== index)
}

// The form keeps the item id only; the full items, which the select shows
// with article name, order code and manufacturer, are fetched once per id.
// A failed fetch is reported and forgotten, so the next change retries it.
const boughtItems = reactive(new Map<number, BoughtItemResponse>())
const requested = new Set<number>()

watch(
  () => rows.value.map((row) => row.bought_item_id),
  (ids) => {
    for (const id of ids) {
      if (id === null || requested.has(id)) continue
      requested.add(id)
      getBoughtItems({ id, limit: 1, include_archived: true })
        .then((page) => {
          const [item] = page.items
          if (item) boughtItems.set(item.id, item)
        })
        .catch((e: unknown) => {
          requested.delete(id)
          toastOnError()(e)
        })
    }
  },
  { immediate: true },
)

function selectedItem(row: ProductDeviceComponentForm): BoughtItemResponse | null {
  return row.bought_item_id === null ? null : (boughtItems.get(row.bought_item_id) ?? null)
}

function pickBoughtItem(row: ProductDeviceComponentForm, item: BoughtItemResponse | null): void {
  row.bought_item_id = item?.id ?? null
  if (item) {
    boughtItems.set(item.id, item)
    requested.add(item.id)
  }
}
</script>

<template>
  <fieldset class="dialog-section components-editor">
    <legend>{{ t('productDevices.devices.components') }}</legend>
    <p v-if="rows.length === 0" class="hint">{{ t('productDevices.devices.noComponents') }}</p>

    <Panel
      v-for="(row, index) in rows"
      :key="row.key"
      class="component-panel"
      toggleable
      :header="
        roleOptions(row.role_id).find((r) => r.value === row.role_id)?.label ??
        t('productDevices.devices.newComponent')
      "
    >
      <template #icons>
        <Button
          type="button"
          icon="mdi mdi-close"
          size="small"
          text
          severity="danger"
          :disabled="disabled"
          :aria-label="t('productDevices.devices.removeComponent')"
          @click="removeComponent(index)"
        />
      </template>
      <div class="component-grid">
        <div class="field">
          <label :id="`pdc-role-${row.key}-label`" :for="`pdc-role-${row.key}`">{{ t('productDevices.devices.fields.role') }} *</label>
          <Select
            v-model="row.role_id"
            :input-id="`pdc-role-${row.key}`"
            :aria-labelledby="`pdc-role-${row.key}-label`"
            :options="roleOptions(row.role_id)"
            option-label="label"
            option-value="value"
            :disabled="disabled"
            size="small"
            fluid
          />
        </div>
        <div class="field">
          <label :for="`pdc-tag-${row.key}`">{{ t('productDevices.devices.fields.eplanTag') }}</label>
          <InputText
            :id="`pdc-tag-${row.key}`"
            v-model="row.eplan_tag"
            :maxlength="60"
            :disabled="disabled"
            size="small"
            fluid
          />
        </div>
        <div class="field">
          <label :for="`pdc-b10d-${row.key}`">{{ t('productDevices.devices.fields.b10d') }}</label>
          <InputNumber
            v-model="row.b10d_cycles"
            :input-id="`pdc-b10d-${row.key}`"
            :min="1"
            :disabled="disabled"
            size="small"
            fluid
          />
        </div>
        <div class="field">
          <label :for="`pdc-mttfd-${row.key}`">{{ t('productDevices.devices.fields.mttfd') }}</label>
          <InputNumber
            v-model="row.mttfd_years"
            :input-id="`pdc-mttfd-${row.key}`"
            :min="0"
            :max-fraction-digits="1"
            :disabled="disabled"
            size="small"
            fluid
          />
        </div>
        <div class="field field-wide">
          <label :id="`pdc-item-${row.key}-label`" :for="`pdc-item-${row.key}`">{{ t('productDevices.devices.fields.boughtItem') }}</label>
          <BoughtItemSelect
            :model-value="selectedItem(row)"
            :input-id="`pdc-item-${row.key}`"
            :aria-labelledby="`pdc-item-${row.key}-label`"
            :disabled="disabled"
            :placeholder="t('productDevices.devices.pickBoughtItem')"
            show-clear
            size="small"
            fluid
            class="bought-item-select"
            data-testid="component-bought-item"
            @update:model-value="pickBoughtItem(row, $event)"
          />
        </div>
        <div class="field field-wide">
          <!-- eslint-disable-next-line vuejs-accessibility/label-has-for -- captions every row below, each control names it through aria-labelledby -->
          <label :id="`${uid}-signals-label-${row.key}`">{{ t('productDevices.devices.fields.signals') }}</label>
          <div v-for="(signal, signalIndex) in row.signals" :key="signalIndex" class="signal-row">
            <Select
              :aria-labelledby="`${uid}-signals-label-${row.key}`"
              :model-value="signal.signal_type"
              :options="signalTypeOptions"
              option-label="label"
              option-value="value"
              :disabled="disabled"
              :aria-label="t('productDevices.devices.fields.signalType')"
              size="small"
              class="signal-type"
              @update:model-value="(type: ProductDeviceSignalType) => setType(signal, type)"
            />
            <Select
              :model-value="picked(signal)"
              :options="pickOptions(signal.signal_type)"
              option-label="label"
              option-value="value"
              option-group-label="label"
              option-group-children="items"
              show-clear
              :disabled="disabled || pickOptions(signal.signal_type).length === 0"
              :placeholder="pickPlaceholder(signal.signal_type)"
              :aria-label="pickPlaceholder(signal.signal_type)"
              size="small"
              class="signal-position"
              data-testid="signal-position"
              @update:model-value="(value: string | null) => pick(signal, value)"
            />
            <InputText
              v-model="signal.meaning"
              :maxlength="80"
              :disabled="disabled"
              :placeholder="
                signal.position_id !== null || signal.kind_signal_id !== null
                  ? t('productDevices.devices.fields.signalMeaningOptional')
                  : t('productDevices.devices.fields.signalMeaning')
              "
              :aria-label="t('productDevices.devices.fields.signalMeaning')"
              size="small"
              class="signal-meaning"
            />
            <InputText
              v-model="signal.address"
              v-tooltip.bottom="t('productDevices.devices.signalAddressHint')"
              :maxlength="30"
              :disabled="disabled"
              :placeholder="t('productDevices.devices.fields.signalAddress')"
              :aria-label="t('productDevices.devices.fields.signalAddress')"
              size="small"
              class="signal-address"
              data-testid="signal-address"
            />
            <InputText
              v-model="signal.tag_suffix"
              v-tooltip.bottom="t('productDevices.devices.signalSuffixHint')"
              :maxlength="60"
              :disabled="disabled"
              :invalid="signal.tag_suffix.trim() !== '' && !/^[A-Za-z0-9_]+$/.test(signal.tag_suffix.trim())"
              :placeholder="t('productDevices.devices.fields.signalSuffix')"
              :aria-label="t('productDevices.devices.fields.signalSuffix')"
              size="small"
              class="signal-suffix"
              data-testid="signal-suffix"
            />
            <ToggleButton
              v-model="signal.safety"
              v-tooltip.bottom="t('productDevices.devices.fields.signalSafety')"
              on-icon="mdi mdi-shield-alert"
              off-icon="mdi mdi-shield-outline"
              on-label=""
              off-label=""
              :disabled="disabled || signal.signal_type === 'bus'"
              :aria-label="t('productDevices.devices.fields.signalSafety')"
              size="small"
              data-testid="signal-safety"
            />
            <Button
              type="button"
              icon="mdi mdi-close"
              size="small"
              text
              severity="secondary"
              :disabled="disabled"
              :aria-label="t('productDevices.devices.removeSignal')"
              @click="row.signals.splice(signalIndex, 1)"
            />
          </div>
          <Button
            type="button"
            icon="mdi mdi-plus"
            :label="t('productDevices.devices.addSignal')"
            size="small"
            text
            class="add-signal"
            :disabled="disabled"
            @click="row.signals.push(newSignal(props.safetyRelevant ?? false))"
          />
        </div>
        <div class="field field-wide">
          <label :for="`pdc-note-${row.key}`">{{ t('productDevices.devices.fields.note') }}</label>
          <InputText
            :id="`pdc-note-${row.key}`"
            v-model="row.note"
            :maxlength="500"
            :disabled="disabled"
            size="small"
            fluid
          />
        </div>
      </div>
    </Panel>
    <Button
      type="button"
      icon="mdi mdi-plus"
      :label="t('productDevices.devices.addComponent')"
      size="small"
      text
      class="add-component"
      :disabled="disabled"
      data-testid="device-add-component"
      @click="addComponent"
    />
  </fieldset>
</template>

<style scoped lang="scss">
.add-component {
  align-self: flex-start;
}

.component-grid {
  display: grid;
  grid-template-columns: 2fr 2fr 1fr 1fr;
  gap: var(--space-2) var(--space-4);
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

.bought-item-select {
  width: 100%;
}

// Every field but the meaning keeps its width, so the meaning gives way and
// the safety and remove buttons always fit.
.signal-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);

  > * {
    flex-shrink: 0;
  }
}

.signal-meaning {
  flex: 1 1 6rem;
  min-width: 0;
}

.signal-position {
  width: 12rem;
  flex-shrink: 0;
}

.signal-type {
  width: 8rem;
  flex-shrink: 0;
}

.signal-address {
  width: 6.5rem;
  flex-shrink: 0;
}

.signal-suffix {
  width: 8rem;
  flex-shrink: 0;
}

.add-signal {
  align-self: flex-start;
}

.hint {
  margin: 0;
}
</style>
