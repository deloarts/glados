<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'
import { useConfirm } from 'openvue/useconfirm'

import type { DataTableRowContextMenuEvent } from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'

import { extractApiError } from '@/core/utils/errors'
import { toDateKey, toLocalDayStart } from '@/core/utils/dates'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { useAdminSettingsStore } from '@/features/admin-settings'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useClipboard } from '@/core/composables/useClipboard'
import WeeklyHoursGrid from '@/shared/components/WeeklyHoursGrid.vue'
import EmptyState from '@/shared/components/EmptyState.vue'

import { getMachineWorkingHours } from '../api/getMachineWorkingHours'
import { setMachineWorkingHours } from '../api/setMachineWorkingHours'
import { deleteMachineWorkingHours } from '../api/deleteMachineWorkingHours'
import { getMachineCalendarExceptions } from '../api/getMachineCalendarExceptions'
import { createMachineCalendarException } from '../api/createMachineCalendarException'
import { updateMachineCalendarException } from '../api/updateMachineCalendarException'
import { deleteMachineCalendarException } from '../api/deleteMachineCalendarException'

import type { ProductionMachineResponse } from '../types/productionMachinesResponse'
import type { MachineCalendarExceptionResponse } from '../types/machineCalendarResponse'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import {
  DEFAULT_DAY_START,
  MINUTES_PER_DAY,
  copyWeeklyHours,
  defaultWeeklyHours,
  type WeeklyHours,
} from '@/shared/utils/weeklyHours'
import { HelpButton } from '@/shared/help'

interface Props {
  machine: ProductionMachineResponse | null
}

const props = defineProps<Props>()
const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const toast = useAppToast()
const confirm = useConfirm()
const { copyToClipboard } = useClipboard()
const { hasPermission } = usePermissions()
const adminSettingsStore = useAdminSettingsStore()

const canWrite = computed(() => hasPermission(Permission.WRITE_MACHINES))
// Without write:machines the exception controls stay visible but disabled.
const { missing } = useMissingPermission()
const writeBlocked = computed(() => missing(Permission.WRITE_MACHINES))

const loading = ref(false)
const savingHours = ref(false)

watchLoadingBar(loading)

const useOverride = ref(false)
// A ref (not reactive()) because WeeklyHoursGrid's v-model:hours replaces
// the whole object on every edit, reactive() can't be reassigned this way.
const hours = ref<WeeklyHours>(defaultWeeklyHours())

const globalDefault = computed<WeeklyHours>(
  () => adminSettingsStore.settings?.production?.default_weekly_hours ?? defaultWeeklyHours(),
)

const exceptions = ref<MachineCalendarExceptionResponse[]>([])

interface ExceptionForm {
  editingId: number | null
  exception_date: Date | null
  closed: boolean
  start: string
  available_minutes: number
  note: string
}

function emptyExceptionForm(): ExceptionForm {
  return {
    editingId: null,
    exception_date: null,
    closed: true,
    start: DEFAULT_DAY_START,
    available_minutes: 0,
    note: '',
  }
}

const exceptionForm = reactive<ExceptionForm>(emptyExceptionForm())
const savingException = ref(false)
const exceptionError = ref<string | null>(null)

function onErrorToast(e: unknown): void {
  toast.error(extractApiError(e) ?? t('productionMachines.errors.unknown'))
}

async function load(): Promise<void> {
  if (!props.machine) return
  loading.value = true
  try {
    if (!adminSettingsStore.settings) {
      await adminSettingsStore.fetch()
    }
    const [workingHours, exc] = await Promise.all([
      getMachineWorkingHours(props.machine.id),
      getMachineCalendarExceptions(props.machine.id),
    ])
    useOverride.value = workingHours !== null
    hours.value = copyWeeklyHours(workingHours ? workingHours.weekly_hours : globalDefault.value)
    exceptions.value = exc
  } catch (e) {
    onErrorToast(e)
  } finally {
    loading.value = false
  }
}

watch(visible, (isVisible) => {
  if (!isVisible) return
  Object.assign(exceptionForm, emptyExceptionForm())
  exceptionError.value = null
  void load()
})

async function onToggleOverride(value: boolean): Promise<void> {
  if (!props.machine) return
  const previous = useOverride.value
  useOverride.value = value
  if (value) return

  savingHours.value = true
  try {
    await deleteMachineWorkingHours(props.machine.id)
    hours.value = copyWeeklyHours(globalDefault.value)
    toast.success(t('adminSettings.saved'))
  } catch (e) {
    useOverride.value = previous
    onErrorToast(e)
  } finally {
    savingHours.value = false
  }
}

