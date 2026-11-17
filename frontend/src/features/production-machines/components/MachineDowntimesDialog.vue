<script setup lang="ts">
// Cross-machine downtime browser with period and machine filters, an End
// action on open rows and Delete for writers. Opens unfiltered or
// pre-filtered to one machine.
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'

import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { API_MAX_PAGE_SIZE } from '@/core/constants/table'
import { extractApiError } from '@/core/utils/errors'
import EmptyState from '@/shared/components/EmptyState.vue'
import { HelpDrawer } from '@/shared/help'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'

import { getProductionMachines } from '../api/getProductionMachines'
import { getMachineDowntimes } from '../api/getMachineDowntimes'
import { endMachineDowntime } from '../api/endMachineDowntime'
import { deleteMachineDowntime } from '../api/deleteMachineDowntime'

import type { ProductionMachineResponse } from '../types/productionMachinesResponse'
import type { MachineDowntimeResponse } from '../types/machineDowntimeResponse'

interface Props {
  // Pre-selects the machine filter; it stays editable.
  initialMachineId?: number | null
}

const props = withDefaults(defineProps<Props>(), { initialMachineId: null })

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const toast = useAppToast()
const { withErrorToast } = useErrorToast()
const confirm = useConfirm()
const { hasPermission } = usePermissions()

const canWrite = computed(() => hasPermission(Permission.WRITE_MACHINES))
const explainVisible = ref(false)

const loading = ref(false)
watchLoadingBar(loading)

const machines = ref<ProductionMachineResponse[]>([])
const downtimes = ref<MachineDowntimeResponse[]>([])

interface Filters {
  machineId: number | null
  from: Date | null
  to: Date | null
}

const filters = reactive<Filters>({ machineId: null, from: null, to: null })

const machineOptions = computed(() =>
  [...machines.value].sort((a, b) => a.internal_name.localeCompare(b.internal_name)),
)

// A picked day maps to the local instant range of that day.
function dayStartISO(d: Date): string {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).toISOString()
}
function dayEndISO(d: Date): string {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + 1).toISOString()
}

async function load(): Promise<void> {
  loading.value = true
  await withErrorToast(
    async () => {
      const result = await getMachineDowntimes({
        machine_id: filters.machineId ?? undefined,
        started_from: filters.from ? dayStartISO(filters.from) : undefined,
        started_to: filters.to ? dayEndISO(filters.to) : undefined,
        limit: 100,
        order_by: 'started_at',
        order_dir: 'desc',
      })
      downtimes.value = result.items
    },
    { summary: t('productionMachines.downtime.list.loadError') },
  )
  loading.value = false
}

watch(visible, async (isVisible) => {
  if (!isVisible) return
  filters.machineId = props.initialMachineId
  filters.from = null
  filters.to = null
  if (machines.value.length === 0) {
    machines.value = (await getProductionMachines({ limit: API_MAX_PAGE_SIZE, include_archived: true })).items
  }
  await load()
})

watch(
  () => [filters.machineId, filters.from, filters.to],
  () => {
    if (visible.value) void load()
  },
)

async function onEnd(downtime: MachineDowntimeResponse): Promise<void> {
  try {
    const updated = await endMachineDowntime(downtime.id)
    const index = downtimes.value.findIndex((d) => d.id === updated.id)
    if (index !== -1) downtimes.value[index] = updated
  } catch (e) {
    // The server says why, such as another user ending the downtime first,
    // and the reload shows the row as it stands now.
    toast.error(
      downtime.machine_internal_name,
      extractApiError(e) ?? t('productionMachines.downtime.list.endError'),
    )
    await load()
  }
}

function onDelete(downtime: MachineDowntimeResponse): void {
  async function onAccept(): Promise<void> {
    try {
      await deleteMachineDowntime(downtime.id)
      downtimes.value = downtimes.value.filter((d) => d.id !== downtime.id)
    } catch (e) {
      toast.error(
        downtime.machine_internal_name,
        extractApiError(e) ?? t('productionMachines.downtime.list.deleteError'),
      )
      await load()
    }
  }

  confirm.require({
    message: t('productionMachines.downtime.list.deleteConfirm', {
      machine: downtime.machine_internal_name,
    }),
    header: t('common.delete'),
    icon: 'mdi mdi-delete-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('common.delete'), severity: 'danger' },
    accept: () => void onAccept(),
  })
}

