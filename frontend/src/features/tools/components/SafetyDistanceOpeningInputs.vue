<script setup lang="ts">
/**
 * Inputs for reaching through a regular opening: its shape and size, the
 * length of a slot, which limbs can reach it and whether children can,
 * and optionally the distance to the hazard as built.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { LIMITS } from '../utils/safetyDistance/inputs'
import { LIMBS, OPENING_SHAPES } from '../utils/safetyDistance/types'
import type { OpeningInputs } from '../utils/safetyDistance/types'
import SafetyDistanceField from './SafetyDistanceField.vue'

const model = defineModel<OpeningInputs>({ required: true })

const { t } = useI18n()

const F = 'tools.safetyDistance.fields'

function set<K extends keyof OpeningInputs>(key: K, value: OpeningInputs[K]) {
  model.value = { ...model.value, [key]: value }
}

const shapeOptions = computed(() => OPENING_SHAPES.map((value) => ({ value, label: t(`${F}.shape.${value}`) })))
const limbOptions = computed(() => LIMBS.map((value) => ({ value, label: t(`${F}.limb.${value}`) })))
</script>

<template>
  <div class="sd-opening">
    <div class="sd-opening-choices">
      <div class="sd-opening-choice">
        <span id="sd-op-shape-label" class="sd-opening-label">{{ t(`${F}.shape.label`) }}</span>
        <SelectButton
          :model-value="model.shape"
          :options="shapeOptions"
          option-label="label"
          option-value="value"
          :allow-empty="false"
          aria-labelledby="sd-op-shape-label"
          data-testid="sd-op-shape"
          @update:model-value="set('shape', $event)"
        />
      </div>
      <div class="sd-opening-choice">
        <span id="sd-op-limb-label" class="sd-opening-label">{{ t(`${F}.limb.label`) }}</span>
        <SelectButton
          :model-value="model.limb"
          :options="limbOptions"
          option-label="label"
          option-value="value"
          :allow-empty="false"
          aria-labelledby="sd-op-limb-label"
          data-testid="sd-op-limb"
          @update:model-value="set('limb', $event)"
        />
      </div>
    </div>
    <small class="sd-opening-hint">{{ t(`${F}.shape.hint`) }}</small>

    <div class="sd-opening-grid">
      <SafetyDistanceField
        id="sd-op-e"
        :model-value="model.size"
        :label="t(`${F}.openingSize.label`)"
        symbol="e"
        unit="mm"
        :hint="t(`${F}.openingSize.hint`)"
        :max="LIMITS.length.max"
        @update:model-value="set('size', $event)"
      />
      <SafetyDistanceField
        v-if="model.shape === 'slot'"
        id="sd-op-sl"
        :model-value="model.slotLength"
        :label="t(`${F}.slotLength.label`)"
        unit="mm"
        :hint="t(`${F}.slotLength.hint`)"
        :max="LIMITS.length.max"
        @update:model-value="set('slotLength', $event)"
      />
      <SafetyDistanceField
        id="sd-op-sr"
        :model-value="model.distance"
        :label="t(`${F}.openingDistance.label`)"
        symbol="s_r"
        unit="mm"
        :hint="t(`${F}.openingDistance.hint`)"
        :max="LIMITS.length.max"
        @update:model-value="set('distance', $event)"
      />
    </div>

    <div v-if="model.limb === 'upper'">
      <div class="sd-opening-toggle">
        <ToggleSwitch
          :model-value="model.children"
          input-id="sd-op-kids"
          data-testid="sd-op-kids"
          @update:model-value="set('children', $event)"
        />
        <label for="sd-op-kids">{{ t(`${F}.children.label`) }}</label>
      </div>
      <small class="sd-opening-hint">{{ t(`${F}.children.hint`) }}</small>
    </div>
    <small v-else class="sd-opening-hint">{{ t(`${F}.limb.lowerHint`) }}</small>
  </div>
</template>

<style scoped lang="scss">
.sd-opening {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.sd-opening-choices {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3) var(--space-5);
}

.sd-opening-choice {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-1);
}

.sd-opening-label {
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--p-text-muted-color);
}

.sd-opening-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(13rem, 1fr));
  gap: var(--space-3) var(--space-4);
  align-items: start;
}

.sd-opening-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.sd-opening-hint {
  display: block;
  color: var(--p-text-muted-color);
  line-height: 1.35;
}

.sd-opening-toggle + .sd-opening-hint {
  margin-top: var(--space-1);
}

.sd-opening-choices + .sd-opening-hint {
  margin-top: -0.4rem;
}
</style>
