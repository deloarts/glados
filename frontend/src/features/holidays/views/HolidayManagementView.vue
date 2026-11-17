<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { useConfirm } from 'openvue/useconfirm'

import { useAppToast } from '@/core/composables/useAppToast'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { extractApiError } from '@/core/utils/errors'
import { formatISODate, toDateKey, toLocalDayStart } from '@/core/utils/dates'
import EmptyState from '@/shared/components/EmptyState.vue'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import { HelpButton } from '@/shared/help'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'

import {
  createTenantHoliday,
  deleteTenantHoliday,
  getTenantHolidays,
  updateTenantHoliday,
} from '../api/holidaysApi'
import type { HolidayCategory, TenantHoliday } from '../types/holidayTypes'

// Public holidays and plant shutdowns close every machine's calendar. A
// machine's own calendar exception still opens it on such a day.

const CATEGORIES: HolidayCategory[] = ['public_holiday', 'plant_shutdown']
const DAY_MS = 24 * 60 * 60 * 1000

const { t } = useI18n()
const toast = useAppToast()
const confirm = useConfirm()
const { hasPermission } = usePermissions()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const { missing } = useMissingPermission()

const canWrite = hasPermission(Permission.WRITE_MACHINES)
const canDelete = hasPermission(Permission.WRITE_MACHINES)
const writeHint = computed(() => missing(Permission.WRITE_MACHINES) || undefined)
const deleteHint = computed(() => missing(Permission.WRITE_MACHINES) || undefined)

const holidays = ref<TenantHoliday[]>([])
const loading = ref(false)
watchLoadingBar(loading)

const categoryOptions = computed(() =>
  CATEGORIES.map((value) => ({ value, label: t(`resources.holidays.categories.${value}`) })),
)

interface HolidayForm {
  id: number | null
  name: string
  category: HolidayCategory
  start: Date | null
  end: Date | null
}

const dialogVisible = ref(false)
const saving = ref(false)
const formError = ref<string | null>(null)
const form = reactive<HolidayForm>({
  id: null,
  name: '',
  category: 'public_holiday',
  start: null,
  end: null,
})

function dayCount(holiday: TenantHoliday): number {
  const start = Date.parse(holiday.start_date)
  const end = Date.parse(holiday.end_date)
  return Math.round((end - start) / DAY_MS) + 1
}

async function load(): Promise<void> {
  loading.value = true
  try {
    holidays.value = await getTenantHolidays()
  } catch (e) {
    toast.error(extractApiError(e) ?? t('resources.holidays.errors.unknown'))
  } finally {
    loading.value = false
  }
}

onMounted(() => void load())

function openCreate(): void {
  Object.assign(form, { id: null, name: '', category: 'public_holiday', start: null, end: null })
  formError.value = null
  dialogVisible.value = true
}

function openEdit(holiday: TenantHoliday): void {
  Object.assign(form, {
    id: holiday.id,
    name: holiday.name,
    category: holiday.category,
    // Calendar dates, put on the picker's local calendar without a day shift.
    start: toLocalDayStart(holiday.start_date),
    end: toLocalDayStart(holiday.end_date),
  })
  formError.value = null
  dialogVisible.value = true
}

async function onSave(): Promise<void> {
  if (!form.name.trim() || !form.start) {
    formError.value = t('resources.holidays.errors.required')
    return
  }
  const cmd = {
    name: form.name.trim(),
    category: form.category,
    start_date: toDateKey(form.start),
    end_date: toDateKey(form.end ?? form.start),
  }
  saving.value = true
  formError.value = null
  try {
    if (form.id === null) {
      await createTenantHoliday(cmd)
    } else {
      await updateTenantHoliday(form.id, cmd)
    }
    dialogVisible.value = false
    toast.success(t('resources.holidays.saved'))
    await load()
  } catch (e) {
    formError.value = extractApiError(e) ?? t('resources.holidays.errors.unknown')
  } finally {
    saving.value = false
  }
}

function onDelete(holiday: TenantHoliday): void {
  async function onAccept(): Promise<void> {
    try {
      await deleteTenantHoliday(holiday.id)
      holidays.value = holidays.value.filter((h) => h.id !== holiday.id)
    } catch (e) {
      toast.error(extractApiError(e) ?? t('resources.holidays.errors.unknown'))
    }
  }

  confirm.require({
    message: t('resources.holidays.deleteConfirm', { name: holiday.name }),
    header: t('common.delete'),
    icon: 'mdi mdi-delete-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('common.delete'), severity: 'danger' },
    accept: () => void onAccept(),
  })
}
</script>

