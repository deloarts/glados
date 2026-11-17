<script setup lang="ts">
import { computed, reactive, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import { useAdminSettingsStore } from '../stores/adminSettingsStore'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useSettingsSave } from '../composables/useSettingsSave'
import { extractApiError } from '@/core/utils/errors'
import type { UpdateAuthSettingsCommand } from '../types/adminSettingsTypes'
import AdminSettingsTabShell from './AdminSettingsTabShell.vue'

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const appToast = useAppToast()
const store = useAdminSettingsStore()
const { hasPermission } = usePermissions()

const canWrite = hasPermission(Permission.WRITE_SETTINGS)

interface Form {
  ldap_enabled: boolean
  ldap_host: string
  ldap_port: number
  ldap_use_ssl: boolean
  ldap_start_tls: boolean
  ldap_verify_certificate: boolean
  ldap_domain: string
  ldap_timeout_seconds: number
}

const form = reactive<Form>({
  ldap_enabled: false,
  ldap_host: '',
  ldap_port: 636,
  ldap_use_ssl: true,
  ldap_start_tls: false,
  ldap_verify_certificate: false,
  ldap_domain: '',
  ldap_timeout_seconds: 5,
})

watch(
  () => store.settings?.auth,
  (auth) => {
    if (!auth) return
    form.ldap_enabled = auth.ldap_enabled
    form.ldap_host = auth.ldap_host
    form.ldap_port = auth.ldap_port
    form.ldap_use_ssl = auth.ldap_use_ssl
    form.ldap_start_tls = auth.ldap_start_tls
    form.ldap_verify_certificate = auth.ldap_verify_certificate
    form.ldap_domain = auth.ldap_domain
    form.ldap_timeout_seconds = auth.ldap_timeout_seconds
  },
  { immediate: true },
)

// Implicit TLS and StartTLS are alternatives, not a stack, turning one on
// turns the other off rather than silently producing an invalid combination.
watch(
  () => form.ldap_use_ssl,
  (on) => {
    if (on) form.ldap_start_tls = false
  },
)
watch(
  () => form.ldap_start_tls,
  (on) => {
    if (on) form.ldap_use_ssl = false
  },
)

function buildCommand(): UpdateAuthSettingsCommand {
  return {
    ldap_enabled: form.ldap_enabled,
    ldap_host: form.ldap_host.trim(),
    ldap_port: form.ldap_port,
    ldap_use_ssl: form.ldap_use_ssl,
    ldap_start_tls: form.ldap_start_tls,
    ldap_verify_certificate: form.ldap_verify_certificate,
    ldap_domain: form.ldap_domain.trim(),
    ldap_timeout_seconds: form.ldap_timeout_seconds,
  }
}

const { saving, onSave } = useSettingsSave(() => store.saveAuth(buildCommand()))

// Without a login-attempt limit our lockout never trips, so every guess
// against this endpoint reaches the directory and consumes the account's
// badPwdCount, brute-forcing us would lock real accounts out company-wide.
const lockoutDisabled = computed(
  () => form.ldap_enabled && store.settings?.security.max_login_attempts === 0,
)

// Sending the password in cleartext, or over an unvalidated TLS session,
// hands an on-path attacker real directory credentials.
const insecureTransport = computed(
  () => form.ldap_enabled && !form.ldap_use_ssl && !form.ldap_start_tls,
)
const unvalidatedCertificate = computed(
  () =>
    form.ldap_enabled &&
    (form.ldap_use_ssl || form.ldap_start_tls) &&
    !form.ldap_verify_certificate,
)

const testVisible = ref(false)
const testUsername = ref('')
const testPassword = ref('')
const testing = ref(false)

const canTest = computed(() => canWrite && !!form.ldap_host.trim() && !!form.ldap_domain.trim())

function openTestDialog() {
  testUsername.value = ''
  testPassword.value = ''
  testVisible.value = true
}

