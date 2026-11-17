<script setup lang="ts">
/**
 * Inputs of an interlocking guard: optional guard locking, the opening
 * before the interlock trips, either known with its shape or worked out for
 * a hinged guard with a cam operated switch, and optionally an own reach
 * through the opening from the risk assessment instead of ISO 13857.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { LIMITS } from '../utils/safetyDistance/inputs'
import { OPENING_METHODS, OPENING_SHAPES } from '../utils/safetyDistance/types'
import type { GuardInputs } from '../utils/safetyDistance/types'
import SafetyDistanceField from './SafetyDistanceField.vue'
import SafetyDistanceText from './SafetyDistanceText.vue'

const model = defineModel<GuardInputs>({ required: true })

const { t } = useI18n()

const F = 'tools.safetyDistance.fields'

function set<K extends keyof GuardInputs>(key: K, value: GuardInputs[K]) {
  model.value = { ...model.value, [key]: value }
}

const openingOptions = computed(() =>
  OPENING_METHODS.map((value) => ({ value, label: t(`${F}.openingMethod.${value}`) })),
)
const shapeOptions = computed(() => OPENING_SHAPES.map((value) => ({ value, label: t(`${F}.shape.${value}`) })))
</script>

<template>
  <div class="sd-guard">
    <div class="sd-guard-toggle">
      <ToggleSwitch
        :model-value="model.locking"
        input-id="sd-lock"
        data-testid="sd-lock"
        @update:model-value="set('locking', $event)"
      />
      <label for="sd-lock">{{ t(`${F}.locking.label`) }}</label>
    </div>

    <div v-if="model.locking" class="sd-guard-grid">
      <SafetyDistanceField
        id="sd-tdy"
        :model-value="model.unlockDelay"
        :label="t(`${F}.unlockDelay.label`)"
        symbol="t_DY"
        unit="s"
        :hint="t(`${F}.unlockDelay.hint`)"
        :min="LIMITS.time.min"
        :max="LIMITS.time.max"
        :digits="4"
        @update:model-value="set('unlockDelay', $event)"
      />
    </div>

    <div class="sd-guard-choice">
      <span id="sd-opening-label" class="sd-guard-label">{{ t(`${F}.openingMethod.label`) }}</span>
      <SelectButton
        :model-value="model.openingMethod"
        :options="openingOptions"
        option-label="label"
        option-value="value"
        :allow-empty="false"
        aria-labelledby="sd-opening-label"
        data-testid="sd-opening-method"
        @update:model-value="set('openingMethod', $event)"
      />
    </div>

    <template v-if="model.openingMethod === 'direct'">
      <div class="sd-guard-choice">
        <span id="sd-shape-label" class="sd-guard-label">{{ t(`${F}.shape.label`) }}</span>
        <SelectButton
          :model-value="model.openingShape"
          :options="shapeOptions"
          option-label="label"
          option-value="value"
          :allow-empty="false"
          aria-labelledby="sd-shape-label"
          data-testid="sd-guard-shape"
          @update:model-value="set('openingShape', $event)"
        />
      </div>
      <div class="sd-guard-grid">
        <SafetyDistanceField
          id="sd-e"
          :model-value="model.opening"
          :label="t(`${F}.opening.label`)"
          symbol="e"
          unit="mm"
          :hint="t(`${F}.opening.hint`)"
          :max="LIMITS.length.max"
          @update:model-value="set('opening', $event)"
        />
        <SafetyDistanceField
          v-if="model.openingShape === 'slot'"
          id="sd-guard-sl"
          :model-value="model.slotLength"
          :label="t(`${F}.slotLength.label`)"
          unit="mm"
          :hint="t(`${F}.slotLength.guardHint`)"
          :max="LIMITS.length.max"
          @update:model-value="set('slotLength', $event)"
        />
      </div>
    </template>
    <div v-else class="sd-guard-grid">
      <SafetyDistanceField
        id="sd-gw"
        :model-value="model.guardWidth"
        :label="t(`${F}.guardWidth.label`)"
        symbol="G_W"
        unit="mm"
        :hint="t(`${F}.guardWidth.hint`)"
        :max="LIMITS.length.max"
        @update:model-value="set('guardWidth', $event)"
      />
      <SafetyDistanceField
        id="sd-angle"
        :model-value="model.angle"
        :label="t(`${F}.angle.label`)"
        symbol="ω"
        unit="°"
        :hint="t(`${F}.angle.hint`)"
        :min="LIMITS.angle.min"
        :max="LIMITS.angle.max"
        :digits="2"
        @update:model-value="set('angle', $event)"
      />
      <SafetyDistanceField
        id="sd-gt"
        :model-value="model.guardThickness"
        :label="t(`${F}.guardThickness.label`)"
        symbol="G_T"
        unit="mm"
        :max="LIMITS.length.max"
        @update:model-value="set('guardThickness', $event)"
      />
    </div>

    <div class="sd-guard-toggle">
      <ToggleSwitch
        :model-value="model.reachThroughOwn"
        input-id="sd-own"
        data-testid="sd-own"
        @update:model-value="set('reachThroughOwn', $event)"
      />
      <label for="sd-own">{{ t(`${F}.reachThroughOwn.label`) }}</label>
    </div>
    <small class="sd-guard-hint"><SafetyDistanceText :text="t(`${F}.reachThroughOwn.hint`)" /></small>
    <div v-if="model.reachThroughOwn" class="sd-guard-grid">
      <SafetyDistanceField
        id="sd-dgt"
        :model-value="model.reachThrough"
        :label="t(`${F}.reachThrough.label`)"
        symbol="D_GT"
        unit="mm"
        :hint="t(`${F}.reachThrough.hint`)"
        :max="LIMITS.length.max"
        @update:model-value="set('reachThrough', $event)"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
.sd-guard {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.sd-guard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(13rem, 1fr));
  gap: var(--space-3) var(--space-4);
  align-items: start;
}

.sd-guard-choice {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-1);
}

.sd-guard-label {
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--p-text-muted-color);
}

.sd-guard-hint {
  margin-top: -0.5rem;
  color: var(--p-text-muted-color);
  line-height: 1.35;
}

.sd-guard-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: 600;
}
</style>
