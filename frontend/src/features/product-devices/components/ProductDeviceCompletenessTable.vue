<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { useAppToast } from '@/core/composables/useAppToast'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { formatISODateTime } from '@/core/utils/dates'
import { extractApiError } from '@/core/utils/errors'
import EmptyState from '@/shared/components/EmptyState.vue'
import { setDeviceCheck } from '../api/deviceCompletenessApi'
import { useProductDevicesViewStore } from '../stores/productDevicesViewStore'
import type {
  DevicePlan,
  ProductDevice,
  ProductDeviceCompleteness,
  ProductDisciplines,
  SequenceCoverage,
} from '../types/productDevice'

/**
 * Whether each device of a product is in every plan outside Glados it has
 * to be in, so nothing is forgotten between disciplines: one row per
 * device, one tick per plan the machine's disciplines call for (the CAD
 * assembly always), each with who ticked it and when, and whether a flow
 * sequence moves or checks the device. Only Incomplete in the controls bar
 * hides the devices with nothing left to do.
 */
const props = defineProps<{
  devices: ProductDevice[]
  completeness: ProductDeviceCompleteness[]
  disciplines?: ProductDisciplines
  canEdit: boolean
}>()

const emit = defineEmits<{ changed: [] }>()

const { t } = useI18n()
const toast = useAppToast()
const { onlyIncomplete } = storeToRefs(useProductDevicesViewStore())
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const plans = computed<DevicePlan[]>(() => {
  const d = props.disciplines
  return [
    'cad_assembly',
    ...(d?.electrics ? (['eplan'] as const) : []),
    ...(d?.pneumatics ? (['pneumatics'] as const) : []),
    ...(d?.hydraulics ? (['hydraulics'] as const) : []),
    ...(d?.robotics ? (['robot_program'] as const) : []),
  ]
})

const hostStore = useHostStore()

const byDevice = computed(() => new Map(props.completeness.map((c) => [c.device_id, c])))

function check(device: ProductDevice, plan: DevicePlan) {
  return byDevice.value.get(device.id)?.checks.find((c) => c.plan === plan) ?? null
}

function coverage(device: ProductDevice): SequenceCoverage {
  return byDevice.value.get(device.id)?.sequence_coverage ?? 'none'
}

function complete(device: ProductDevice): boolean {
  // With sequences switched off, coverage cannot be reached, so it no
  // longer counts towards a complete device.
  return (
    plans.value.every((plan) => check(device, plan) !== null) &&
    (!hostStore.sequencesEnabled || coverage(device) === 'released')
  )
}

const rows = computed(() =>
  props.devices.filter((d) => !d.archived).filter((d) => !onlyIncomplete.value || !complete(d)),
)

const COVERAGE_SEVERITY: Record<SequenceCoverage, 'success' | 'warn' | 'danger'> = {
  released: 'success',
  draft: 'warn',
  none: 'danger',
}

function tooltip(device: ProductDevice, plan: DevicePlan): string {
  if (!props.canEdit) return t('productDevices.tags.noRights')
  const done = check(device, plan)
  return done ? t('productDevices.completeness.checkedBy', { name: done.checked_by_name, date: formatISODateTime(done.checked_at) }) : ''
}

async function toggle(device: ProductDevice, plan: DevicePlan, checked: boolean): Promise<void> {
  try {
    await setDeviceCheck(device.id, plan, checked)
    emit('changed')
  } catch (e) {
    toast.error(device.name_utf8, extractApiError(e) ?? t('productDevices.completeness.saveFailed'))
  }
}
</script>

<template>
  <DataTable
    :value="rows"
    data-key="id"
    size="small"
    scrollable
    scroll-height="flex"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    class="completeness-table"
    data-testid="device-completeness-table"
  >
    <template #empty><EmptyState /></template>
    <Column :header="t('productDevices.devices.columns.nameUtf8')">
      <template #body="{ data }: { data: ProductDevice }">
        {{ data.name_utf8 }}
        <i v-if="complete(data)" class="mdi mdi-check-circle done" :aria-label="t('productDevices.completeness.complete')" />
      </template>
    </Column>
    <Column v-for="plan in plans" :key="plan" :header="t(`productDevices.completeness.plans.${plan}`)" style="width: 9rem">
      <template #body="{ data }: { data: ProductDevice }">
        <span v-tooltip.bottom="tooltip(data, plan)">
          <Checkbox
            :model-value="check(data, plan) !== null"
            binary
            :disabled="!canEdit"
            :aria-label="t(`productDevices.completeness.plans.${plan}`)"
            :data-testid="`check-${plan}-${data.id}`"
            @update:model-value="(value: boolean) => toggle(data, plan, value)"
          />
        </span>
      </template>
    </Column>
    <Column
      v-if="hostStore.sequencesEnabled"
      :header="t('productDevices.completeness.sequence')"
      style="width: 12rem"
    >
      <template #body="{ data }: { data: ProductDevice }">
        <Tag
          :value="t(`productDevices.completeness.coverage.${coverage(data)}`)"
          :severity="COVERAGE_SEVERITY[coverage(data)]"
          :data-testid="`coverage-${data.id}`"
        />
      </template>
    </Column>
  </DataTable>
</template>

<style scoped lang="scss">
.completeness-table {
  flex: 1;
  min-height: 0;
}

.done {
  margin-left: var(--space-1);
  color: var(--p-green-500);
}
</style>
