<script setup lang="ts">
import { reactive, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAdminSettingsStore } from '../stores/adminSettingsStore'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useSettingsSave } from '../composables/useSettingsSave'
import AdminSettingsTabShell from './AdminSettingsTabShell.vue'

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const store = useAdminSettingsStore()
const { hasPermission } = usePermissions()

const canWrite = hasPermission(Permission.WRITE_SETTINGS)

interface Form {
  log_retention_days: number
  audit_retention_days: number
  soft_delete_cleanup_days: number
  meeting_retention_days: number
}

const form = reactive<Form>({
  log_retention_days: 90,
  audit_retention_days: 365,
  soft_delete_cleanup_days: 0,
  meeting_retention_days: 0,
})

watch(
  () => store.settings?.retention,
  (r) => {
    if (!r) return
    Object.assign(form, r)
  },
  { immediate: true },
)

const { saving, onSave } = useSettingsSave(() => store.saveRetention({ ...form }))
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
        <label :for="`${uid}-log-retention-days`">{{ t('adminSettings.retention.logRetentionDays') }}</label>
        <InputNumber
          v-model="form.log_retention_days"
          :input-id="`${uid}-log-retention-days`"
          :disabled="!canWrite"
          :min="1"
          :use-grouping="false"
        />
      </div>
      <div class="field-row">
        <label :for="`${uid}-audit-retention-days`">{{ t('adminSettings.retention.auditRetentionDays') }}</label>
        <InputNumber
          v-model="form.audit_retention_days"
          :input-id="`${uid}-audit-retention-days`"
          :disabled="!canWrite"
          :min="1"
          :use-grouping="false"
        />
      </div>
      <div class="field-row">
        <label :for="`${uid}-soft-delete-cleanup-days`">
          {{ t('adminSettings.retention.softDeleteCleanupDays') }}
          <small class="hint">{{ t('adminSettings.security.zeroMeansDisabled') }}</small>
        </label>
        <InputNumber
          v-model="form.soft_delete_cleanup_days"
          :input-id="`${uid}-soft-delete-cleanup-days`"
          :disabled="!canWrite"
          :min="0"
          :use-grouping="false"
        />
      </div>
      <div class="field-row">
        <label :for="`${uid}-meeting-retention-days`">
          {{ t('adminSettings.retention.meetingRetentionDays') }}
          <small class="hint">{{ t('adminSettings.retention.meetingRetentionHint') }}</small>
        </label>
        <InputNumber
          v-model="form.meeting_retention_days"
          :input-id="`${uid}-meeting-retention-days`"
          :disabled="!canWrite"
          :min="0"
          :use-grouping="false"
        />
      </div>
    </div>
  </AdminSettingsTabShell>
</template>
