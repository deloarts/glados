<script setup lang="ts">
import { reactive, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import { useAdminSettingsStore } from '../stores/adminSettingsStore'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { useHostStore } from '@/core/host/stores/hostStore'
import { apiErrorStatus, extractApiError } from '@/core/utils/errors'
import AdminSettingsTabShell from './AdminSettingsTabShell.vue'

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const appToast = useAppToast()
const store = useAdminSettingsStore()
const hostStore = useHostStore()
const { hasPermission } = usePermissions()

const canWrite = hasPermission(Permission.WRITE_SETTINGS)
// Without write:settings the tab's controls stay visible but disabled,
// naming the missing permission.
const writeBlocked = useMissingPermission().missing(Permission.WRITE_SETTINGS)

interface Form {
  enabled: boolean
  message: string
  allowed_ips: string[]
  ip_input: string
}

const form = reactive<Form>({
  enabled: false,
  message: '',
  allowed_ips: [],
  ip_input: '',
})

watch(
  () => store.settings?.maintenance,
  (m) => {
    if (!m) return
    form.enabled = m.enabled
    form.message = m.message ?? ''
    form.allowed_ips = [...m.allowed_ips]
  },
  { immediate: true },
)

// A light client-side sanity check only: no spaces, and nothing outside
// what an IPv4/IPv6 address or a CIDR range could ever contain. The real
// validator is the backend's normalise_allowed_ips (parses every entry via
// the stdlib ipaddress module), whose 422 is surfaced from onSave() below.
const IP_OR_CIDR_SHAPE = /^[0-9a-fA-F:./]+$/

function addIp() {
  const ip = form.ip_input.trim()
  if (!ip) return

  if (!IP_OR_CIDR_SHAPE.test(ip)) {
    appToast.error(t('adminSettings.maintenance.invalidIp', { ip }))
    return
  }

  if (!form.allowed_ips.includes(ip)) {
    form.allowed_ips.push(ip)
  }
  form.ip_input = ''
}

function removeIp(ip: string) {
  form.allowed_ips = form.allowed_ips.filter((i) => i !== ip)
}

// Not useSettingsSave: that composable's catch is a single generic
// "something went wrong" toast, but a 422 here is the backend's own
// allowed_ips/message validation rejecting something the light client-side
// check in addIp() let through (e.g. a message over 500 characters, which
// nothing here stops you from typing), so it's worth surfacing its actual
// reason rather than papering over it with the generic message.
const saving = ref(false)

async function onSave() {
  saving.value = true
  try {
    const result = await store.saveMaintenance({
      enabled: form.enabled,
      message: form.message.trim() || null,
      allowed_ips: form.allowed_ips,
    })
    // hostStore.fetch() early-returns once loaded, and 'host' is excluded
    // from the logout reset, so without this an admin who flips the toggle
    // would see no change in the in-app banner until a hard reload, the same
    // reasoning as the General tab's hostStore.officeLauncherEnabled lines.
    hostStore.maintenanceEnabled = result.enabled
    hostStore.maintenanceMessage = result.message
    appToast.success(t('adminSettings.saved'))
  } catch (err) {
    if (apiErrorStatus(err) === 422) {
      appToast.error(extractApiError(err) ?? t('adminSettings.errors.unknown'))
    } else {
      appToast.error(t('adminSettings.errors.unknown'))
    }
  } finally {
    saving.value = false
  }
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
            :disabled="!canWrite"
            @click="onSave"
          />
        </template>
      </Toolbar>
    </template>

    <div class="settings-fields">
      <div class="field-row field-row--toggle">
        <label :for="`${uid}-enabled`">{{ t('adminSettings.maintenance.enabled') }}</label>
        <ToggleSwitch v-model="form.enabled" :input-id="`${uid}-enabled`" :disabled="!canWrite" />
        <small class="hint">{{ t('adminSettings.maintenance.enabledHint') }}</small>
      </div>
      <div class="field-row">
        <label :for="`${uid}-message`">{{ t('adminSettings.maintenance.message') }}</label>
        <Textarea v-model="form.message" :id="`${uid}-message`" :disabled="!canWrite" rows="3" auto-resize />
      </div>
      <div class="field-row">
        <label :for="`${uid}-allowed-ips`">{{ t('adminSettings.maintenance.allowedIps') }}</label>
        <div class="ip-list">
          <Tag
            v-for="ip in form.allowed_ips"
            :key="ip"
            :value="ip"
            severity="secondary"
            class="ip-tag"
          >
            <template #default>
              {{ ip }}
              <span v-tooltip.top="writeBlocked || undefined">
                <Button
                  icon="mdi mdi-close"
                  text
                  rounded
                  size="small"
                  class="ip-remove"
                  :disabled="!canWrite"
                  :aria-label="t('adminSettings.maintenance.removeIp', { ip })"
                  @click="removeIp(ip)"
                />
              </span>
            </template>
          </Tag>
          <div class="ip-add-row" v-tooltip.top="writeBlocked || undefined">
            <InputText
              v-model="form.ip_input"
              :id="`${uid}-allowed-ips`"
              :disabled="!canWrite"
              :placeholder="t('adminSettings.maintenance.allowedIpsPlaceholder')"
              @keydown.enter.prevent="addIp"
            />
            <Button
              icon="mdi mdi-plus"
              severity="secondary"
              :disabled="!canWrite"
              :aria-label="t('adminSettings.maintenance.addIp')"
              @click="addIp"
            />
          </div>
        </div>
        <small class="hint">{{ t('adminSettings.maintenance.allowedIpsHint') }}</small>
      </div>
    </div>
  </AdminSettingsTabShell>
</template>

<style scoped lang="scss">
.ip-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
}

.ip-tag {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
}

.ip-remove {
  width: 1.5rem;
  height: 1.5rem;
  opacity: 0.7;

  &:hover {
    opacity: 1;
  }
}

.ip-add-row {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}
</style>
