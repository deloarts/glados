<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import type { DataTableRowContextMenuEvent } from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'

import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import { useFabricationMethodsStore } from '@/features/fabrication-methods'
import { useInspectionMethodsStore } from '@/features/inspection-methods'
import { createMadeItemProcess } from '../api/createMadeItemProcess'
import { updateMadeItemProcess } from '../api/updateMadeItemProcess'
import { deleteMadeItemProcess } from '../api/deleteMadeItemProcess'
import { reorderMadeItemProcesses } from '../api/reorderMadeItemProcesses'
import { storeToRefs } from 'pinia'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { useClipboard } from '@/core/composables/useClipboard'
import { processMethodLabel } from '../utils/madeItemProcessGroups'
import EmptyState from '@/shared/components/EmptyState.vue'

import type { MadeItemProcessResponse } from '../types/madeItemsResponse'
import type { MadeItemResponse } from '../types/madeItemsResponse'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { useConfirmDelete } from '@/shared/composables/useConfirmDelete'
import { labelName, localizeLabel } from '@/shared/utils/localizeLabel'

const props = withDefaults(
  defineProps<{
    item: MadeItemResponse
    readonly?: boolean
  }>(),
  { readonly: false },
)

const emit = defineEmits<{
  updated: [processes: MadeItemProcessResponse[]]
}>()

const { t } = useI18n()
const { toastOnError, withErrorToast } = useErrorToast()
const { confirmDelete } = useConfirmDelete()
const toast = useAppToast()
const { copyToClipboard } = useClipboard()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const { hasPermission } = usePermissions()
const fabricationMethodsStore = useFabricationMethodsStore()
const inspectionMethodsStore = useInspectionMethodsStore()

const canWrite = computed(() => hasPermission(Permission.WRITE_MADE_ITEMS))
const canEdit = computed(() => canWrite.value && !props.readonly)

const processes = ref<MadeItemProcessResponse[]>([...(props.item.processes ?? [])])
const savingRowId = ref<number | null>(null)

onMounted(() => {
  if (fabricationMethodsStore.items.length === 0) {
    void fabricationMethodsStore.refresh()
  }
  if (inspectionMethodsStore.items.length === 0) {
    void inspectionMethodsStore.refresh()
  }
})

const rollup = computed(() =>
  processes.value.reduce(
    (acc, p) => ({
      setup: acc.setup + (p.estimated_setup_minutes ?? 0),
      perPiece: acc.perPiece + (p.estimated_minutes_per_piece ?? 0),
    }),
    { setup: 0, perPiece: 0 },
  ),
)

function fabricationMethodName(id: number): string {
  return localizeLabel(fabricationMethodsStore.getById(id)?.name) || getEmptyPlaceholder()
}

// Inspection rows show the QA label; fabrication rows show the live method
// name, which follows a renamed archived method.
function readOnlyMethodLabel(row: MadeItemProcessResponse): string {
  if (row.role === 'inspection') return processMethodLabel(row)
  return fabricationMethodName(row.fabrication_method_id)
}

// Archived methods stay selectable, sorted last, but a new process defaults
// to the first live method.
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

function emitUpdated(): void {
  emit('updated', processes.value)
}

async function addProcess(): Promise<void> {
  const firstMethod = fabricationMethodsStore.activeItems[0]
  if (!firstMethod) {
    toast.warn(t('madeItems.catalogue.processes.noMethodsAvailable'))
    return
  }
  const created = await createMadeItemProcess(props.item.id, {
    role: 'fabrication',
    fabrication_method_id: firstMethod.id,
  })
  processes.value = [...processes.value, created]
  emitUpdated()
}

// Defaults to the first active inspection method.
async function addInspectionProcess(): Promise<void> {
  const firstMethod = inspectionMethodsStore.activeItems[0]
  if (!firstMethod) {
    toast.warn(t('madeItems.catalogue.processes.noInspectionMethodsAvailable'))
    return
  }
  const created = await createMadeItemProcess(props.item.id, {
    role: 'inspection',
    inspection_method_id: firstMethod.id,
  })
  processes.value = [...processes.value, created]
  emitUpdated()
}

const addSplitButtonItems = computed<MenuItem[]>(() => [
  {
    label: t('madeItems.catalogue.processes.addInspection'),
    icon: 'mdi mdi-check-decagram',
    command: () => void addInspectionProcess().catch(toastOnError()),
  },
])

async function onFieldChange(row: MadeItemProcessResponse): Promise<void> {
  savingRowId.value = row.id
  try {
    const updated = await updateMadeItemProcess(props.item.id, row.id, {
      fabrication_method_id: row.fabrication_method_id,
      inspection_method_id: row.inspection_method_id,
      note: row.note,
      estimated_setup_minutes: row.estimated_setup_minutes,
      estimated_minutes_per_piece: row.estimated_minutes_per_piece,
    })
    const idx = processes.value.findIndex((p) => p.id === row.id)
    if (idx !== -1) processes.value[idx] = updated
    emitUpdated()
  } finally {
    savingRowId.value = null
  }
}

// A step is deleted for good, so the user confirms first.
async function removeProcess(row: MadeItemProcessResponse): Promise<void> {
  if (savingRowId.value !== null) return
  if (!(await confirmDelete(readOnlyMethodLabel(row)))) return
  savingRowId.value = row.id
  try {
    const removed = await withErrorToast(
      async () => {
        await deleteMadeItemProcess(props.item.id, row.id)
        return true
      },
      { summary: t('madeItems.catalogue.columns.processes') },
    )
    if (!removed) return
    processes.value = processes.value.filter((p) => p.id !== row.id)
    emitUpdated()
  } finally {
    savingRowId.value = null
  }
}

