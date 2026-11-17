<script setup lang="ts">
import { computed, onMounted, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { HelpDrawer } from '@/shared/help'
import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { useProductionQueueStore } from '../../stores/productionQueueStore'
import { getMachinePools } from '@/features/production-machines'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'

import type { ProductionOrderResponse } from '../../types/productionOrdersResponse'
import type { StartProductionOrderRequest } from '../../types/productionOrdersRequest'
import type { ProductionMachineResponse } from '@/features/production-machines'

const props = defineProps<{
  order: ProductionOrderResponse | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  started: []
}>()

const { t } = useI18n()
const explainVisible = ref(false)
// Prefixes the ids that tie each label to its control.
const uid = useId()
const { toastOnError } = useErrorToast()
const store = useProductionQueueStore()
const currentUserStore = useCurrentUserStore()

const operatorId = ref<number | null>(null)
const { submitting, errorMessage, run } = useSubmitAction()

const operatorRequired = computed(() => currentUserStore.isSharedAccount)

const operatorOptions = computed(() =>
  store.operators.map((op) => ({ label: op.full_name, value: op.id })),
)

onMounted(() => {
  if (operatorRequired.value && store.operators.length === 0) {
    store.fetchOperators().catch(toastOnError())
  }
})

// ── Pool resolution ─────────────────────────────────────────────────
// A pool-assigned order without a machine must pick one of the pool's
// members to start.

const machineId = ref<number | null>(null)
const poolMachines = ref<ProductionMachineResponse[]>([])
const loadingPoolMachines = ref(false)

// Archived machines stay selectable, sorted last.
const { sortedOptions: machineOptions, isArchived: isMachineArchived } =
  useArchivableOptions(poolMachines)
const selectedMachine = computed<ProductionMachineResponse | null>(
  () => machineOptions.value.find((m) => m.id === machineId.value) ?? null,
)

const needsMachineSelection = computed(
  () => props.order?.machine_pool_id != null && props.order.machine_id === null,
)

async function loadPoolMachines(poolId: number): Promise<void> {
  loadingPoolMachines.value = true
  try {
    const result = await getMachinePools({ id: poolId, limit: 1, include_archived: true })
    poolMachines.value = result.items[0]?.machines ?? []
  } finally {
    loadingPoolMachines.value = false
  }
}

watch(visible, (isVisible) => {
  if (!isVisible) return
  operatorId.value = null
  machineId.value = null
  poolMachines.value = []
  errorMessage.value = null
  if (props.order?.machine_pool_id != null && props.order.machine_id === null) {
    loadPoolMachines(props.order.machine_pool_id).catch(toastOnError())
  }
})

const isValid = computed(
  () =>
    (!operatorRequired.value || operatorId.value !== null) &&
    (!needsMachineSelection.value || machineId.value !== null),
)

async function onSubmit(): Promise<void> {
  const order = props.order
  if (!order) return
  if (!isValid.value) {
    errorMessage.value =
      needsMachineSelection.value && machineId.value === null
        ? t('productionQueue.start.errors.machineRequired')
        : t('productionQueue.operators.required')
    return
  }

  await run(async () => {
    const payload: StartProductionOrderRequest = {}
    if (operatorId.value !== null) payload.operator_id = operatorId.value
    if (needsMachineSelection.value) payload.machine_id = machineId.value

    await store.start(order.id, payload)
    visible.value = false
    emit('started')
  }, t('productionQueue.start.errors.unknown'))
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :style="{ width: 'var(--dialog-width-sm)' }">
    <template #header>
      <div class="dialog-header">
        <span class="p-dialog-title">{{ t('productionQueue.start.title') }}</span>
        <Button
          type="button"
          class="dialog-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('productionQueue.start.explain')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('productionQueue.start.explain')"
          @click="explainVisible = true"
        />
      </div>
    </template>

    <div v-if="order" class="start-form">
      <div v-if="needsMachineSelection" class="field">
        <label :id="`${uid}-select-machine-label`" :for="`${uid}-select-machine`">
          <i class="mdi mdi-view-grid-outline" aria-hidden="true" />
          {{ t('productionQueue.start.selectMachine') }} *
        </label>
        <Select
          v-model="machineId"
          :input-id="`${uid}-select-machine`"
          :aria-labelledby="`${uid}-select-machine-label`"
          :options="machineOptions"
          option-label="internal_name"
          option-value="id"
          :loading="loadingPoolMachines"
          :placeholder="t('productionQueue.start.selectMachinePlaceholder')"
          fluid
        >
          <template #option="{ option }">
            <span>{{ option.internal_name }}</span>
            <ArchivedOptionTag v-if="option.archived" />
          </template>
          <template #value>
            <span v-if="selectedMachine">{{ selectedMachine.internal_name }}</span>
            <ArchivedOptionTag v-if="selectedMachine?.archived" />
          </template>
        </Select>
        <ArchivedSelectionWarning v-if="isMachineArchived(selectedMachine)" />
        <small class="hint">{{
          t('productionQueue.start.poolHint', { pool: order.machine_pool_name })
        }}</small>
      </div>

      <div v-if="operatorRequired" class="field">
        <label :id="`${uid}-label-label`" :for="`${uid}-operators`"> {{ t('productionQueue.operators.label') }} * </label>
        <Select
          v-model="operatorId"
          :input-id="`${uid}-operators`"
          :aria-labelledby="`${uid}-label-label`"
          :options="operatorOptions"
          option-label="label"
          option-value="value"
          :placeholder="t('productionQueue.operators.placeholderRequired')"
          :disabled="operatorOptions.length === 0"
          fluid
        />
        <Message v-if="operatorOptions.length === 0" severity="warn" :closable="false">
          {{ t('productionQueue.operators.noneAssigned') }}
        </Message>
      </div>

      <Message v-if="errorMessage" severity="error" :closable="false">
        {{ errorMessage }}
      </Message>
    </div>

    <template #footer>
      <Button
        :label="t('common.cancel')"
        severity="secondary"
        outlined
        :disabled="submitting"
        @click="visible = false"
      />
      <Button
        :label="t('productionQueue.start.submit')"
        :loading="submitting"
        :disabled="!isValid"
        @click="onSubmit"
      />
    </template>
  </Dialog>

  <HelpDrawer v-model:visible="explainVisible" slug="production/queue" anchor="start" />
</template>

<style scoped lang="scss">
.dialog-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.dialog-explain-button :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.start-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
</style>
