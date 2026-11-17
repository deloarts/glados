<script setup lang="ts">
import { computed, useId } from 'vue'
import { useI18n } from 'vue-i18n'

import { useLocalizedText } from '@/shared/composables/useLocalizedText'
import { useProductDeviceResourcesStore } from '../stores/productDeviceResourcesStore'
import type { ProductDevice, ProductDeviceKindPosition } from '../types/productDevice'

/**
 * The device a device is driven by, such as the first clamp cylinder whose
 * valve also moves the second one, and for a driver of another kind which
 * of this device's positions goes with each of the driver's. A device that
 * drives others cannot be driven itself, and a driven device drives
 * nothing, so neither is offered.
 */
const props = defineProps<{
  device?: ProductDevice
  devices: ProductDevice[]
  kindId: number | null
  /** This device's live positions. */
  positions: ProductDeviceKindPosition[]
  readonly?: boolean
}>()

const drivenById = defineModel<number | null>('drivenById', { required: true })
const positionMap = defineModel<Record<string, number | null>>('positionMap', { required: true })

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const { localize } = useLocalizedText()
const resources = useProductDeviceResourcesStore()

const followers = computed(() =>
  props.device ? props.devices.filter((d) => d.driven_by_id === props.device?.id) : [],
)
const choices = computed(() =>
  props.devices
    .filter((d) => d.id !== props.device?.id && d.driven_by_id === null)
    .filter((d) => !d.archived || d.id === props.device?.driven_by_id)
    .map((d) => ({ value: d.id, label: d.name_utf8 })),
)
const driver = computed(() => props.devices.find((d) => d.id === drivenById.value))
const driverPositions = computed(() => {
  const driverKind = driver.value ? resources.kindById.get(driver.value.kind_id) : undefined
  if (!driverKind || driverKind.id === props.kindId) return []
  return driverKind.positions.filter((p) => !p.archived)
})
const ownChoices = computed(() => props.positions.map((p) => ({ value: p.id, label: localize(p.label) })))

function setMapped(driverPositionId: number, own: number | null): void {
  positionMap.value = { ...positionMap.value, [String(driverPositionId)]: own }
}
</script>

<template>
  <div class="field field-wide">
    <label id="pd-driven-by-label" for="pd-driven-by">{{ t('productDevices.devices.fields.drivenBy') }}</label>
    <Select
      v-model="drivenById"
      input-id="pd-driven-by"
      aria-labelledby="pd-driven-by-label"
      :options="choices"
      option-label="label"
      option-value="value"
      show-clear
      filter
      :disabled="readonly || followers.length > 0"
      :placeholder="t('productDevices.devices.notDriven')"
      fluid
      data-testid="pd-driven-by"
    />
    <small class="hint">
      {{
        followers.length > 0
          ? t('productDevices.devices.drivesOthers', { names: followers.map((d) => d.name_utf8).join(', ') })
          : t('productDevices.devices.drivenByHint')
      }}
    </small>
  </div>
  <div v-if="driverPositions.length" class="field field-wide">
    <!-- eslint-disable-next-line vuejs-accessibility/label-has-for -- captions every row below, each control names it through aria-labelledby -->
    <label :id="`${uid}-position-map-label`">{{ t('productDevices.devices.positionMap') }}</label>
    <small class="hint">{{ t('productDevices.devices.positionMapHint') }}</small>
    <div v-for="position in driverPositions" :key="position.id" class="map-row">
      <span :id="`${uid}-position-${position.id}`" class="map-driver">{{ localize(position.label) }}</span>
      <i class="mdi mdi-arrow-right" aria-hidden="true" />
      <Select
        :aria-labelledby="`${uid}-position-map-label ${uid}-position-${position.id}`"
        :model-value="positionMap[String(position.id)] ?? null"
        :options="ownChoices"
        option-label="label"
        option-value="value"
        show-clear
        :disabled="readonly"
        :placeholder="t('productDevices.devices.notMapped')"
        size="small"
        class="map-own"
        @update:model-value="(own: number | null) => setMapped(position.id, own)"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
.map-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.map-driver {
  width: 10rem;
  font-size: var(--font-size-sm);
}

.map-own {
  width: 14rem;
}
</style>
