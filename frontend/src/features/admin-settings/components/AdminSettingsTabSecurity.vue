<script setup lang="ts">
import { reactive, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'

import { useAppToast } from '@/core/composables/useAppToast'

import { useAdminSettingsStore } from '../stores/adminSettingsStore'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { useSettingsSave } from '../composables/useSettingsSave'
import AdminSettingsTabShell from './AdminSettingsTabShell.vue'

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const store = useAdminSettingsStore()
const { hasPermission } = usePermissions()
const confirm = useConfirm()
const appToast = useAppToast()

const canWrite = hasPermission(Permission.WRITE_SETTINGS)
// Without write:settings the tab's controls stay visible but disabled,
// naming the missing permission.
const writeBlocked = useMissingPermission().missing(Permission.WRITE_SETTINGS)

interface Form {
  enforce_totp: boolean
  allow_rfid_login: boolean
  allow_local_login: boolean
  enable_api_key_auth: boolean
  min_password_length: number
  session_timeout_minutes: number
  session_max_lifetime_days: number
  totp_trusted_device_days: number
  max_login_attempts: number
  lockout_duration_minutes: number
  token_max_lifetime_days: number
  enable_terminals: boolean
  terminal_allowed_ips: string[]
  enable_infoscreen_weather: boolean
}

const form = reactive<Form>({
  enforce_totp: false,
  allow_rfid_login: true,
  allow_local_login: true,
  enable_api_key_auth: false,
  min_password_length: 8,
  session_timeout_minutes: 1440,
  session_max_lifetime_days: 30,
  totp_trusted_device_days: 30,
  max_login_attempts: 0,
  lockout_duration_minutes: 15,
  token_max_lifetime_days: 3650,
  enable_terminals: true,
  terminal_allowed_ips: [],
  enable_infoscreen_weather: true,
})

watch(
  () => store.settings?.security,
  (s) => {
    if (!s) return
    Object.assign(form, s)
    // A copy, so adding an address does not change the stored settings before Save.
    form.terminal_allowed_ips = [...(s.terminal_allowed_ips ?? [])]
  },
  { immediate: true },
)

// A light shape check only, as on the maintenance tab: the backend parses
// every entry and answers a 422 for one that is not an address or range.
const IP_OR_CIDR_SHAPE = /^[0-9a-fA-F:./]+$/

const terminalIpInput = ref('')

function addTerminalIp(): void {
  const ip = terminalIpInput.value.trim()
  if (!ip) return
  if (!IP_OR_CIDR_SHAPE.test(ip)) {
    appToast.error(t('adminSettings.security.invalidTerminalIp', { ip }))
    return
  }
  if (!form.terminal_allowed_ips.includes(ip)) form.terminal_allowed_ips.push(ip)
  terminalIpInput.value = ''
}

function removeTerminalIp(ip: string): void {
  form.terminal_allowed_ips = form.terminal_allowed_ips.filter((entry) => entry !== ip)
}

const { saving, onSave } = useSettingsSave(() => store.saveSecurity({ ...form }))

/**
 * Password sign-in is currently the only interactive login method, so
 * switching it off locks every ordinary user out of the application. It is
 * recoverable, since the system user is exempt and the `enable-local-login`
 * CLI command turns it back on, but that is not obvious, hence the
 * confirmation.
 */
function onSaveSecurity() {
  const disablingLocalLogin =
    !form.allow_local_login && store.settings?.security?.allow_local_login !== false

  if (!disablingLocalLogin) {
    void onSave()
    return
  }

  confirm.require({
    header: t('adminSettings.security.disableLocalLoginConfirmHeader'),
    message: t('adminSettings.security.disableLocalLoginConfirm'),
    icon: 'mdi mdi-alert',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('common.save'), severity: 'danger' },
    accept: () => void onSave(),
  })
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
            @click="onSaveSecurity"
          />
        </template>
      </Toolbar>
    </template>

    <div class="settings-fields">
      <p class="section-label">{{ t('adminSettings.security.authenticationSection') }}</p>
      <div class="field-row field-row--toggle">
        <label :for="`${uid}-enforce-topt`">{{ t('adminSettings.security.enforceTopt') }}</label>
        <ToggleSwitch v-model="form.enforce_totp" :input-id="`${uid}-enforce-topt`" :disabled="!canWrite" />
      </div>
      <div class="field-row field-row--toggle">
        <label :for="`${uid}-allow-rfid-login`">{{ t('adminSettings.security.allowRfidLogin') }}</label>
        <ToggleSwitch v-model="form.allow_rfid_login" :input-id="`${uid}-allow-rfid-login`" :disabled="!canWrite" />
      </div>
      <div class="field-row field-row--toggle">
        <label :for="`${uid}-allow-local-login`">{{ t('adminSettings.security.allowLocalLogin') }}</label>
        <ToggleSwitch v-model="form.allow_local_login" :input-id="`${uid}-allow-local-login`" :disabled="!canWrite" />
      </div>
      <div class="field-row field-row--toggle">
        <label :for="`${uid}-enable-api-key-auth`">{{ t('adminSettings.security.enableApiKeyAuth') }}</label>
        <ToggleSwitch
          v-model="form.enable_api_key_auth"
          :input-id="`${uid}-enable-api-key-auth`"
          :disabled="!canWrite"
        />
        <small class="hint">{{ t('adminSettings.security.enableApiKeyAuthHint') }}</small>
      </div>
      <div class="field-row field-row--toggle">
        <label :for="`${uid}-enable-terminals`">{{ t('adminSettings.security.enableTerminals') }}</label>
        <ToggleSwitch
          v-model="form.enable_terminals"
          :input-id="`${uid}-enable-terminals`"
          :disabled="!canWrite"
          data-testid="security-enable-terminals"
        />
        <small class="hint">{{ t('adminSettings.security.enableTerminalsHint') }}</small>
      </div>
      <div class="field-row">
        <label :for="`${uid}-terminal-allowed-ips`">
          {{ t('adminSettings.security.terminalAllowedIps') }}
          <small class="hint">{{ t('adminSettings.security.terminalAllowedIpsHint') }}</small>
        </label>
        <div class="ip-editor">
          <div class="ip-list" data-testid="security-terminal-ips">
            <Tag
              v-for="ip in form.terminal_allowed_ips"
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
                    :aria-label="t('adminSettings.security.removeTerminalIp', { ip })"
                    @click="removeTerminalIp(ip)"
                  />
                </span>
              </template>
            </Tag>
          </div>
          <div class="ip-add-row" v-tooltip.top="writeBlocked || undefined">
            <InputText
              v-model="terminalIpInput"
              :id="`${uid}-terminal-allowed-ips`"
              :disabled="!canWrite"
              :placeholder="t('adminSettings.security.terminalAllowedIpsPlaceholder')"
              :aria-label="t('adminSettings.security.terminalAllowedIps')"
              data-testid="security-terminal-ip-input"
              @keydown.enter.prevent="addTerminalIp"
            />
            <Button
              icon="mdi mdi-plus"
              severity="secondary"
              :disabled="!canWrite"
              :aria-label="t('adminSettings.security.addTerminalIp')"
              data-testid="security-terminal-ip-add"
              @click="addTerminalIp"
            />
          </div>
          <Message severity="info" size="small" :closable="false">
            {{ t('adminSettings.security.terminalAllowedIpsProxyHint') }}
          </Message>
        </div>
      </div>
      <div class="field-row field-row--toggle">
        <label :for="`${uid}-enable-infoscreen-weather`">
          {{ t('adminSettings.security.enableInfoscreenWeather') }}
        </label>
        <ToggleSwitch
          v-model="form.enable_infoscreen_weather"
          :input-id="`${uid}-enable-infoscreen-weather`"
          :disabled="!canWrite"
          data-testid="security-enable-infoscreen-weather"
        />
        <small class="hint">{{ t('adminSettings.security.enableInfoscreenWeatherHint') }}</small>
      </div>

      <Divider />

      <p class="section-label">{{ t('adminSettings.security.policySection') }}</p>
      <div class="field-row">
        <label :for="`${uid}-min-password-length`">{{ t('adminSettings.security.minPasswordLength') }}</label>
        <InputNumber
          v-model="form.min_password_length"
          :input-id="`${uid}-min-password-length`"
          :disabled="!canWrite"
          :min="4"
          :max="128"
          :use-grouping="false"
        />
      </div>
      <div class="field-row">
        <label :for="`${uid}-session-timeout-minutes`">
          {{ t('adminSettings.security.sessionTimeoutMinutes') }}
          <small class="hint">{{ t('adminSettings.security.sessionTimeoutHint') }}</small>
        </label>
        <InputNumber
          v-model="form.session_timeout_minutes"
          :input-id="`${uid}-session-timeout-minutes`"
          :disabled="!canWrite"
          :min="1"
          :use-grouping="false"
        />
      </div>
      <div class="field-row">
        <label :for="`${uid}-session-max-lifetime-days`">
          {{ t('adminSettings.security.sessionMaxLifetimeDays') }}
          <small class="hint">{{ t('adminSettings.security.sessionMaxLifetimeDaysHint') }}</small>
        </label>
        <InputNumber
          v-model="form.session_max_lifetime_days"
          :input-id="`${uid}-session-max-lifetime-days`"
          :disabled="!canWrite"
          :min="1"
          :max="365"
          :use-grouping="false"
        />
      </div>
      <div class="field-row">
        <label :for="`${uid}-totp-trusted-device-days`">
          {{ t('adminSettings.security.totpTrustedDeviceDays') }}
          <small class="hint">{{ t('adminSettings.security.zeroMeansDisabled') }}</small>
        </label>
        <InputNumber
          v-model="form.totp_trusted_device_days"
          :input-id="`${uid}-totp-trusted-device-days`"
          :disabled="!canWrite"
          :min="0"
          :max="365"
          :use-grouping="false"
        />
      </div>
      <div class="field-row">
        <label :for="`${uid}-max-login-attempts`">
          {{ t('adminSettings.security.maxLoginAttempts') }}
          <small class="hint">{{ t('adminSettings.security.maxLoginAttemptsHint') }}</small>
        </label>
        <InputNumber
          v-model="form.max_login_attempts"
          :input-id="`${uid}-max-login-attempts`"
          :disabled="!canWrite"
          :min="0"
          :use-grouping="false"
        />
      </div>
      <div class="field-row">
        <label :for="`${uid}-lockout-duration-minutes`">{{ t('adminSettings.security.lockoutDurationMinutes') }}</label>
        <InputNumber
          v-model="form.lockout_duration_minutes"
          :input-id="`${uid}-lockout-duration-minutes`"
          :disabled="!canWrite"
          :min="1"
          :use-grouping="false"
        />
      </div>
      <div class="field-row">
        <label :for="`${uid}-token-max-lifetime-days`">
          {{ t('adminSettings.security.tokenMaxLifetimeDays') }}
          <small class="hint">{{ t('adminSettings.security.tokenMaxLifetimeDaysHint') }}</small>
        </label>
        <InputNumber
          v-model="form.token_max_lifetime_days"
          :input-id="`${uid}-token-max-lifetime-days`"
          :disabled="!canWrite"
          :min="0"
          :max="36500"
          :use-grouping="false"
        />
      </div>
    </div>
  </AdminSettingsTabShell>
</template>

<style scoped lang="scss">
.ip-editor {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  max-width: 24rem;
}

.ip-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  align-items: center;
}

.ip-tag {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.ip-remove {
  width: 1.5rem;
  height: 1.5rem;
}

.ip-add-row {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}
</style>
