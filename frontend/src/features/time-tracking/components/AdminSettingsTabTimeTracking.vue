<script setup lang="ts">
// The time tracking tab: the time tracking service every user's own time
// tracking calls go through, the API key Glados calls it with, and the
// credential key users' credentials are sealed for. Glados never talks to
// the time tracking system itself. The API key is write-only: an empty
// field keeps the stored one. A connection test shows what the service
// reports, and its credential key is confirmed in a separate step from the
// toolbar, which only works for the saved service and a tested key. The tab also lists who stored
// credentials and purges them. The settings are loaded here, not with the
// aggregate, because they carry that list.
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'
import { storeToRefs } from 'pinia'

import { useAppToast } from '@/core/composables/useAppToast'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { formatISODateTime } from '@/core/utils/dates'
import { AdminSettingsTabShell, useAdminSettingsStore } from '@/features/admin-settings'
import type {
  AdminTimeTrackingSettings,
  TimeTrackingCredentialHolder,
  TimeTrackingServiceTestResult,
} from '@/features/admin-settings'
import EmptyState from '@/shared/components/EmptyState.vue'
import { timeTrackingErrorMessage } from '../utils/timeTrackingErrors'

const { t } = useI18n()
const toast = useAppToast()
const confirm = useConfirm()
const store = useAdminSettingsStore()
const hostStore = useHostStore()
const { hasPermission } = usePermissions()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const canWrite = hasPermission(Permission.WRITE_SETTINGS)

const form = reactive({
  enabled: false,
  service_url: '',
  api_key: '',
  privacy_policy_url: '',
})

const settings = computed<AdminTimeTrackingSettings | null>(() => store.timeTracking)

watch(
  settings,
  (value) => {
    if (!value) return
    form.enabled = value.enabled
    form.service_url = value.service_url
    form.api_key = ''
    form.privacy_policy_url = value.privacy_policy_url ?? ''
  },
  { immediate: true },
)

onMounted(() => {
  void store.fetchTimeTracking()
})

const isDirty = computed(() => {
  const value = settings.value
  if (!value) return false
  return (
    form.enabled !== value.enabled ||
    form.service_url.trim() !== value.service_url ||
    form.api_key !== '' ||
    form.privacy_policy_url.trim() !== (value.privacy_policy_url ?? '')
  )
})

const holders = computed<TimeTrackingCredentialHolder[]>(() => settings.value?.credential_holders ?? [])
const awaitingKey = computed(
  () => !!settings.value?.enabled && !!settings.value.is_configured && !settings.value.is_ready,
)

function unknownError(): string {
  return t('adminSettings.errors.unknown')
}

// The capabilities are read once per app load; mirror the new state so the
// time tracking surfaces follow without a reload.
function mirrorCapabilities(result: AdminTimeTrackingSettings): void {
  hostStore.timeTrackingEnabled = result.is_ready
  hostStore.timeTrackingProviderLabel = result.is_ready ? result.provider_label : null
}

// ── Save ────────────────────────────────────────────────────────────────

const saving = ref(false)

async function onSave(): Promise<void> {
  saving.value = true
  try {
    const result = await store.saveTimeTracking({
      enabled: form.enabled,
      service_url: form.service_url.trim(),
      ...(form.api_key ? { api_key: form.api_key } : {}),
      privacy_policy_url: form.privacy_policy_url.trim(),
    })
    mirrorCapabilities(result)
    toast.success(t('adminSettings.saved'))
  } catch (err: unknown) {
    toast.error(unknownError(), timeTrackingErrorMessage(err, t, unknownError()))
  } finally {
    form.api_key = ''
    saving.value = false
  }
}

// ── Test connection and confirm the key ────────────────────────────────

const testing = ref(false)
const confirmingKey = ref(false)
const testResult = ref<TimeTrackingServiceTestResult | null>(null)

const canTest = computed(
  () =>
    canWrite && !!form.service_url.trim() && (!!form.api_key || !!settings.value?.api_key_configured),
)
const canConfirmKey = computed(
  () => canWrite && !isDirty.value && !!testResult.value && !testResult.value.key_confirmed,
)

async function onTest(): Promise<void> {
  testing.value = true
  testResult.value = null
  try {
    testResult.value = await store.testTimeTrackingService({
      service_url: form.service_url.trim() || null,
      ...(form.api_key ? { api_key: form.api_key } : {}),
    })
    toast.success(t('adminSettings.timeTracking.testSuccess'))
  } catch (err: unknown) {
    toast.error(
      t('adminSettings.timeTracking.testFailed'),
      timeTrackingErrorMessage(err, t, unknownError()),
    )
  } finally {
    testing.value = false
  }
}