async function onSaveHours(): Promise<void> {
  if (!props.machine) return
  savingHours.value = true
  try {
    await setMachineWorkingHours(props.machine.id, { weekly_hours: copyWeeklyHours(hours.value) })
    toast.success(t('adminSettings.saved'))
  } catch (e) {
    onErrorToast(e)
  } finally {
    savingHours.value = false
  }
}

function onEditException(exception: MachineCalendarExceptionResponse): void {
  exceptionForm.editingId = exception.id
  exceptionForm.exception_date = toLocalDayStart(exception.exception_date)
  exceptionForm.closed = exception.available_minutes === 0
  exceptionForm.start = exception.start
  exceptionForm.available_minutes = exception.available_minutes
  exceptionForm.note = exception.note ?? ''
  exceptionError.value = null
}

function onCancelExceptionEdit(): void {
  Object.assign(exceptionForm, emptyExceptionForm())
  exceptionError.value = null
}

async function onSaveException(): Promise<void> {
  if (!props.machine) return
  if (!exceptionForm.exception_date) {
    exceptionError.value = t('productionMachines.calendar.exceptions.errors.dateRequired')
    return
  }

  const availableMinutes = exceptionForm.closed ? 0 : exceptionForm.available_minutes
  const notePayload = exceptionForm.note.trim() || null

  savingException.value = true
  exceptionError.value = null
  try {
    if (exceptionForm.editingId !== null) {
      const updated = await updateMachineCalendarException(exceptionForm.editingId, {
        available_minutes: availableMinutes,
        start: exceptionForm.start,
        note: notePayload,
      })
      const index = exceptions.value.findIndex((e) => e.id === updated.id)
      if (index !== -1) exceptions.value[index] = updated
    } else {
      const created = await createMachineCalendarException(props.machine.id, {
        exception_date: toDateKey(exceptionForm.exception_date),
        available_minutes: availableMinutes,
        start: exceptionForm.start,
        note: notePayload,
      })
      exceptions.value = [...exceptions.value, created].sort((a, b) =>
        a.exception_date.localeCompare(b.exception_date),
      )
    }
    Object.assign(exceptionForm, emptyExceptionForm())
  } catch (e) {
    exceptionError.value = extractApiError(e) ?? t('productionMachines.errors.unknown')
  } finally {
    savingException.value = false
  }
}

