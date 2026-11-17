<script lang="ts">
// Module-level so split row ids stay stable across mounts and keep each
// row's inputs tied to it when a sibling is removed.
let nextSplitRowId = 0

function createSplitRowId(): number {
  return ++nextSplitRowId
}
</script>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { extractApiError } from '@/core/utils/errors'
import { API_MAX_PAGE_SIZE } from '@/core/constants/table'
import { getProductionMachines } from '@/features/production-machines'
import { useProductionLotDetailStore } from '../stores/productionLotDetailStore'
import { useMachineCapability } from '../../composables/useMachineCapability'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'

import type { ProductionMachineResponse } from '@/features/production-machines'
import type { LotPositionResponse } from '../../types/productionLotsResponse'
import { localizeLabel } from '@/shared/utils/localizeLabel'

const props = defineProps<{
  lotId: number
  position: LotPositionResponse | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  assigned: []
}>()

const { t } = useI18n()
const detailStore = useProductionLotDetailStore()
const { getCapableMachines, positionIsManual, getExternalRequiredSteps } = useMachineCapability()

interface SplitRow {
  id: number
  machine_id: number | null
  quantity: number | null
}

const rows = ref<SplitRow[]>([{ id: createSplitRowId(), machine_id: null, quantity: null }])
const submitting = ref(false)
const loadingMachines = ref(false)
const errorMessage = ref<string | null>(null)
const machines = ref<ProductionMachineResponse[]>([])

const capableMachines = computed(() => getCapableMachines(props.position, machines.value))

// Archived machines stay selectable, sorted last; each split row looks up
// its own machine_id.
const { sortedOptions: machineOptions, isArchived } = useArchivableOptions(capableMachines)

function selectedMachineFor(machineId: number | null): ProductionMachineResponse | null {
  return machineOptions.value.find((m) => m.id === machineId) ?? null
}

// A manual position never has a capable machine, so it gets an info message
// instead of a warning.
const isManualPosition = computed(() => positionIsManual(props.position))

// Methods flagged required_external; internal assignment is allowed but
// flagged.
const externalMethodNames = computed(() => {
  const names = getExternalRequiredSteps(props.position).map((s) => localizeLabel(s.fabrication_method_name))
  return [...new Set(names)]
})

const totalAssigned = computed(() => rows.value.reduce((sum, row) => sum + (row.quantity ?? 0), 0))

// What the position still lacks: its quantity less its live order lines,
// its production orders and what canceled orders made. A line closed short
// leaves only the pieces it never brought.
const open = computed(() => props.position?.quantity_remaining ?? 0)

const remaining = computed(() => open.value - totalAssigned.value)

const isValid = computed(() => {
  if (!props.position) return false
  if (rows.value.length === 0) return false
  if (totalAssigned.value <= 0) return false
  if (totalAssigned.value > open.value + 1e-9) return false
  return rows.value.every((row) => (row.quantity ?? 0) > 0)
})

watch(visible, async (isVisible) => {
  if (!isVisible) return
  rows.value = [
    { id: createSplitRowId(), machine_id: null, quantity: open.value > 0 ? open.value : null },
  ]
  errorMessage.value = null
  loadingMachines.value = true
  try {
    const response = await getProductionMachines({ limit: API_MAX_PAGE_SIZE, include_archived: true })
    machines.value = response.items
  } finally {
    loadingMachines.value = false
  }
})

function addRow(): void {
  rows.value.push({
    id: createSplitRowId(),
    machine_id: null,
    quantity: remaining.value > 0 ? remaining.value : null,
  })
}

function removeRow(id: number): void {
  rows.value = rows.value.filter((row) => row.id !== id)
}

async function onSubmit(): Promise<void> {
  if (!props.position || !isValid.value) return

  submitting.value = true
  errorMessage.value = null

  try {
    await detailStore.assignInternal(props.lotId, props.position.id, {
      orders: rows.value.map((row) => ({
        machine_id: row.machine_id,
        quantity: row.quantity!,
      })),
    })
    visible.value = false
    emit('assigned')
  } catch (e) {
    errorMessage.value =
      extractApiError(e) ?? t('production.lots.detail.assignInternal.errors.unknown')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('production.lots.detail.assignInternal.title')"
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <div class="assign-internal">
      <div class="rows">
        <div v-for="row in rows" :key="row.id" class="row">
          <div class="row-machine">
            <Select
              v-model="row.machine_id"
              :aria-label="t('production.lots.detail.assignInternal.selectMachine')"
              :options="machineOptions"
              option-label="internal_name"
              option-value="id"
              :loading="loadingMachines"
              :placeholder="t('production.lots.detail.assignInternal.selectMachine')"
              show-clear
              fluid
            >
              <template #option="{ option }">
                <span>{{ option.internal_name }}</span>
                <ArchivedOptionTag v-if="option.archived" />
              </template>
              <template #value>
                <span v-if="selectedMachineFor(row.machine_id)">{{
                  selectedMachineFor(row.machine_id)!.internal_name
                }}</span>
                <ArchivedOptionTag v-if="selectedMachineFor(row.machine_id)?.archived" />
              </template>
            </Select>
            <ArchivedSelectionWarning v-if="isArchived(selectedMachineFor(row.machine_id))" />
          </div>
          <InputNumber
            v-model="row.quantity"
            :min="1"
            :max-fraction-digits="0"
            :placeholder="t('production.lots.detail.assignInternal.quantity')"
          />
          <Button
            icon="mdi mdi-delete-outline"
            severity="secondary"
            text
            :disabled="rows.length === 1"
            :aria-label="t('production.lots.detail.assignInternal.removeMachine')"
            @click="removeRow(row.id)"
          />
        </div>

        <Button
          :label="t('production.lots.detail.assignInternal.addMachine')"
          icon="mdi mdi-plus"
          severity="secondary"
          outlined
          size="small"
          @click="addRow"
        />

        <div class="summary">
          {{ t('production.lots.detail.assignInternal.assigned') }}: {{ totalAssigned }} /
          {{ open }}
          <span v-if="remaining > 0" class="remaining">
            ({{ t('production.lots.detail.assignInternal.remaining') }}: {{ remaining }})
          </span>
        </div>

        <Message v-if="externalMethodNames.length > 0" severity="warn" :closable="false">
          {{
            t('production.lots.detail.assignInternal.externalMethodWarning', {
              methods: externalMethodNames.join(', '),
            })
          }}
        </Message>
        <Message v-if="isManualPosition" severity="info" :closable="false">
          {{ t('production.lots.detail.assignInternal.manualPosition') }}
        </Message>
        <Message
          v-else-if="capableMachines.length === 0 && !loadingMachines"
          severity="warn"
          :closable="false"
        >
          {{ t('production.lots.detail.assignInternal.noCapableMachines') }}
          {{ t('production.lots.detail.assignInternal.noCapableMachinesHint') }}
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
        :label="t('common.save')"
        :loading="submitting"
        :disabled="!isValid"
        @click="onSubmit"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.assign-internal {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.rows {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.row {
  display: grid;
  grid-template-columns: 1fr 8rem auto;
  gap: var(--space-2);
  align-items: center;
}

.row-machine {
  display: flex;
  flex-direction: column;
}

.summary {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
  font-variant-numeric: tabular-nums;
}

.remaining {
  color: var(--p-orange-500);
}
</style>