async function onConfirmKey(): Promise<void> {
  const result = testResult.value
  if (!result) return
  confirmingKey.value = true
  try {
    const saved = await store.confirmTimeTrackingKey({
      credential_key_id: result.credential_key_id,
    })
    testResult.value = { ...result, key_confirmed: true }
    mirrorCapabilities(saved)
    toast.success(t('adminSettings.timeTracking.keyConfirmed'))
  } catch (err: unknown) {
    testResult.value = null
    toast.error(
      t('adminSettings.timeTracking.keyConfirmFailed'),
      timeTrackingErrorMessage(err, t, unknownError()),
    )
  } finally {
    confirmingKey.value = false
  }
}

// ── Purge ───────────────────────────────────────────────────────────────

const purging = ref(false)

function onPurge(): void {
  async function onAccept(): Promise<void> {
    purging.value = true
    try {
      const result = await store.purgeTimeTrackingCredentials()
      toast.success(t('adminSettings.timeTracking.purged', { count: result.deleted }, result.deleted))
    } catch (err: unknown) {
      toast.error(
        t('adminSettings.timeTracking.purgeFailed'),
        timeTrackingErrorMessage(err, t, unknownError()),
      )
    } finally {
      purging.value = false
    }
  }

  confirm.require({
    group: 'time-tracking-purge',
    header: t('adminSettings.timeTracking.purgeConfirmHeader'),
    message: t('adminSettings.timeTracking.purgeConfirmMessage'),
    icon: 'mdi mdi-alert',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('adminSettings.timeTracking.purge'), severity: 'danger' },
    accept: () => void onAccept(),
  })
}