function onDeleteException(exception: MachineCalendarExceptionResponse): void {
  async function onAccept(): Promise<void> {
    try {
      await deleteMachineCalendarException(exception.id)
      exceptions.value = exceptions.value.filter((e) => e.id !== exception.id)
      if (exceptionForm.editingId === exception.id) {
        Object.assign(exceptionForm, emptyExceptionForm())
      }
    } catch (e) {
      onErrorToast(e)
    }
  }

  confirm.require({
    message: t('productionMachines.calendar.exceptions.deleteConfirm', {
      date: exception.exception_date,
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

const cm = ref()
const contextMenuItem = ref<MachineCalendarExceptionResponse | null>(null)

function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
  cm.value?.show(event.originalEvent)
}

const contextMenuItems = computed<MenuItem[]>(() => {
  const exception = contextMenuItem.value
  if (!exception) return []

  return [
    {
      label: t('common.copyUuid'),
      icon: 'mdi mdi-content-copy',
      command: () => void copyToClipboard(exception.public_id),
    },
  ]
})
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <template #header>
      <div class="machine-calendar-header">
        <span class="p-dialog-title">{{ t('productionMachines.calendar.title', { name: machine?.internal_name ?? '' }) }}</span>
        <span class="machine-calendar-help">
          <HelpButton slug="resources/machines" anchor="working-hours" icon="mdi mdi-help" rounded />
        </span>
      </div>
    </template>
    <div v-if="loading" class="calendar-dialog-loading" />

    <div v-else class="calendar-dialog">
      <div class="settings-section">
        <h3>{{ t('productionMachines.calendar.workingHours.title') }}</h3>
        <div class="override-toggle">
          <SelectButton
            :model-value="useOverride"
            :options="[
              { label: t('productionMachines.calendar.workingHours.useDefault'), value: false },
              { label: t('productionMachines.calendar.workingHours.useCustom'), value: true },
            ]"
            option-label="label"
            option-value="value"
            :disabled="!canWrite || savingHours"
            @update:model-value="onToggleOverride"
          />
        </div>

        <WeeklyHoursGrid
          v-model:hours="hours"
          :disabled="!canWrite || !useOverride || savingHours"
        />

        <Button
          v-if="useOverride"
          :label="t('common.save')"
          icon="mdi mdi-content-save"
          size="small"
          :loading="savingHours"
          :disabled="!canWrite"
          @click="onSaveHours"
        />
      </div>

      <div class="settings-section">
        <h3>{{ t('productionMachines.calendar.exceptions.title') }}</h3>

        <DataTable
          :value="exceptions"
          v-model:context-menu-selection="contextMenuItem"
          size="small"
          data-key="id"
          @row-contextmenu="onRowContextMenu"
        >
          <Column
            field="exception_date"
            :header="t('productionMachines.calendar.exceptions.columns.date')"
          />
          <Column :header="t('productionMachines.calendar.exceptions.columns.availableMinutes')">
            <template #body="{ data }">
              <span v-if="(data as MachineCalendarExceptionResponse).available_minutes === 0">
                {{ t('common.closed') }}
              </span>
              <span v-else>
                {{
                  t('productionMachines.calendar.exceptions.window', {
                    start: (data as MachineCalendarExceptionResponse).start,
                    minutes: (data as MachineCalendarExceptionResponse).available_minutes,
                  })
                }}
              </span>
            </template>
          </Column>
          <Column field="note" :header="t('productionMachines.calendar.exceptions.columns.note')">
            <template #body="{ data }">
              <span v-if="(data as MachineCalendarExceptionResponse).note">
                {{ (data as MachineCalendarExceptionResponse).note }}
              </span>
              <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
            </template>
          </Column>
          <Column style="width: 6rem">
            <template #body="{ data }">
              <div class="row-actions" v-tooltip.top="writeBlocked || undefined">
                <Button
                  icon="mdi mdi-pencil"
                  size="small"
                  severity="secondary"
                  text
                  :disabled="!canWrite"
                  :aria-label="t('productionMachines.calendar.exceptions.edit')"
                  @click="onEditException(data as MachineCalendarExceptionResponse)"
                />
                <Button
                  icon="mdi mdi-delete-outline"
                  size="small"
                  severity="danger"
                  text
                  :disabled="!canWrite"
                  :aria-label="t('common.delete')"
                  @click="onDeleteException(data as MachineCalendarExceptionResponse)"
                />
              </div>
            </template>
          </Column>
          <template #empty>
            <EmptyState :message="t('productionMachines.calendar.exceptions.empty')" />
          </template>
        </DataTable>

        <ContextMenu ref="cm" :model="contextMenuItems" @hide="contextMenuItem = null" />

        <form
          class="exception-form"
          data-testid="machine-calendar-exception-form"
          @submit.prevent="onSaveException"
        >
          <DatePicker
            v-model="exceptionForm.exception_date"
            show-button-bar
            :disabled="!canWrite || exceptionForm.editingId !== null"
            :placeholder="t('productionMachines.calendar.exceptions.columns.date')"
            size="small"
          />
          <label class="closed-toggle">
            <Checkbox v-model="exceptionForm.closed" binary :disabled="!canWrite" />
            {{ t('common.closed') }}
          </label>
          <InputText
            v-if="!exceptionForm.closed"
            v-model="exceptionForm.start"
            type="time"
            :disabled="!canWrite"
            :aria-label="t('common.weeklyHours.start')"
            size="small"
          />
          <InputNumber
            v-if="!exceptionForm.closed"
            v-model="exceptionForm.available_minutes"
            :min="0"
            :max="MINUTES_PER_DAY"
            suffix=" min"
            :disabled="!canWrite"
            size="small"
          />
          <InputText
            v-model="exceptionForm.note"
            :disabled="!canWrite"
            :placeholder="t('productionMachines.calendar.exceptions.columns.note')"
            size="small"
          />
          <div class="exception-form-actions">
            <Button
              v-if="exceptionForm.editingId !== null"
              type="button"
              :label="t('common.cancel')"
              severity="secondary"
              size="small"
              @click="onCancelExceptionEdit"
            />
            <span v-tooltip.top="writeBlocked || undefined">
              <Button
                type="submit"
                :label="
                  exceptionForm.editingId !== null
                    ? t('common.save')
                    : t('productionMachines.calendar.exceptions.add')
                "
                size="small"
                :disabled="!canWrite"
                :loading="savingException"
                data-testid="machine-calendar-exception-submit"
              />
            </span>
          </div>
        </form>
        <Message v-if="exceptionError" severity="error" class="mt-2">{{ exceptionError }}</Message>
      </div>
    </div>

    <template #footer>
      <Button :label="t('common.close')" severity="secondary" @click="onClose" />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.machine-calendar-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.machine-calendar-help :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.calendar-dialog {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.settings-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);

  h3 {
    margin: 0;
  }
}

.override-toggle {
  display: flex;
}

.exception-form {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.exception-form-actions {
  display: flex;
  gap: var(--space-2);
  margin-left: auto;
}

.closed-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
}

.calendar-dialog-loading {
  min-height: 12rem;
}
</style>
