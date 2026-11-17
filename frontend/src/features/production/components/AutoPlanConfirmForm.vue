<script setup lang="ts">
// Confirm step of the Auto-Plan dialog: the run options and the machines
// the planner may touch. Every option is a v-model owned by the dialog.
import { computed, ref, toRef } from 'vue'
import { useI18n } from 'vue-i18n'

import type { DataTableRowContextMenuEvent } from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'

import { useClipboard } from '@/core/composables/useClipboard'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import { AUTO_PLAN_ALGORITHMS, algorithmKey } from '../utils/autoPlanAlgorithms'

import type { ProductionMachineResponse } from '@/features/production-machines'
import type { AutoPlanAlgorithm, AutoPlanPlanningLevel } from '../types/scheduleBoardResponse'
import LabelTag from '@/shared/components/labels/LabelTag.vue'

const props = defineProps<{
  machines: ProductionMachineResponse[]
  errorMessage: string | null
  warnMessage: string | null
  infoMessage: string | null
}>()

const planningLevel = defineModel<AutoPlanPlanningLevel>('planningLevel', { required: true })
const algorithm = defineModel<AutoPlanAlgorithm>('algorithm', { required: true })
const responseTimeDays = defineModel<number>('responseTimeDays', { required: true })
const selectedMachines = defineModel<ProductionMachineResponse[]>('selectedMachines', {
  required: true,
})
const assignMachines = defineModel<boolean>('assignMachines', { required: true })
const overwritePinned = defineModel<boolean>('overwritePinned', { required: true })
const excludeTodaysPlanned = defineModel<boolean>('excludeTodaysPlanned', { required: true })

const { t } = useI18n()
const { copyToClipboard } = useClipboard()

// Archived machines stay listed, sorted last and tagged per row.
const { sortedOptions: sortedMachines } = useArchivableOptions(toRef(props, 'machines'))

const algorithmOptions = computed(() =>
  AUTO_PLAN_ALGORITHMS.map((value) => ({ value, label: t(algorithmKey(value, 'label')) })),
)

const PLANNING_LEVELS: AutoPlanPlanningLevel[] = ['machines', 'pools']
const planningLevelOptions = computed(() =>
  PLANNING_LEVELS.map((value) => ({
    value,
    label: t(`productionSchedule.autoPlan.planningLevelOptions.${value}`),
  })),
)

const cm = ref()
const contextMenuItem = ref<ProductionMachineResponse | null>(null)

function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
  cm.value?.show(event.originalEvent)
}

const contextMenuItems = computed<MenuItem[]>(() => {
  const machine = contextMenuItem.value
  if (!machine) return []
  return [
    {
      label: t('common.copyUuid'),
      icon: 'mdi mdi-content-copy',
      command: () => void copyToClipboard(machine.public_id),
    },
  ]
})
</script>

