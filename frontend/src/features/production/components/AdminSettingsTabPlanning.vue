<script setup lang="ts">
import { reactive, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { AdminSettingsTabShell, useAdminSettingsStore, useSettingsSave } from '@/features/admin-settings'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { formatISODateTime } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

// The planning features that work next to the scheduler: how far ahead the
// nightly baseline records, how long recorded plans are kept, and from when
// the booking quality view counts bookings. The last one is set once and
// only shown.
const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const store = useAdminSettingsStore()
const { hasPermission } = usePermissions()

const canWrite = hasPermission(Permission.WRITE_SETTINGS)

interface Form {
  commit_horizon_working_days: number
  plan_retention_days: number
}

const form = reactive<Form>({
  commit_horizon_working_days: 5,
  plan_retention_days: 400,
})

watch(
  () => store.settings?.planning,
  (p) => {
    if (!p) return
    form.commit_horizon_working_days = p.commit_horizon_working_days
    form.plan_retention_days = p.plan_retention_days
  },
  { immediate: true },
)

const { saving, onSave } = useSettingsSave(() => store.savePlanning({ ...form }))

defineExpose({ form })
</script>

<template>
  <AdminSettingsTabShell>
    <template #controls>
      <Toolbar>
        <template #start>
          <Button
            :label="t('common.save')"
            icon="mdi mdi-content-save"
            text
            severity="contrast"
            :loading="saving"
            :disabled="!canWrite"
            @click="onSave"
          />
        </template>
      </Toolbar>
    </template>

    <div class="settings-fields">
      <div class="field-row">
        <label :for="`${uid}-commit-horizon`">
          {{ t('adminSettings.planning.commitHorizonWorkingDays') }}
          <small class="hint">{{ t('adminSettings.planning.commitHorizonHint') }}</small>
        </label>
        <InputNumber
          v-model="form.commit_horizon_working_days"
          :input-id="`${uid}-commit-horizon`"
          :disabled="!canWrite"
          :min="1"
          :max="20"
          :use-grouping="false"
        />
      </div>
      <div class="field-row">
        <label :for="`${uid}-plan-retention`">
          {{ t('adminSettings.planning.planRetentionDays') }}
          <small class="hint">{{ t('adminSettings.planning.planRetentionHint') }}</small>
        </label>
        <InputNumber
          v-model="form.plan_retention_days"
          :input-id="`${uid}-plan-retention`"
          :disabled="!canWrite"
          :min="30"
          :max="3650"
          :use-grouping="false"
        />
      </div>
      <div class="field-row">
        <span :id="`${uid}-booking-quality-since`" class="field-caption">
          {{ t('adminSettings.planning.bookingQualitySince') }}
          <small class="hint">{{ t('adminSettings.planning.bookingQualitySinceHint') }}</small>
        </span>
        <span class="field-value" :aria-labelledby="`${uid}-booking-quality-since`">
          {{
            store.settings?.planning
              ? formatISODateTime(store.settings.planning.booking_quality_since)
              : getEmptyPlaceholder()
          }}
        </span>
      </div>
    </div>
  </AdminSettingsTabShell>
</template>