function onClose(): void {
  visible.value = false
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="{ width: 'var(--dialog-width-lg)' }"
  >
    <template #header>
      <div class="downtimes-header">
        <span class="p-dialog-title">{{ t('productionMachines.downtime.list.title') }}</span>
        <Button
          type="button"
          class="downtimes-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('productionMachines.downtime.list.explain')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('productionMachines.downtime.list.explain')"
          data-testid="downtimes-explain"
          @click="explainVisible = true"
        />
      </div>
    </template>
    <div class="downtimes-dialog">
      <div class="filters-row">
        <div class="filter-field">
          <label id="dt-filter-machine-label" for="dt-filter-machine">{{
            t('productionMachines.downtime.list.machineFilter')
          }}</label>
          <Select
            id="dt-filter-machine"
            aria-labelledby="dt-filter-machine-label"
            v-model="filters.machineId"
            :options="machineOptions"
            option-label="internal_name"
            option-value="id"
            show-clear
            filter
            :placeholder="t('productionMachines.downtime.list.machineFilterPlaceholder')"
          />
        </div>
        <div class="filter-field">
          <label for="dt-filter-from">{{ t('productionMachines.downtime.list.periodFrom') }}</label>
          <DatePicker id="dt-filter-from" v-model="filters.from" show-button-bar show-icon />
        </div>
        <div class="filter-field">
          <label for="dt-filter-to">{{ t('productionMachines.downtime.list.periodTo') }}</label>
          <DatePicker id="dt-filter-to" v-model="filters.to" show-button-bar show-icon />
        </div>
      </div>

      <DataTable :value="downtimes" size="small" data-key="id" :loading="loading">
        <Column
          field="machine_internal_name"
          :header="t('productionMachines.downtime.list.columns.machine')"
        />
        <Column :header="t('productionMachines.downtime.list.columns.startedAt')">
          <template #body="{ data }">
            <UserDateCell
              :date="(data as MachineDowntimeResponse).started_at"
              :user-id="(data as MachineDowntimeResponse).reported_by_id"
              :name="(data as MachineDowntimeResponse).reported_by_full_name"
              with-time
            />
          </template>
        </Column>
        <Column :header="t('productionMachines.downtime.list.columns.endedAt')">
          <template #body="{ data }">
            <Tag
              v-if="(data as MachineDowntimeResponse).ended_at === null"
              severity="danger"
              :value="t('productionMachines.downtime.list.open')"
            />
            <UserDateCell
              v-else
              :date="(data as MachineDowntimeResponse).ended_at"
              :user-id="(data as MachineDowntimeResponse).ended_by_id"
              :name="(data as MachineDowntimeResponse).ended_by_full_name"
              with-time
            />
          </template>
        </Column>
        <Column :header="t('productionMachines.downtime.list.columns.reason')">
          <template #body="{ data }">{{
            t(`productionMachines.downtime.reasons.${(data as MachineDowntimeResponse).reason}`)
          }}</template>
        </Column>
        <Column style="width: 6rem">
          <template #body="{ data }">
            <div class="row-actions">
              <Button
                v-if="(data as MachineDowntimeResponse).ended_at === null"
                icon="mdi mdi-stop-circle-outline"
                size="small"
                severity="secondary"
                text
                :disabled="!canWrite"
                v-tooltip.top.focus="t('productionMachines.downtime.list.end')"
                :aria-label="t('productionMachines.downtime.list.end')"
                @click="onEnd(data as MachineDowntimeResponse)"
              />
              <Button
                icon="mdi mdi-delete-outline"
                size="small"
                severity="danger"
                text
                :disabled="!canWrite"
                v-tooltip.top.focus="t('common.delete')"
                :aria-label="t('common.delete')"
                @click="onDelete(data as MachineDowntimeResponse)"
              />
            </div>
          </template>
        </Column>
        <template #empty>
          <EmptyState :message="t('productionMachines.downtime.list.empty')" />
        </template>
      </DataTable>
    </div>

    <template #footer>
      <Button :label="t('common.close')" severity="secondary" @click="onClose" />
    </template>
  </Dialog>
  <HelpDrawer v-model:visible="explainVisible" slug="resources/machines" anchor="downtimes" />
</template>

<style scoped lang="scss">
.downtimes-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.downtimes-explain-button :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.downtimes-dialog {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.filters-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.filter-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);

  label {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}
</style>
