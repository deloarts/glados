<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import { useFabricationMethodsStore } from '@/features/fabrication-methods'
import { useInspectionMethodsStore } from '@/features/inspection-methods'
import { storeToRefs } from 'pinia'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { normalizeGroupIndexes } from '@/core/utils/grouping'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import EmptyState from '@/shared/components/EmptyState.vue'

import type { MenuItem } from 'openvue/menuitem'
import type { MadeItemProcessCreateRequest } from '../types/madeItemsRequest'
import { labelName, localizeLabel } from '@/shared/utils/localizeLabel'

const processes = defineModel<MadeItemProcessCreateRequest[]>({ default: () => [] })

const { t } = useI18n()
const toast = useAppToast()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const fabricationMethodsStore = useFabricationMethodsStore()
const inspectionMethodsStore = useInspectionMethodsStore()

onMounted(() => {
  if (fabricationMethodsStore.items.length === 0) {
    void fabricationMethodsStore.refresh()
  }
  if (inspectionMethodsStore.items.length === 0) {
    void inspectionMethodsStore.refresh()
  }
})

// Archived methods stay selectable, sorted last, but a new row defaults to
// the first live method.
const { sortedOptions: fabricationMethodOptions, isArchived: isFabricationMethodArchived } =
  useArchivableOptions(computed(() => fabricationMethodsStore.items))
const { sortedOptions: inspectionMethodOptions, isArchived: isInspectionMethodArchived } =
  useArchivableOptions(computed(() => inspectionMethodsStore.items))

function fabricationMethodById(id: number | null) {
  return fabricationMethodsStore.getById(id) ?? null
}

function inspectionMethodById(id: number | null) {
  return inspectionMethodsStore.getById(id) ?? null
}

const rollup = computed(() =>
  processes.value.reduce(
    (acc, p) => ({
      setup: acc.setup + (p.estimated_setup_minutes ?? 0),
      perPiece: acc.perPiece + (p.estimated_minutes_per_piece ?? 0),
    }),
    { setup: 0, perPiece: 0 },
  ),
)

function addProcess(): void {
  const firstMethod = fabricationMethodsStore.activeItems[0]
  if (!firstMethod) {
    toast.warn(t('madeItems.catalogue.processes.noMethodsAvailable'))
    return
  }
  processes.value = [
    ...processes.value,
    {
      role: 'fabrication',
      fabrication_method_id: firstMethod.id,
      note: null,
      estimated_setup_minutes: null,
      estimated_minutes_per_piece: null,
      group_index: null,
    },
  ]
}

// Defaults to the first active inspection method.
function addInspectionProcess(): void {
  const firstMethod = inspectionMethodsStore.activeItems[0]
  if (!firstMethod) {
    toast.warn(t('madeItems.catalogue.processes.noInspectionMethodsAvailable'))
    return
  }
  processes.value = [
    ...processes.value,
    {
      role: 'inspection',
      fabrication_method_id: null,
      inspection_method_id: firstMethod.id,
      note: null,
      estimated_setup_minutes: null,
      estimated_minutes_per_piece: null,
      group_index: null,
    },
  ]
}

const addSplitButtonItems = computed<MenuItem[]>(() => [
  {
    label: t('madeItems.catalogue.processes.addInspection'),
    icon: 'mdi mdi-check-decagram',
    command: () => addInspectionProcess(),
  },
])

function removeProcess(index: number): void {
  processes.value = normalizeGroupIndexes(processes.value.filter((_, i) => i !== index))
}

function onRowReorder(event: { value: MadeItemProcessCreateRequest[] }): void {
  processes.value = normalizeGroupIndexes(event.value)
}
</script>

