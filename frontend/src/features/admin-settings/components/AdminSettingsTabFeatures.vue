<script setup lang="ts">
import { reactive, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAdminSettingsStore } from '../stores/adminSettingsStore'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useSettingsSave } from '../composables/useSettingsSave'
import AdminSettingsTabShell from './AdminSettingsTabShell.vue'

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const store = useAdminSettingsStore()
const hostStore = useHostStore()
const { hasPermission } = usePermissions()

const canWrite = hasPermission(Permission.WRITE_SETTINGS)

// Every flag here gates something; flags no code reads are not offered.
interface Form {
  enable_production_planning: boolean
  enable_calculations: boolean
  enable_checklists: boolean
  enable_devices: boolean
  enable_sequences: boolean
  enable_todos: boolean
  enable_email_notifications: boolean
  allow_private_webhooks: boolean
}

const form = reactive<Form>({
  enable_production_planning: true,
  enable_calculations: true,
  enable_checklists: true,
  enable_devices: true,
  enable_sequences: true,
  enable_todos: true,
  enable_email_notifications: true,
  allow_private_webhooks: true,
})

// The module switches, in the order they are listed.
const MODULES = [
  { key: 'enable_production_planning', label: 'enableProductionPlanning' },
  { key: 'enable_calculations', label: 'enableCalculations' },
  { key: 'enable_checklists', label: 'enableChecklists' },
  { key: 'enable_devices', label: 'enableDevices' },
  { key: 'enable_sequences', label: 'enableSequences' },
  { key: 'enable_todos', label: 'enableTodos' },
] as const

watch(
  () => store.settings?.features,
  (f) => {
    if (!f) return
    for (const key of Object.keys(form) as (keyof Form)[]) form[key] = f[key]
  },
  { immediate: true },
)

// The host flags are loaded once per session, so the saved switches are
// applied to them here and the admin sees the effect without reloading.
async function save() {
  const saved = await store.saveFeatures({ ...form })
  hostStore.productionPlanningEnabled = saved.enable_production_planning
  hostStore.calculationsEnabled = saved.enable_calculations
  hostStore.checklistsEnabled = saved.enable_checklists
  hostStore.devicesEnabled = saved.enable_devices
  hostStore.sequencesEnabled = saved.enable_sequences && saved.enable_devices
  hostStore.todosEnabled = saved.enable_todos
  return saved
}

const { saving, onSave } = useSettingsSave(save)
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
      <p class="section-label">{{ t('adminSettings.features.modulesSection') }}</p>
      <p class="hint">{{ t('adminSettings.features.modulesHint') }}</p>
      <div
        v-for="module in MODULES"
        :key="module.key"
        class="field-row field-row--toggle"
        :data-testid="`feature-${module.key}`"
      >
        <label :for="`${uid}-key-${module.key}`">{{ t(`adminSettings.features.${module.label}`) }}</label>
        <ToggleSwitch
          v-model="form[module.key]"
          :input-id="`${uid}-key-${module.key}`"
          :disabled="!canWrite || (module.key === 'enable_sequences' && !form.enable_devices)"
        />
        <small class="hint">{{
          module.key === 'enable_sequences' && !form.enable_devices
            ? t('adminSettings.features.enableSequencesNeedsDevices')
            : t(`adminSettings.features.${module.label}Hint`)
        }}</small>
      </div>

      <Divider />

      <p class="section-label">{{ t('adminSettings.features.deliverySection') }}</p>
      <div class="field-row field-row--toggle">
        <label :for="`${uid}-enable-email-notifications`">
          {{ t('adminSettings.features.enableEmailNotifications') }}
        </label>
        <ToggleSwitch
          v-model="form.enable_email_notifications"
          :input-id="`${uid}-enable-email-notifications`"
          :disabled="!canWrite"
        />
        <small class="hint">{{ t('adminSettings.features.enableEmailNotificationsHint') }}</small>
      </div>
      <div class="field-row field-row--toggle">
        <label :for="`${uid}-allow-private-webhooks`">{{ t('adminSettings.features.allowPrivateWebhooks') }}</label>
        <ToggleSwitch
          v-model="form.allow_private_webhooks"
          :input-id="`${uid}-allow-private-webhooks`"
          :disabled="!canWrite"
        />
        <small class="hint">{{ t('adminSettings.features.allowPrivateWebhooksHint') }}</small>
      </div>
    </div>
  </AdminSettingsTabShell>
</template>
