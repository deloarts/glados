<!--
  The "Connection" block of the SolidWorks PDM settings: the toggle that
  enables the whole PDM integration, the Web API connection fields and a
  read-only status line for the backend's shared PDM session. Each field is
  its own v-model, so the parent tab keeps the form.
-->
<script setup lang="ts">
import { useId } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatISODateTime } from '@/core/utils/dates'
import type { PdmSession } from '../../types/adminSettingsTypes'

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()

defineProps<{
  canWrite: boolean
  passwordConfigured: boolean
  session: PdmSession
}>()

const enabled = defineModel<boolean>('enabled', { required: true })
const baseUrl = defineModel<string>('baseUrl', { required: true })
const vaultName = defineModel<string>('vaultName', { required: true })
const username = defineModel<string>('username', { required: true })
const password = defineModel<string>('password', { required: true })
const verifyCertificate = defineModel<boolean>('verifyCertificate', { required: true })
const timeoutSeconds = defineModel<number>('timeoutSeconds', { required: true })
</script>

<template>
  <div class="pdm-connection-section">
    <p class="section-label">{{ t('adminSettings.solidworksPdm.pdm.connectionSection') }}</p>

    <div class="field-row field-row--toggle">
      <label :for="`${uid}-enabled`">
        {{ t('adminSettings.solidworksPdm.pdm.sync.enabled') }}
        <span class="hint">{{ t('adminSettings.solidworksPdm.pdm.sync.enabledHint') }}</span>
      </label>
      <ToggleSwitch v-model="enabled" :input-id="`${uid}-enabled`" :disabled="!canWrite" />
    </div>

    <div class="field-row">
      <label :for="`${uid}-base-url`">{{ t('adminSettings.solidworksPdm.pdm.baseUrl') }}</label>
      <InputText
        v-model="baseUrl"
        :id="`${uid}-base-url`"
        :placeholder="t('adminSettings.solidworksPdm.pdm.baseUrlPlaceholder')"
        :disabled="!canWrite"
      />
    </div>

    <div class="field-row">
      <label :for="`${uid}-vault-name`">{{ t('adminSettings.solidworksPdm.pdm.vaultName') }}</label>
      <InputText v-model="vaultName" :id="`${uid}-vault-name`" :disabled="!canWrite" />
    </div>

    <div class="field-row">
      <label :for="`${uid}-username`">{{ t('adminSettings.solidworksPdm.pdm.username') }}</label>
      <InputText v-model="username" :id="`${uid}-username`" :disabled="!canWrite" />
    </div>

    <div class="field-row">
      <label :for="`${uid}-password`">{{ t('adminSettings.solidworksPdm.pdm.password') }}</label>
      <InputText
        v-model="password"
        :id="`${uid}-password`"
        type="password"
        :disabled="!canWrite"
        :placeholder="
          passwordConfigured
            ? t('adminSettings.solidworksPdm.pdm.passwordConfigured')
            : t('adminSettings.solidworksPdm.pdm.passwordPlaceholder')
        "
      />
    </div>

    <div class="field-row field-row--toggle">
      <label :for="`${uid}-verify-certificate`">
        {{ t('adminSettings.solidworksPdm.pdm.verifyCertificate') }}
        <span class="hint">{{ t('adminSettings.solidworksPdm.pdm.verifyCertificateHint') }}</span>
      </label>
      <ToggleSwitch v-model="verifyCertificate" :input-id="`${uid}-verify-certificate`" :disabled="!canWrite" />
    </div>

    <div class="field-row">
      <label :for="`${uid}-timeout-seconds`">{{ t('adminSettings.solidworksPdm.pdm.timeoutSeconds') }}</label>
      <InputNumber
        v-model="timeoutSeconds"
        :input-id="`${uid}-timeout-seconds`"
        :min="1"
        :max="300"
        :use-grouping="false"
        :disabled="!canWrite"
      />
    </div>

    <p class="session-status">
      <i
        class="mdi"
        :class="session.active ? 'mdi-check-circle-outline' : 'mdi-circle-off-outline'"
        aria-hidden="true"
      />
      {{
        session.active && session.obtained_at
          ? t('adminSettings.solidworksPdm.pdm.sessionActiveSince', {
              date: formatISODateTime(session.obtained_at),
            })
          : t('adminSettings.solidworksPdm.pdm.sessionNone')
      }}
    </p>
  </div>
</template>

<style scoped lang="scss">
.pdm-connection-section {
  display: contents;
}

.session-status {
  margin: var(--space-1) 0 0;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