async function onTest() {
  testing.value = true
  try {
    await store.verifyLdap({
      ...buildCommand(),
      username: testUsername.value.trim(),
      password: testPassword.value,
    })
    appToast.success(t('adminSettings.auth.testSuccess'))
    testVisible.value = false
  } catch (err: unknown) {
    appToast.error(
      t('adminSettings.auth.testFailed'),
      extractApiError(err) ?? t('adminSettings.errors.unknown'),
    )
  } finally {
    testing.value = false
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
          <Button
            :label="t('adminSettings.auth.testConnection')"
            icon="mdi mdi-lan-connect"
            text
            severity="contrast"
            :disabled="!canTest"
            @click="openTestDialog"
          />
        </template>
      </Toolbar>
    </template>

    <Message v-if="lockoutDisabled" severity="warn" :closable="false" class="auth-warning">
      {{ t('adminSettings.auth.lockoutDisabledWarning') }}
    </Message>
    <Message v-if="insecureTransport" severity="error" :closable="false" class="auth-warning">
      {{ t('adminSettings.auth.insecureTransportWarning') }}
    </Message>
    <Message
      v-else-if="unvalidatedCertificate"
      severity="warn"
      :closable="false"
      class="auth-warning"
    >
      {{ t('adminSettings.auth.unvalidatedCertificateWarning') }}
    </Message>

    <section class="auth-flow">
      <h3 class="auth-flow__heading">{{ t('adminSettings.auth.flow.heading') }}</h3>
      <p class="auth-flow__intro">{{ t('adminSettings.auth.flow.intro') }}</p>
      <ol class="auth-flow__steps">
        <li>{{ t('adminSettings.auth.flow.routing') }}</li>
        <li>{{ t('adminSettings.auth.flow.accepted') }}</li>
        <li>{{ t('adminSettings.auth.flow.rejected') }}</li>
        <li>{{ t('adminSettings.auth.flow.unreachable') }}</li>
      </ol>
      <p class="auth-flow__note">{{ t('adminSettings.auth.flow.systemNote') }}</p>
    </section>

    <div class="settings-fields">
      <div class="field-row field-row--toggle">
        <label :for="`${uid}-ldap-enabled`">
          {{ t('adminSettings.auth.ldapEnabled') }}
          <span class="hint">{{ t('adminSettings.auth.ldapEnabledHint') }}</span>
        </label>
        <ToggleSwitch v-model="form.ldap_enabled" :input-id="`${uid}-ldap-enabled`" :disabled="!canWrite" />
      </div>

      <div class="field-row">
        <label :for="`${uid}-ldap-host`">
          {{ t('adminSettings.auth.ldapHost') }}
          <span class="hint">{{ t('adminSettings.auth.ldapHostHint') }}</span>
        </label>
        <InputText v-model="form.ldap_host" :id="`${uid}-ldap-host`" :disabled="!canWrite" />
      </div>

      <div class="field-row">
        <label :for="`${uid}-ldap-port`">{{ t('adminSettings.auth.ldapPort') }}</label>
        <InputNumber
          v-model="form.ldap_port"
          :input-id="`${uid}-ldap-port`"
          :disabled="!canWrite"
          :min="1"
          :max="65535"
          :use-grouping="false"
        />
      </div>

      <div class="field-row">
        <label :for="`${uid}-ldap-domain`">
          {{ t('adminSettings.auth.ldapDomain') }}
          <span class="hint">{{ t('adminSettings.auth.ldapDomainHint') }}</span>
        </label>
        <InputText v-model="form.ldap_domain" :id="`${uid}-ldap-domain`" :disabled="!canWrite" />
      </div>

      <div class="field-row field-row--toggle">
        <label :for="`${uid}-ldap-use-ssl`">
          {{ t('adminSettings.auth.ldapUseSsl') }}
          <span class="hint">{{ t('adminSettings.auth.ldapUseSslHint') }}</span>
        </label>
        <ToggleSwitch v-model="form.ldap_use_ssl" :input-id="`${uid}-ldap-use-ssl`" :disabled="!canWrite" />
      </div>

      <div class="field-row field-row--toggle">
        <label :for="`${uid}-ldap-start-tls`">
          {{ t('adminSettings.auth.ldapStartTls') }}
          <span class="hint">{{ t('adminSettings.auth.ldapStartTlsHint') }}</span>
        </label>
        <ToggleSwitch v-model="form.ldap_start_tls" :input-id="`${uid}-ldap-start-tls`" :disabled="!canWrite" />
      </div>

      <div class="field-row field-row--toggle">
        <label :for="`${uid}-ldap-verify-certificate`">
          {{ t('adminSettings.auth.ldapVerifyCertificate') }}
          <span class="hint">{{ t('adminSettings.auth.ldapVerifyCertificateHint') }}</span>
        </label>
        <ToggleSwitch
          v-model="form.ldap_verify_certificate"
          :input-id="`${uid}-ldap-verify-certificate`"
          :disabled="!canWrite"
        />
      </div>

      <div class="field-row">
        <label :for="`${uid}-ldap-timeout`">
          {{ t('adminSettings.auth.ldapTimeout') }}
          <span class="hint">{{ t('adminSettings.auth.ldapTimeoutHint') }}</span>
        </label>
        <InputNumber
          v-model="form.ldap_timeout_seconds"
          :input-id="`${uid}-ldap-timeout`"
          :disabled="!canWrite"
          :min="1"
          :max="120"
          :use-grouping="false"
        />
      </div>
    </div>
  </AdminSettingsTabShell>

  <Dialog
    v-model:visible="testVisible"
    :header="t('adminSettings.auth.testDialog.header')"
    modal
    :style="{ width: 'var(--dialog-width-sm)' }"
  >
    <p class="dialog-intro">{{ t('adminSettings.auth.testDialog.intro') }}</p>
    <div class="dialog-field">
      <label :for="`${uid}-username`">{{ t('adminSettings.auth.testDialog.username') }}</label>
      <InputText v-model="testUsername" :id="`${uid}-username`" fluid autofocus autocomplete="off" />
    </div>
    <div class="dialog-field">
      <label :for="`${uid}-password`">{{ t('adminSettings.auth.testDialog.password') }}</label>
      <InputText
        v-model="testPassword"
        :id="`${uid}-password`"
        type="password"
        fluid
        autocomplete="off"
        @keydown.enter="onTest"
      />
    </div>
    <template #footer>
      <Button :label="t('common.cancel')" severity="contrast" text @click="testVisible = false" />
      <Button
        :label="t('adminSettings.auth.testDialog.submit')"
        icon="mdi mdi-lan-connect"
        :loading="testing"
        :disabled="!testUsername.trim() || !testPassword"
        @click="onTest"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.auth-warning {
  margin-bottom: var(--space-4);
}

.auth-flow {
  margin-bottom: var(--space-5);
  padding: var(--space-4) var(--space-4);
  border-left: 3px solid var(--p-primary-color);
  border-radius: var(--p-content-border-radius);
  background: var(--p-content-hover-background);

  &__heading {
    margin: 0 0 var(--space-2);
    font-size: var(--font-size-md);
    font-weight: 600;
  }

  &__intro {
    margin: 0 0 var(--space-3);
    font-size: var(--font-size-sm);
  }

  &__steps {
    margin: 0;
    padding-left: var(--space-4);
    font-size: var(--font-size-sm);
    line-height: 1.6;

    li + li {
      margin-top: var(--space-1);
    }
  }

  &__note {
    margin: var(--space-3) 0 0;
    font-size: var(--font-size-sm);
    opacity: 0.75;
  }
}

.dialog-intro {
  margin: 0 0 var(--space-4);
  font-size: var(--font-size-sm);
  opacity: 0.8;
}

.dialog-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);

  & + .dialog-field {
    margin-top: var(--space-3);
  }
}
</style>