// The new order shows at once; a refused reorder puts the old one back.
async function onRowReorder(event: { value: MadeItemProcessResponse[] }): Promise<void> {
  const previous = processes.value
  processes.value = event.value
  const reordered = await withErrorToast(
    () =>
      reorderMadeItemProcesses(
        props.item.id,
        event.value.map((p) => p.id),
      ),
    { summary: t('madeItems.catalogue.columns.processes') },
  )
  if (!reordered) {
    processes.value = previous
    return
  }
  processes.value = reordered
  emitUpdated()
}

const cm = ref()
const contextMenuItem = ref<MadeItemProcessResponse | null>(null)

function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
  cm.value?.show(event.originalEvent)
}

const contextMenuItems = computed<MenuItem[]>(() => {
  const process = contextMenuItem.value
  if (!process) return []

  return [
    {
      label: t('common.copyUuid'),
      icon: 'mdi mdi-content-copy',
      command: () => void copyToClipboard(process.public_id),
    },
  ]
})
</script>

<template>
  <div class="process-editor">
    <div class="process-editor-header">
      <span class="process-editor-title">{{ t('madeItems.catalogue.processes.title') }}</span>
      <span class="process-editor-rollup">
        {{ t('madeItems.catalogue.detail.rollupSetup') }}: {{ rollup.setup }} ·
        {{ t('madeItems.catalogue.detail.rollupPerPiece') }}: {{ rollup.perPiece }}
      </span>
      <SplitButton
        v-if="canEdit"
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
      v-model:context-menu-selection="contextMenuItem"
      data-key="id"
      size="small"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
      :reorderable-rows="canEdit"
      @row-reorder="onRowReorder"
      @row-contextmenu="onRowContextMenu"
    >
      <Column v-if="canEdit" row-reorder header-style="width: 2.5rem" />
      <Column
        field="fabrication_method_id"
        :header="t('madeItems.catalogue.processes.fabricationMethod')"
        style="min-width: 12rem"
      >
        <template #body="{ data }">
          <Select
            v-if="canEdit && data.role === 'fabrication'"
            v-model="data.fabrication_method_id"
            :aria-label="t('madeItems.catalogue.processes.fabricationMethod')"
            :options="fabricationMethodOptions"
            :option-label="labelName"
            option-value="id"
            fluid
            @change="onFieldChange(data)"
          >
            <template #option="{ option }">
              <span>{{ localizeLabel(option.name) }}</span>
              <ArchivedOptionTag v-if="option.archived" />
            </template>
            <template #value="{ value }">
              <span v-if="value !== null">{{ fabricationMethodName(value) }}</span>
              <ArchivedOptionTag v-if="isFabricationMethodArchived(fabricationMethodById(value))" />
            </template>
          </Select>
          <Select
            v-else-if="canEdit"
            v-model="data.inspection_method_id"
            :aria-label="t('madeItems.catalogue.processes.fabricationMethod')"
            :options="inspectionMethodOptions"
            :option-label="labelName"
            option-value="id"
            fluid
            @change="onFieldChange(data)"
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
          <span v-else class="cell-text">{{ readOnlyMethodLabel(data) }}</span>
        </template>
      </Column>
      <Column
        field="estimated_setup_minutes"
        :header="t('madeItems.catalogue.processes.setupMinutes')"
        style="width: 9rem"
      >
        <template #body="{ data }">
          <InputNumber
            v-if="canEdit"
            v-model="data.estimated_setup_minutes"
            :min="0"
            fluid
            @blur="onFieldChange(data)"
          />
          <span v-else class="cell-text">{{
            data.estimated_setup_minutes ?? getEmptyPlaceholder()
          }}</span>
        </template>
      </Column>
      <Column
        field="estimated_minutes_per_piece"
        :header="t('madeItems.catalogue.processes.perPieceMinutes')"
        style="width: 9rem"
      >
        <template #body="{ data }">
          <InputNumber
            v-if="canEdit"
            v-model="data.estimated_minutes_per_piece"
            :min="0"
            :min-fraction-digits="0"
            :max-fraction-digits="2"
            fluid
            @blur="onFieldChange(data)"
          />
          <span v-else class="cell-text">{{
            data.estimated_minutes_per_piece ?? getEmptyPlaceholder()
          }}</span>
        </template>
      </Column>
      <Column
        field="note"
        :header="t('madeItems.catalogue.processes.note')"
        style="min-width: 10rem"
      >
        <template #body="{ data }">
          <InputText v-if="canEdit" v-model="data.note" fluid @blur="onFieldChange(data)" />
          <span v-else class="cell-text">{{ data.note || getEmptyPlaceholder() }}</span>
        </template>
      </Column>
      <Column v-if="canEdit" header-style="width: 3rem">
        <template #body="{ data }">
          <Button
            icon="mdi mdi-delete-outline"
            size="small"
            severity="danger"
            text
            rounded
            :loading="savingRowId === data.id"
            :aria-label="t('common.delete')"
            @click="removeProcess(data)"
          />
        </template>
      </Column>

      <template #empty>
        <EmptyState :message="t('madeItems.catalogue.detail.noProcesses')" />
      </template>
    </DataTable>

    <ContextMenu ref="cm" :model="contextMenuItems" @hide="contextMenuItem = null" />
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

.cell-text {
  font-size: var(--font-size-sm);
}
</style>
