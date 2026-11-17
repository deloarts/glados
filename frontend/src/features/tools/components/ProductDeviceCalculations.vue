<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import type { Schemas } from '@/core/api/generated'
import { Permission } from '@/core/auth/permissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { usePermissions } from '@/core/composables/usePermissions'
import { extractApiError } from '@/core/utils/errors'
import { getCalculations } from '../api/getCalculations'
import { setCalculationDevice } from '../api/setCalculationDevice'
import { toolByKey } from '../registry'
import NewCalculationButton from './NewCalculationButton.vue'
import { permissionLabel } from '@/shared/utils/permissionLabels'
import type { ProductDevice } from '@/features/product-devices'

type Calculation = Schemas['CalculationSummaryResponse']

/**
 * The calculations that refer to a device, such as the drive sizing of an
 * axis or the safety distance of a light curtain. A draft of the product,
 * or of one of its projects, can be linked here and unlinked again; a
 * released calculation keeps the device it was released with, so changing
 * that needs a new revision of it. New Calculation opens a tool with this
 * device already picked for saving.
 */
const props = defineProps<{ device: ProductDevice }>()

const emit = defineEmits<{ loaded: [calculations: Calculation[]] }>()

const { t } = useI18n()
const toast = useAppToast()
const { hasPermission } = usePermissions()

const linked = ref<Calculation[]>([])
const candidates = ref<Calculation[]>([])
const busy = ref(false)

const canWrite = computed(() => hasPermission(Permission.WRITE_CALCULATIONS))
const noRights = computed(() =>
  canWrite.value ? '' : t('productDevices.calculations.noRights', { permission: permissionLabel(t, Permission.WRITE_CALCULATIONS) }),
)
const owner = computed(() => `product:${props.device.product_id}:${props.device.product_number ?? ''}`)

const candidateOptions = computed(() =>
  candidates.value.map((c) => ({ value: c.id, label: `${c.document_number} ${c.title} (${toolLabel(c.tool)})` })),
)

function toolLabel(key: string): string {
  const tool = toolByKey(key)
  return tool ? t(tool.labelKey) : key
}

async function load(): Promise<void> {
  const page = await getCalculations({ product_device_id: props.device.id, limit: 200 })
  linked.value = page.items
  emit('loaded', page.items)
}

async function loadCandidates(): Promise<void> {
  if (!canWrite.value) return
  const page = await getCalculations({ related_product_id: props.device.product_id, released: false, limit: 200 })
  candidates.value = page.items.filter((c) => c.product_device_id === null)
}

watch(
  () => props.device.id,
  () => {
    void load().catch(() => {})
    void loadCandidates().catch(() => {})
  },
  { immediate: true },
)

async function relink(calculation: Calculation, deviceId: number | null, done: string): Promise<void> {
  busy.value = true
  try {
    await setCalculationDevice(calculation.id, deviceId)
    toast.success(calculation.title, done)
    await Promise.all([load(), loadCandidates()])
  } catch (e) {
    toast.error(calculation.title, extractApiError(e) ?? t('productDevices.calculations.failed'))
  } finally {
    busy.value = false
  }
}

function link(id: number | null): void {
  const calculation = candidates.value.find((c) => c.id === id)
  if (calculation) void relink(calculation, props.device.id, t('productDevices.calculations.linked'))
}
</script>

<template>
  <fieldset class="dialog-section" data-testid="device-calculations">
    <legend>{{ t('productDevices.calculations.title') }}</legend>
    <p class="hint">{{ t('productDevices.calculations.hint') }}</p>

    <ul v-if="linked.length" class="list">
      <li v-for="calculation in linked" :key="calculation.id" class="row" data-testid="device-calculation">
        <RouterLink :to="{ name: 'CalculationOpen', params: { id: calculation.id } }" class="title">
          <span class="number">{{ calculation.document_number }}</span>
          {{ calculation.title }}
        </RouterLink>
        <span class="muted">{{ toolLabel(calculation.tool) }}</span>
        <Tag :value="t('documents.revision.tag', { revision: calculation.revision })" severity="secondary" />
        <Tag
          v-if="calculation.released_at"
          :value="t('tools.calculations.status.released')"
          severity="success"
        />
        <Tag v-else :value="t('tools.calculations.status.draft')" severity="secondary" />
        <span
          v-tooltip.bottom="
            calculation.released_at ? t('productDevices.calculations.releasedKeepsLink') : noRights
          "
          class="unlink"
        >
          <Button
            icon="mdi mdi-link-variant-off"
            :aria-label="t('productDevices.calculations.unlink')"
            severity="secondary"
            text
            size="small"
            :disabled="!canWrite || !!calculation.released_at || busy"
            data-testid="device-calculation-unlink"
            @click="relink(calculation, null, t('productDevices.calculations.unlinked'))"
          />
        </span>
      </li>
    </ul>
    <p v-else class="muted">{{ t('productDevices.calculations.empty') }}</p>

    <div class="actions">
      <span v-tooltip.bottom="noRights" class="picker">
        <Select
          :aria-label="t('productDevices.calculations.link')"
          :model-value="null"
          :options="candidateOptions"
          option-label="label"
          option-value="value"
          :placeholder="t('productDevices.calculations.link')"
          :empty-message="t('productDevices.calculations.noCandidates')"
          :disabled="!canWrite || busy"
          filter
          size="small"
          fluid
          data-testid="device-calculation-link"
          @update:model-value="link"
        />
      </span>
      <NewCalculationButton :owner="owner" :device-id="device.id" :disabled="!canWrite" />
    </div>
  </fieldset>
</template>

<style scoped lang="scss">
.hint,
.muted {
  margin: 0;
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.title {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.number {
  font-weight: 600;
  margin-right: var(--space-1);
}

.actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.picker {
  flex: 1 1 auto;
}
</style>
