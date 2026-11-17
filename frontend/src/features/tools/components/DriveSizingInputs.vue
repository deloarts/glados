<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { localeTag } from '@/core/utils/dates'
import { isFieldRelevant, NUMERIC_FIELDS, ORIENTATIONS, TRANSMISSIONS } from '../utils/driveSizing/model'
import type {
  DriveSizingSettings,
  FieldGroup,
  NumericField,
  NumericKey,
  Orientation,
  Transmission,
} from '../utils/driveSizing/model'

const settings = defineModel<DriveSizingSettings>({ required: true })

const { t, te } = useI18n()

const GROUPS: readonly FieldGroup[] = ['axis', 'gearbox', 'motor', 'load']

// One card for all four groups; the switch picks which group's fields are
// shown.
const activeGroup = ref<FieldGroup>('axis')
const groupOptions = computed(() =>
  GROUPS.map((value) => ({ value, label: t(`tools.driveSizing.groups.${value}`) })),
)

const orientationOptions = computed(() =>
  ORIENTATIONS.map((value) => ({ value, label: t(`tools.driveSizing.orientation.${value}`) })),
)
const transmissionOptions = computed(() =>
  TRANSMISSIONS.map((value) => ({ value, label: t(`tools.driveSizing.transmission.${value}`) })),
)

const groups = computed(() =>
  GROUPS.map((group) => ({
    group,
    fields: NUMERIC_FIELDS.filter((field) => field.group === group && isFieldRelevant(field.key, settings.value)),
  })),
)

function setNumber(key: NumericKey, value: number | null) {
  settings.value = { ...settings.value, [key]: value }
}

function setOrientation(orientation: Orientation) {
  settings.value = { ...settings.value, orientation }
}

function setTransmission(transmission: Transmission) {
  settings.value = { ...settings.value, transmission }
}

function hint(field: NumericField): string {
  const key = `tools.driveSizing.hints.${field.key}`
  return te(key) ? t(key) : ''
}

function placeholder(field: NumericField): string | undefined {
  const key = `tools.driveSizing.placeholders.${field.key}`
  return te(key) ? t(key) : undefined
}
</script>

<template>
  <section class="ds-inputs">
    <SelectButton
      v-model="activeGroup"
      :options="groupOptions"
      option-label="label"
      option-value="value"
      :allow-empty="false"
      :aria-label="t('tools.driveSizing.groupsLabel')"
      class="ds-group-switch"
      data-testid="ds-group-switch"
    />
    <div
      v-for="{ group, fields } in groups"
      :key="group"
      class="ds-group"
      :class="{ 'ds-group--hidden': group !== activeGroup }"
      :data-testid="`ds-group-${group}`"
    >
      <h3 class="ds-group-title">{{ t(`tools.driveSizing.groups.${group}`) }}</h3>
      <div class="ds-fields">
        <template v-if="group === 'axis'">
          <div class="ds-field ds-field--wide">
            <span id="ds-orientation-label" class="ds-label">{{ t('tools.driveSizing.orientation.label') }}</span>
            <SelectButton
              :model-value="settings.orientation"
              :options="orientationOptions"
              option-label="label"
              option-value="value"
              :allow-empty="false"
              aria-labelledby="ds-orientation-label"
              data-testid="ds-orientation"
              @update:model-value="setOrientation"
            />
          </div>
          <div class="ds-field ds-field--wide">
            <span id="ds-transmission-label" class="ds-label">{{ t('tools.driveSizing.transmission.label') }}</span>
            <Select
              :model-value="settings.transmission"
              :options="transmissionOptions"
              option-label="label"
              option-value="value"
              aria-labelledby="ds-transmission-label"
              data-testid="ds-transmission"
              class="ds-select"
              @update:model-value="setTransmission"
            />
          </div>
        </template>
        <div v-for="field in fields" :key="field.key" class="ds-field">
          <label :for="`ds-${field.key}`" class="ds-label">
            {{ t(`tools.driveSizing.fields.${field.key}`) }}
            <span v-if="field.symbol[0]" class="ds-symbol">{{ field.symbol[0] }}<sub v-if="field.symbol[1]">{{ field.symbol[1] }}</sub></span>
          </label>
          <InputNumber
            :model-value="settings[field.key]"
            :input-id="`ds-${field.key}`"
            :min="field.min"
            :max="field.max"
            :min-fraction-digits="0"
            :max-fraction-digits="field.digits"
            :locale="localeTag()"
            :suffix="field.unit ? ` ${field.unit}` : undefined"
            :placeholder="placeholder(field)"
            :data-testid="`ds-field-${field.key}`"
            class="ds-number"
            @update:model-value="(value: number | null) => setNumber(field.key, value)"
          />
          <small v-if="hint(field)" class="ds-hint">{{ hint(field) }}</small>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped lang="scss">
.ds-inputs {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  min-width: 0;
  padding: var(--space-3) var(--space-4);
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
}

.ds-group-switch {
  flex-wrap: wrap;
}

.ds-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  min-width: 0;

  &--hidden {
    display: none;
  }
}

// On screen the switch names the group; the heading is for paper.
.ds-group-title {
  display: none;
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
}

.ds-fields {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(9rem, 1fr));
  gap: var(--space-3);
}

.ds-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;

  &--wide {
    grid-column: 1 / -1;
  }
}

.ds-label {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--p-text-muted-color);
}

.ds-symbol {
  margin-left: var(--space-1);
  font-style: italic;
  font-weight: 400;

  sub {
    font-style: normal;
  }
}

.ds-number {
  width: 100%;

  :deep(input) {
    width: 100%;
    min-width: 0;
  }
}

.ds-select {
  width: 100%;
}

.ds-hint {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}
</style>