<template>
  <div class="process-editor">
    <div class="process-editor-header">
      <span class="process-editor-title">{{ t('madeItems.create.processesTitle') }}</span>
      <span class="process-editor-rollup">
        {{ t('madeItems.catalogue.detail.rollupSetup') }}: {{ rollup.setup }} ·
        {{ t('madeItems.catalogue.detail.rollupPerPiece') }}: {{ rollup.perPiece }}
      </span>
      <SplitButton
        :label="t('madeItems.catalogue.processes.add')"
        icon="mdi mdi-plus"
        size="small"
        severity="secondary"
        outlined
        :model="addSplitButtonItems"
        @click="addProcess"
      />
    </div>

    <DataTable
      :value="processes"
      size="small"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
      reorderable-rows
      @row-reorder="onRowReorder"
    >
      <Column row-reorder header-style="width: 2.5rem" />
      <Column
        field="fabrication_method_id"
        :header="t('madeItems.catalogue.processes.fabricationMethod')"
        style="min-width: 12rem"
      >
        <template #body="{ data }">
          <Select
            v-if="data.role !== 'inspection'"
            v-model="data.fabrication_method_id"
            :aria-label="t('madeItems.catalogue.processes.fabricationMethod')"
            :options="fabricationMethodOptions"
            :option-label="labelName"
            option-value="id"
            fluid
          >
            <template #option="{ option }">
              <span>{{ localizeLabel(option.name) }}</span>
              <ArchivedOptionTag v-if="option.archived" />
            </template>
            <template #value="{ value }">
              <span v-if="value !== null">{{
                localizeLabel(fabricationMethodById(value)?.name) || getEmptyPlaceholder()
              }}</span>
              <ArchivedOptionTag v-if="isFabricationMethodArchived(fabricationMethodById(value))" />
            </template>
          </Select>
          <Select
            v-else
            v-model="data.inspection_method_id"
            :aria-label="t('madeItems.catalogue.processes.fabricationMethod')"
            :options="inspectionMethodOptions"
            :option-label="labelName"
            option-value="id"
            fluid
          >
            <template #option="{ option }">
              <span>{{ localizeLabel(option.name) }}</span>
              <ArchivedOptionTag v-if="option.archived" />
            </template>
            <template #value="{ value }">
              <span v-if="value !== null">{{
                localizeLabel(inspectionMethodById(value)?.name) || getEmptyPlaceholder()
              }}</span>
              <ArchivedOptionTag v-if="isInspectionMethodArchived(inspectionMethodById(value))" />
            </template>
          </Select>
        </template>
      </Column>
      <Column
        field="estimated_setup_minutes"
        :header="t('madeItems.catalogue.processes.setupMinutes')"
        style="width: 9rem"
      >
        <template #body="{ data }">
          <InputNumber v-model="data.estimated_setup_minutes" :min="0" fluid />
        </template>
      </Column>
      <Column
        field="estimated_minutes_per_piece"
        :header="t('madeItems.catalogue.processes.perPieceMinutes')"
        style="width: 9rem"
      >
        <template #body="{ data }">
          <InputNumber
            v-model="data.estimated_minutes_per_piece"
            :min="0"
            :min-fraction-digits="0"
            :max-fraction-digits="2"
            fluid
          />
        </template>
      </Column>
      <Column
        field="note"
        :header="t('madeItems.catalogue.processes.note')"
        style="min-width: 10rem"
      >
        <template #body="{ data }">
          <InputText v-model="data.note" fluid />
        </template>
      </Column>
      <Column header-style="width: 3rem">
        <template #body="{ index }">
          <Button
            icon="mdi mdi-delete-outline"
            size="small"
            severity="danger"
            text
            rounded
            :aria-label="t('common.delete')"
            @click="removeProcess(index)"
          />
        </template>
      </Column>

      <template #empty>
        <EmptyState :message="t('madeItems.catalogue.detail.noProcesses')" />
      </template>
    </DataTable>
  </div>
</template>

<style scoped lang="scss">
.process-editor {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.process-editor-header {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.process-editor-title {
  font-size: var(--font-size-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--p-text-muted-color);
}

.process-editor-rollup {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
  flex: 1;
}
</style>