function holderState(holder: TimeTrackingCredentialHolder): string {
  if (holder.credentials_valid) return t('adminSettings.timeTracking.holderValid')
  return t(`adminSettings.timeTracking.reasons.${holder.credentials_invalid_reason ?? 'missing'}`)
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
            data-testid="time-tracking-save"
            @click="onSave"
          />
          <Button
            :label="t('adminSettings.timeTracking.testConnection')"
            icon="mdi mdi-lan-connect"
            text
            severity="contrast"
            :loading="testing"
            :disabled="!canTest"
            data-testid="time-tracking-test"
            @click="onTest"
          />
          <Button
            :label="t('adminSettings.timeTracking.confirmKey')"
            icon="mdi mdi-key-chain-variant"
            text
            severity="contrast"
            :loading="confirmingKey"
            :disabled="!canConfirmKey"
            data-testid="time-tracking-confirm-key"
            @click="onConfirmKey"
          />
        </template>
      </Toolbar>
    </template>

    <div class="settings-fields">
      <p class="section-label">{{ t('adminSettings.timeTracking.serviceSection') }}</p>

      <Message
        v-if="awaitingKey"
        severity="warn"
        :closable="false"
        data-testid="time-tracking-awaiting-key"
      >
        {{ t('adminSettings.timeTracking.awaitingKey') }}
      </Message>

      <div class="field-row field-row--toggle">
        <label for="time-tracking-enabled">
          {{ t('adminSettings.timeTracking.enabled') }}
          <span class="hint">{{ t('adminSettings.timeTracking.enabledHint') }}</span>
        </label>
        <ToggleSwitch v-model="form.enabled" input-id="time-tracking-enabled" :disabled="!canWrite" />
      </div>

      <div class="field-row">
        <label for="time-tracking-service-url">
          {{ t('adminSettings.timeTracking.serviceUrl') }}
          <span class="hint">{{ t('adminSettings.timeTracking.serviceUrlHint') }}</span>
        </label>
        <InputText
          id="time-tracking-service-url"
          v-model="form.service_url"
          :placeholder="t('adminSettings.timeTracking.serviceUrlPlaceholder')"
          :disabled="!canWrite"
          autocomplete="off"
        />
      </div>

      <div class="field-row">
        <label for="time-tracking-api-key">
          {{ t('adminSettings.timeTracking.apiKey') }}
          <span class="hint">{{ t('adminSettings.timeTracking.apiKeyHint') }}</span>
        </label>
        <InputText
          id="time-tracking-api-key"
          v-model="form.api_key"
          type="password"
          autocomplete="new-password"
          :placeholder="
            settings?.api_key_configured ? t('adminSettings.timeTracking.apiKeySaved') : ''
          "
          :disabled="!canWrite"
        />
      </div>

      <div class="field-row">
        <label for="time-tracking-privacy-url">
          {{ t('adminSettings.timeTracking.privacyPolicyUrl') }}
          <span class="hint">{{ t('adminSettings.timeTracking.privacyPolicyUrlHint') }}</span>
        </label>
        <InputText
          id="time-tracking-privacy-url"
          v-model="form.privacy_policy_url"
          placeholder="https://"
          :disabled="!canWrite"
          autocomplete="off"
        />
      </div>

      <div class="field-row">
        <span class="field-caption">{{ t('adminSettings.timeTracking.credentialKey') }}</span>
        <span data-testid="time-tracking-confirmed-key">
          <template v-if="settings?.credential_key_id">
            <code>{{ settings.credential_key_id }}</code>
            <span v-if="settings.provider_label" class="hint">
              ({{ settings.provider_label }})
            </span>
          </template>
          <span v-else class="hint">{{ t('adminSettings.timeTracking.noConfirmedKey') }}</span>
        </span>
      </div>

      <template v-if="testResult">
        <Divider />
        <p class="section-label">{{ t('adminSettings.timeTracking.testSection') }}</p>
        <dl class="test-result" data-testid="time-tracking-test-result">
          <dt>{{ t('adminSettings.timeTracking.testService') }}</dt>
          <dd>{{ testResult.service }} {{ testResult.service_version }}</dd>
          <dt>{{ t('adminSettings.timeTracking.testProvider') }}</dt>
          <dd>{{ testResult.provider_label }} {{ testResult.server_version }}</dd>
          <dt>{{ t('adminSettings.timeTracking.testDefaultProject') }}</dt>
          <dd>{{ testResult.default_project }}</dd>
          <dt>{{ t('adminSettings.timeTracking.testContract') }}</dt>
          <dd>{{ testResult.contract_version }}</dd>
          <dt>{{ t('adminSettings.timeTracking.credentialKey') }}</dt>
          <dd><code>{{ testResult.credential_key_id }}</code></dd>
        </dl>
        <Message
          v-if="!testResult.contract_supported"
          severity="warn"
          :closable="false"
          data-testid="time-tracking-contract-unsupported"
        >
          {{ t('adminSettings.timeTracking.contractUnsupported') }}
        </Message>
        <Message
          v-if="!testResult.credential_fields_supported"
          severity="warn"
          :closable="false"
          data-testid="time-tracking-fields-unsupported"
        >
          {{ t('adminSettings.timeTracking.fieldsUnsupported') }}
        </Message>
        <Message
          v-if="testResult.key_confirmed"
          severity="success"
          :closable="false"
          data-testid="time-tracking-key-is-confirmed"
        >
          {{ t('adminSettings.timeTracking.keyIsConfirmed') }}
        </Message>
        <p v-else class="hint" data-testid="time-tracking-confirm-key-hint">
          {{
            isDirty
              ? t('adminSettings.timeTracking.confirmKeySaveFirst')
              : t('adminSettings.timeTracking.confirmKeyHint')
          }}
        </p>
      </template>

      <Divider />

      <p class="section-label">{{ t('adminSettings.timeTracking.credentialsSection') }}</p>
      <p class="hint">{{ t('adminSettings.timeTracking.credentialsHint') }}</p>
      <DataTable
        :value="holders"
        size="small"
        :show-gridlines="isTableGridlinesEnabled"
        :striped-rows="isTableStripedEnabled"
        data-testid="time-tracking-holders"
      >
        <template #empty>
          <EmptyState :message="t('adminSettings.timeTracking.noHolders')" />
        </template>
        <Column field="username" :header="t('adminSettings.timeTracking.holderUser')" />
        <Column field="full_name" :header="t('adminSettings.timeTracking.holderName')" />
        <Column :header="t('adminSettings.timeTracking.holderSaved')">
          <template #body="{ data }: { data: TimeTrackingCredentialHolder }">
            {{ formatISODateTime(data.saved_at) }}
          </template>
        </Column>
        <Column :header="t('adminSettings.timeTracking.holderState')">
          <template #body="{ data }: { data: TimeTrackingCredentialHolder }">
            <Tag
              :value="holderState(data)"
              :severity="data.credentials_valid ? 'success' : 'warn'"
            />
          </template>
        </Column>
      </DataTable>
      <div class="purge">
        <Button
          :label="t('adminSettings.timeTracking.purge')"
          icon="mdi mdi-delete-sweep-outline"
          severity="danger"
          outlined
          size="small"
          :loading="purging"
          :disabled="!canWrite || holders.length === 0"
          data-testid="time-tracking-purge"
          @click="onPurge"
        />
      </div>
    </div>
    <ConfirmDialog group="time-tracking-purge" />
  </AdminSettingsTabShell>
</template>

<style scoped lang="scss">
p.hint {
  margin: 0;
}

.test-result {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: var(--space-1) var(--space-4);
  margin: 0;
  font-size: var(--font-size-sm);

  dt {
    color: var(--p-text-muted-color);
  }

  dd {
    margin: 0;
  }
}

.purge {
  display: flex;
  justify-content: flex-start;
}
</style>