<template>

  <PageLayout>
    <template #controls>
      <ControlsBar>
        <template #start>
          <span v-tooltip.bottom="writeHint">
            <Button
              :label="t('resources.holidays.add')"
              icon="mdi mdi-plus"
              text
              severity="contrast"
              :disabled="!canWrite"
              @click="openCreate"
            />
          </span>
          <Button
            :label="t('common.reload')"
            icon="mdi mdi-refresh"
            text
            severity="contrast"
            :loading="loading"
            @click="load"
          />
        </template>
        <template #handbook>
          <HelpButton rounded />
        </template>
      </ControlsBar>
    </template>

    <p class="hint">{{ t('resources.holidays.hint') }}</p>

    <DataTable
      :value="holidays"
      data-key="id"
      scrollable
      scroll-height="flex"
      size="small"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
    >
      <Column header="#" header-style="width: 3rem" body-class="row-number">
        <template #body="{ index }">{{ index + 1 }}</template>
      </Column>
      <Column field="name" :header="t('resources.holidays.columns.name')" />
      <Column :header="t('resources.holidays.columns.category')" style="width: 12rem">
        <template #body="{ data }">
          {{ t(`resources.holidays.categories.${(data as TenantHoliday).category}`) }}
        </template>
      </Column>
      <Column :header="t('resources.holidays.columns.from')" style="width: 9rem">
        <template #body="{ data }">{{ formatISODate((data as TenantHoliday).start_date) }}</template>
      </Column>
      <Column :header="t('resources.holidays.columns.to')" style="width: 9rem">
        <template #body="{ data }">{{ formatISODate((data as TenantHoliday).end_date) }}</template>
      </Column>
      <Column :header="t('resources.holidays.columns.days')" style="width: 6rem">
        <template #body="{ data }">{{ dayCount(data as TenantHoliday) }}</template>
      </Column>
      <Column style="width: 6rem">
        <template #body="{ data }">
          <span class="row-actions">
            <span v-tooltip.left="writeHint">
              <Button
                icon="mdi mdi-pencil"
                size="small"
                severity="secondary"
                text
                :disabled="!canWrite"
                :aria-label="t('resources.holidays.edit')"
                @click="openEdit(data as TenantHoliday)"
              />
            </span>
            <span v-tooltip.left="deleteHint">
              <Button
                icon="mdi mdi-delete-outline"
                size="small"
                severity="danger"
                text
                :disabled="!canDelete"
                :aria-label="t('common.delete')"
                @click="onDelete(data as TenantHoliday)"
              />
            </span>
          </span>
        </template>
      </Column>
      <template #empty>
        <EmptyState :message="t('resources.holidays.empty')" />
      </template>
    </DataTable>

    <Dialog
      v-model:visible="dialogVisible"
      modal
      :header="form.id === null ? t('resources.holidays.add') : t('resources.holidays.edit')"
      :style="{ width: 'var(--dialog-width-sm)' }"
    >
      <form class="holiday-form" @submit.prevent="onSave">
        <label class="field">
          {{ t('resources.holidays.columns.name') }}
          <InputText v-model="form.name" size="small" />
        </label>
        <label class="field">
          {{ t('resources.holidays.columns.category') }}
          <Select
            v-model="form.category"
            :aria-label="t('resources.holidays.columns.category')"
            :options="categoryOptions"
            option-label="label"
            option-value="value"
            size="small"
          />
        </label>
        <label class="field">
          {{ t('resources.holidays.columns.from') }}
          <DatePicker v-model="form.start" show-button-bar size="small" />
        </label>
        <label class="field">
          {{ t('resources.holidays.columns.to') }}
          <DatePicker
            v-model="form.end"
            show-button-bar
            :min-date="form.start ?? undefined"
            :placeholder="t('resources.holidays.sameDay')"
            size="small"
          />
        </label>
        <Message v-if="formError" severity="error" :closable="false">{{ formError }}</Message>
      </form>
      <template #footer>
        <Button
          :label="t('common.cancel')"
          severity="secondary"
          text
          @click="dialogVisible = false"
        />
        <Button
          :label="t('common.save')"
          icon="mdi mdi-content-save"
          :loading="saving"
          @click="onSave"
        />
      </template>
    </Dialog>
  </PageLayout>
</template>

<style scoped lang="scss">
.hint {
  margin: 0;
  padding: var(--space-3) var(--space-4);
}

.holiday-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.field {
  font-size: var(--font-size-sm);
}
</style>
