<script setup lang="ts">
import { computed, reactive, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import { useAdminSettingsStore } from '../stores/adminSettingsStore'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { apiErrorStatus, extractApiError } from '@/core/utils/errors'
import { getPickerDateFormat, instantToPickerDate, pickerDateToInstant } from '@/core/utils/dates'
import type { AnnouncementSeverity } from '../types/adminSettingsTypes'
import AdminSettingsTabShell from './AdminSettingsTabShell.vue'
import WebhookSubscriptionsPanel from './WebhookSubscriptionsPanel.vue'
import AcknowledgementsPanel from './AcknowledgementsPanel.vue'

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const appToast = useAppToast()
const store = useAdminSettingsStore()
const { hasPermission } = usePermissions()

const canWrite = hasPermission(Permission.WRITE_SETTINGS)

const webhooksPanel = ref<InstanceType<typeof WebhookSubscriptionsPanel> | null>(null)
const acknowledgementsPanel = ref<InstanceType<typeof AcknowledgementsPanel> | null>(null)

interface Form {
  webhook_timeout_seconds: number
}

const form = reactive<Form>({
  webhook_timeout_seconds: 10,
})

watch(
  () => store.settings?.notifications,
  (n) => {
    if (!n) return
    form.webhook_timeout_seconds = n.webhook_timeout_seconds
  },
  { immediate: true },
)

interface BannerForm {
  enabled: boolean
  text: string
  severity: AnnouncementSeverity
  shows_from: Date | null
  shows_until: Date | null
  dismissable: boolean
}

const bannerForm = reactive<BannerForm>({
  enabled: false,
  text: '',
  severity: 'info',
  shows_from: null,
  shows_until: null,
  dismissable: true,
})

watch(
  () => store.settings?.banner,
  (b) => {
    if (!b) return
    bannerForm.enabled = b.enabled
    bannerForm.text = b.text
    bannerForm.severity = b.severity
    // shows_from/shows_until are UTC instants (see the "two kinds of value"
    // comment in core/utils/dates.ts), never calendar dates for dateToParam.
    // The pickers show them on the tenant's wall clock.
    bannerForm.shows_from = b.shows_from ? instantToPickerDate(b.shows_from) : null
    bannerForm.shows_until = b.shows_until ? instantToPickerDate(b.shows_until) : null
    bannerForm.dismissable = b.dismissable
  },
  { immediate: true },
)

const bannerSeverityOptions = computed(() => [
  { value: 'info' as const, label: t('adminSettings.notifications.severities.info') },
  { value: 'warning' as const, label: t('adminSettings.notifications.severities.warning') },
  { value: 'danger' as const, label: t('adminSettings.notifications.severities.danger') },
])

const bannerWindowInvalid = computed(() => {
  if (!bannerForm.shows_from || !bannerForm.shows_until) return false
  return bannerForm.shows_until.getTime() < bannerForm.shows_from.getTime()
})

// Not useSettingsSave: a banner 422 (blank text while enabled, or a window
// the client-side check below didn't already block) needs its own toast
// distinct from "webhook settings saved, banner didn't", the same local-onSave
// reasoning as the Maintenance tab's own 422-detail handling.
const saving = ref(false)

async function onSave(): Promise<void> {
  saving.value = true

  try {
    await store.saveNotifications({
      webhook_timeout_seconds: form.webhook_timeout_seconds,
    })
  } catch {
    appToast.error(t('adminSettings.errors.unknown'))
    saving.value = false
    return
  }

  try {
    await store.saveBanner({
      enabled: bannerForm.enabled,
      text: bannerForm.text.trim(),
      severity: bannerForm.severity,
      shows_from: bannerForm.shows_from
        ? pickerDateToInstant(bannerForm.shows_from).toISOString()
        : null,
      shows_until: bannerForm.shows_until
        ? pickerDateToInstant(bannerForm.shows_until).toISOString()
        : null,
      dismissable: bannerForm.dismissable,
    })
  } catch (err) {
    if (apiErrorStatus(err) === 422) {
      appToast.error(
        t('adminSettings.notifications.banner.saveFailed'),
        extractApiError(err) ?? t('adminSettings.errors.unknown'),
      )
    } else {
      appToast.error(t('adminSettings.notifications.banner.saveFailed'))
    }
    saving.value = false
    return
  }

  appToast.success(t('adminSettings.saved'))
  saving.value = false
}
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
            :disabled="!canWrite || bannerWindowInvalid"
            @click="onSave"
          />

          <Divider layout="vertical" />

          <Button
            :label="t('adminSettings.notifications.webhooks.add')"
            icon="mdi mdi-plus"
            text
            severity="contrast"
            :disabled="!canWrite"
            @click="webhooksPanel?.openCreate()"
          />

          <Button
            :label="t('adminSettings.notifications.acknowledgements.new')"
            icon="mdi mdi-plus"
            text
            severity="contrast"
            :disabled="!canWrite"
            @click="acknowledgementsPanel?.openCreate()"
          />
        </template>
      </Toolbar>
    </template>

    <div class="settings-fields">
      <p class="section-label">{{ t('adminSettings.notifications.webhooks.section') }}</p>
      <div class="field-row">
        <label :for="`${uid}-timeout-seconds`">
          {{ t('adminSettings.notifications.webhooks.timeoutSeconds') }}
          <small class="hint">{{ t('adminSettings.notifications.webhooks.timeoutSecondsHint') }}</small>
        </label>
        <InputNumber
          v-model="form.webhook_timeout_seconds"
          :input-id="`${uid}-timeout-seconds`"
          :disabled="!canWrite"
          :min="1"
          :max="120"
          :use-grouping="false"
        />
      </div>
      <WebhookSubscriptionsPanel ref="webhooksPanel" :can-write="canWrite" />

      <Divider />

      <p class="section-label">{{ t('adminSettings.notifications.banner.section') }}</p>
      <p class="section-hint">{{ t('adminSettings.notifications.banner.description') }}</p>
      <div class="field-row field-row--toggle">
        <label :for="`${uid}-enabled`">{{ t('adminSettings.notifications.banner.enabled') }}</label>
        <ToggleSwitch v-model="bannerForm.enabled" :input-id="`${uid}-enabled`" :disabled="!canWrite" />
      </div>
      <div class="field-row field-row--toggle">
        <label :for="`${uid}-dismissable`">{{ t('adminSettings.notifications.banner.dismissable') }}</label>
        <ToggleSwitch v-model="bannerForm.dismissable" :input-id="`${uid}-dismissable`" :disabled="!canWrite" />
        <small class="hint">{{ t('adminSettings.notifications.banner.dismissableHint') }}</small>
      </div>
      <div class="field-row">
        <label :for="`${uid}-text`">{{ t('adminSettings.notifications.banner.text') }}</label>
        <Textarea v-model="bannerForm.text" :id="`${uid}-text`" :disabled="!canWrite" rows="2" auto-resize />
      </div>
      <div class="field-row">
        <!-- eslint-disable-next-line vuejs-accessibility/label-has-for -- captions the group below, which names it through aria-labelledby -->
        <label :id="`${uid}-banner-severity`">{{ t('adminSettings.notifications.banner.severity') }}</label>
        <div role="group" :aria-labelledby="`${uid}-banner-severity`" class="severity-options">
          <div
            v-for="option in bannerSeverityOptions"
            :key="option.value"
            class="severity-option"
          >
            <RadioButton
              v-model="bannerForm.severity"
              :input-id="`banner-severity-${option.value}`"
              :value="option.value"
              name="banner-severity"
              :disabled="!canWrite"
            />
            <label :for="`banner-severity-${option.value}`">{{ option.label }}</label>
          </div>
        </div>
      </div>
      <div class="field-row">
        <label :for="`${uid}-shows-from`">{{ t('adminSettings.notifications.banner.showsFrom') }}</label>
        <DatePicker
          v-model="bannerForm.shows_from"
          :input-id="`${uid}-shows-from`"
          show-time
          hour-format="24"
          :date-format="getPickerDateFormat()"
          show-clear
          :disabled="!canWrite"
          fluid
        />
      </div>
      <div class="field-row">
        <label :for="`${uid}-shows-until`">{{ t('adminSettings.notifications.banner.showsUntil') }}</label>
        <DatePicker
          v-model="bannerForm.shows_until"
          :input-id="`${uid}-shows-until`"
          show-time
          hour-format="24"
          :date-format="getPickerDateFormat()"
          show-clear
          :disabled="!canWrite"
          fluid
        />
      </div>
      <Message v-if="bannerWindowInvalid" severity="error" :closable="false">
        {{ t('adminSettings.notifications.banner.windowInvalid') }}
      </Message>

      <Divider />

      <p class="section-label">{{ t('adminSettings.notifications.acknowledgements.section') }}</p>
      <AcknowledgementsPanel ref="acknowledgementsPanel" :can-write="canWrite" />
    </div>
  </AdminSettingsTabShell>
</template>

<style scoped lang="scss">
.section-hint {
  margin: -0.25rem 0 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.severity-options {
  display: flex;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.severity-option {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}
</style>