<template>
  <div class="autoplan-confirm">
    <p>{{ t('productionSchedule.autoPlan.description') }}</p>

    <div class="algorithm-select">
      <div class="algorithm-select-row">
        <div class="planning-level-field">
          <label for="autoplan-planning-level">{{
            t('productionSchedule.autoPlan.planningLevel')
          }}</label>
          <SelectButton
            id="autoplan-planning-level"
            v-model="planningLevel"
            :options="planningLevelOptions"
            option-label="label"
            option-value="value"
            :allow-empty="false"
          />
        </div>
        <div class="algorithm-field">
          <label id="autoplan-algorithm-label" for="autoplan-algorithm">{{ t('productionSchedule.autoPlan.algorithm') }}</label>
          <Select
            id="autoplan-algorithm"
            aria-labelledby="autoplan-algorithm-label"
            v-model="algorithm"
            :options="algorithmOptions"
            option-label="label"
            option-value="value"
            fluid
          />
        </div>
        <div class="response-time-field">
          <label for="autoplan-response-time-days">{{
            t('productionSchedule.autoPlan.responseTimeDays')
          }}</label>
          <InputNumber
            id="autoplan-response-time-days"
            v-model="responseTimeDays"
            :min="0"
            fluid
            v-tooltip.top="t('productionSchedule.autoPlan.responseTimeDaysHint')"
          />
        </div>
      </div>
    </div>

    <div class="machine-select">
      <span class="machine-select-label">{{ t('productionSchedule.autoPlan.machines') }}</span>
      <DataTable
        v-model:selection="selectedMachines"
        v-model:context-menu-selection="contextMenuItem"
        :value="sortedMachines"
        data-key="id"
        size="small"
        scrollable
        scroll-height="12rem"
        @row-contextmenu="onRowContextMenu"
      >
        <Column selection-mode="multiple" header-style="width: 3rem" />
        <Column
          field="internal_name"
          :header="t('productionMachines.columns.internalName')"
          style="min-width: 10rem"
        />
        <Column
          field="vendor"
          :header="t('productionMachines.columns.vendor')"
          style="min-width: 7rem"
        />
        <Column
          field="model"
          :header="t('productionMachines.columns.model')"
          style="min-width: 7rem"
        />
        <Column :header="t('productionMachines.columns.capabilities')" style="min-width: 12rem">
          <template #body="{ data }">
            <div class="capability-tags">
              <LabelTag
                v-for="method in (data as ProductionMachineResponse).fabrication_methods"
                :key="method.id"
                :label="method"
              />
              <ArchivedOptionTag v-if="(data as ProductionMachineResponse).archived" />
              <span
                v-if="
                  (data as ProductionMachineResponse).fabrication_methods.length === 0 &&
                  !(data as ProductionMachineResponse).archived
                "
                class="text-muted"
                >{{ getEmptyPlaceholder() }}</span
              >
            </div>
          </template>
        </Column>
        <template #empty>
          <EmptyState :message="t('productionMachines.table.empty')" />
        </template>
      </DataTable>

      <ContextMenu ref="cm" :model="contextMenuItems" @hide="contextMenuItem = null" />
    </div>

    <label class="assign-machines-toggle">
      <Checkbox v-model="assignMachines" binary />
      <span>
        {{ t('productionSchedule.autoPlan.assignMachines') }}
        <small class="field-hint">{{ t('productionSchedule.autoPlan.assignMachinesHint') }}</small>
      </span>
    </label>

    <label class="assign-machines-toggle">
      <Checkbox v-model="overwritePinned" binary />
      <span>
        {{ t('productionSchedule.autoPlan.overwritePinned') }}
        <small class="field-hint">{{ t('productionSchedule.autoPlan.overwritePinnedHint') }}</small>
      </span>
    </label>

    <label class="assign-machines-toggle">
      <Checkbox v-model="excludeTodaysPlanned" binary />
      <span>
        {{ t('productionSchedule.autoPlan.excludeTodaysPlanned') }}
        <small class="field-hint">{{
          t('productionSchedule.autoPlan.excludeTodaysPlannedHint')
        }}</small>
      </span>
    </label>

    <Message v-if="errorMessage" severity="error" data-testid="autoplan-error-message">
      {{ errorMessage }}
    </Message>
    <Message v-if="warnMessage" severity="warn" data-testid="autoplan-warn-message">
      {{ warnMessage }}
    </Message>
    <Message v-if="infoMessage" severity="info" data-testid="autoplan-info-message">
      {{ infoMessage }}
    </Message>
  </div>
</template>

<style scoped lang="scss">
.autoplan-confirm {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.algorithm-select label {
  font-size: var(--font-size-sm);
  font-weight: 500;
}

// Bottom-aligned so the inputs stay on one line when a label wraps.
.algorithm-select-row {
  display: flex;
  align-items: flex-end;
  gap: var(--space-3);
}

.planning-level-field,
.algorithm-field,
.response-time-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.planning-level-field {
  flex: 0 0 auto;
}

.algorithm-field {
  flex: 1 1 auto;
  min-width: 0;
}

.response-time-field {
  flex: 0 0 11rem;
}

.machine-select {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.machine-select-label {
  font-size: var(--font-size-sm);
  font-weight: 500;
}

.capability-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.assign-machines-toggle {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  padding-left: var(--space-2);
}

.field-hint {
  display: block;
  font-weight: 400;
}
</style>
