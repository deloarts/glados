<script setup lang="ts">
import { computed, onMounted, reactive, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import { useAdminSettingsStore } from '../stores/adminSettingsStore'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useSettingsSave } from '../composables/useSettingsSave'
import { useStorageMigration } from '../composables/useStorageMigration'
import { extractApiError } from '@/core/utils/errors'
import { SseHttpError } from '@/core/realtime/sseClient'
import type { StorageProvider } from '../types/adminSettingsTypes'
import AdminSettingsTabShell from './AdminSettingsTabShell.vue'

const { t, te } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const appToast = useAppToast()
const store = useAdminSettingsStore()
const { hasPermission } = usePermissions()

const canWrite = hasPermission(Permission.WRITE_SETTINGS)

// The other providers are product names and stay as they are in every language.
const providerOptions = computed<{ label: string; value: StorageProvider }[]>(() => [
  { label: t('adminSettings.storage.providerLocal'), value: 'local' },
  { label: 'SeaweedFS', value: 'seaweedfs' },
  { label: 'Amazon S3', value: 's3' },
  { label: 'Azure Blob', value: 'azure' },
])

const PROVIDER_DISABLED_FIELDS: Record<StorageProvider, string[]> = {
  local: [
    'endpoint_url',
    'public_endpoint_url',
    'bucket_name',
    'access_key',
    'secret_key',
    'region',
    'use_ssl',
  ],
  seaweedfs: [],
  s3: [],
  azure: ['public_endpoint_url', 'region', 'use_ssl'],
}

// The bundled seaweedfs compose service creates this bucket, and the frontend
// container serves presigned file URLs only for it, under /objects/.
const SEAWEEDFS_DEFAULTS = { endpoint_url: 'http://seaweedfs:8333', bucket_name: 'objects' }

function selectProvider(provider: StorageProvider) {
  form.provider = provider
  // The endpoint and bucket still hold the previous provider's values, which
  // never fit SeaweedFS, so they are replaced with the bundled service's.
  if (provider === 'seaweedfs' && store.settings?.storage?.provider !== 'seaweedfs') {
    form.endpoint_url = SEAWEEDFS_DEFAULTS.endpoint_url
    form.bucket_name = SEAWEEDFS_DEFAULTS.bucket_name
  }
}

function isFieldDisabled(field: string): boolean {
  if (!canWrite) return true
  return PROVIDER_DISABLED_FIELDS[form.provider].includes(field)
}

function dynamicLabel(field: 'endpointUrl' | 'bucketName' | 'accessKey' | 'secretKey'): string {
  return t(`adminSettings.storage.labels.${field}.${form.provider}`)
}

function fieldHint(field: string): string {
  const providerKey = `adminSettings.storage.hints.${field}.${form.provider}`
  if (te(providerKey)) return t(providerKey)
  const genericKey = `adminSettings.storage.hints.${field}`
  if (te(genericKey)) return t(genericKey)
  return ''
}

interface Form {
  provider: StorageProvider
  enabled: boolean
  endpoint_url: string
  public_endpoint_url: string
  bucket_name: string
  access_key: string
  secret_key: string
  secret_key_configured: boolean
  region: string
  use_ssl: boolean
  backup_enabled: boolean
  backup_path: string
  backup_cron: string
  backup_retention_count: number
  disk_warning_percent: number
}

const form = reactive<Form>({
  provider: 'local',
  enabled: false,
  endpoint_url: '',
  public_endpoint_url: '',
  bucket_name: '',
  access_key: '',
  secret_key: '',
  secret_key_configured: false,
  region: '',
  use_ssl: true,
  backup_enabled: false,
  backup_path: '',
  backup_cron: '',
  backup_retention_count: 7,
  // Mirrors the backend's server_default; this form briefly renders it
  // before store.settings hydrates it via the watch below.
  disk_warning_percent: 90,
})

watch(
  () => store.settings?.storage,
  (s) => {
    if (!s) return
    form.provider = s.provider
    form.enabled = s.enabled
    form.endpoint_url = s.endpoint_url ?? ''
    form.public_endpoint_url = s.public_endpoint_url ?? ''
    form.bucket_name = s.bucket_name ?? ''
    form.access_key = s.access_key ?? ''
    form.secret_key = ''
    form.secret_key_configured = s.secret_key_configured
    form.region = s.region ?? ''
    form.use_ssl = s.use_ssl
    form.backup_enabled = s.backup_enabled
    form.backup_path = s.backup_path ?? ''
    form.backup_cron = s.backup_cron ?? ''
    form.backup_retention_count = s.backup_retention_count
    form.disk_warning_percent = s.disk_warning_percent
  },
  { immediate: true },
)

function buildCommand() {
  return {
    provider: form.provider,
    enabled: form.enabled,
    endpoint_url: form.endpoint_url.trim() || null,
    public_endpoint_url: form.public_endpoint_url.trim() || null,
    bucket_name: form.bucket_name.trim() || null,
    access_key: form.access_key.trim() || null,
    secret_key: form.secret_key.trim() || null,
    region: form.region.trim() || null,
    use_ssl: form.use_ssl,
    backup_enabled: form.backup_enabled,
    backup_path: form.backup_path.trim() || null,
    backup_cron: form.backup_cron.trim() || null,
    backup_retention_count: form.backup_retention_count,
    disk_warning_percent: form.disk_warning_percent,
  }
}

const providerChanged = computed(
  () => !!store.settings?.storage && form.provider !== store.settings.storage.provider,
)

const { saving, onSave } = useSettingsSave(() => store.saveStorage(buildCommand()))

const testing = ref(false)

async function onTest() {
  testing.value = true
  try {
    await store.testStorage(buildCommand())
    appToast.success(t('adminSettings.storage.testSuccess'))
  } catch (err) {
    const detail = extractApiError(err) ?? t('adminSettings.errors.unknown')
    appToast.error(t('adminSettings.storage.testFailed'), detail)
  } finally {
    testing.value = false
  }
}

const migrateDialogVisible = ref(false)
const migration = reactive(useStorageMigration())
const migrationInProgress = computed(
  () => migration.phase === 'running' || migration.phase === 'observing',
)

// A migration started earlier, from this tab before a reload or by another
// admin, is still copying: show its progress right away.
onMounted(async () => {
  if (await migration.checkRunning()) migrateDialogVisible.value = true
})

async function openMigrateDialog() {
  migrateDialogVisible.value = true
  if (migrationInProgress.value) return
  migration.reset()
  await migration.checkRunning()
}

async function onMigrate() {
  try {
    await migration.start(buildCommand())
  } catch (err) {
    // An error frame carries the server's message; a refused request does not.
    const detail =
      err instanceof Error && !(err instanceof SseHttpError) ? err.message : undefined
    appToast.error(t('adminSettings.errors.unknown'), detail)
    migrateDialogVisible.value = false
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
            :disabled="!canWrite || providerChanged"
            v-tooltip.bottom="
              providerChanged ? t('adminSettings.storage.saveBlockedHint') : undefined
            "
            @click="onSave"
          />
          <Button
            :label="t('adminSettings.storage.testConnection')"
            icon="mdi mdi-connection"
            severity="contrast"
            text
            :loading="testing"
            :disabled="!canWrite"
            @click="onTest"
          />
          <Button
            :label="t('adminSettings.storage.migrate')"
            icon="mdi mdi-transfer"
            severity="danger"
            text
            :disabled="!canWrite"
            @click="openMigrateDialog"
          />
        </template>
      </Toolbar>
    </template>

    <div class="settings-fields">
      <p class="section-label">{{ t('adminSettings.storage.connectionSection') }}</p>
      <div class="field-row field-row--toggle">
        <label :for="`${uid}-enabled`">{{ t('adminSettings.storage.enabled') }}</label>
        <ToggleSwitch v-model="form.enabled" :input-id="`${uid}-enabled`" :disabled="!canWrite" />
      </div>

      <div class="field-row">
        <label :id="`${uid}-provider-label`" :for="`${uid}-provider`">
          {{ t('adminSettings.storage.provider') }}
          <span class="hint">{{ t('adminSettings.storage.providerInfo.' + form.provider) }}</span>
        </label>
        <Select
          :input-id="`${uid}-provider`"
          :aria-labelledby="`${uid}-provider-label`"
          :model-value="form.provider"
          :options="providerOptions"
          option-label="label"
          option-value="value"
          :disabled="!canWrite"
          @update:model-value="selectProvider"
        />
      </div>

      <div class="field-row">
        <label :for="`${uid}-endpoint-url`">
          {{ dynamicLabel('endpointUrl') }}
          <span v-if="fieldHint('endpointUrl')" class="hint">{{ fieldHint('endpointUrl') }}</span>
        </label>
        <InputText
          v-model="form.endpoint_url"
          :id="`${uid}-endpoint-url`"
          :disabled="isFieldDisabled('endpoint_url')"
        />
      </div>

      <div class="field-row">
        <label :for="`${uid}-public-endpoint-url`">
          {{ t('adminSettings.storage.publicEndpointUrl') }}
          <span v-if="fieldHint('publicEndpointUrl')" class="hint">{{
            fieldHint('publicEndpointUrl')
          }}</span>
        </label>
        <InputText
          v-model="form.public_endpoint_url"
          :id="`${uid}-public-endpoint-url`"
          :disabled="isFieldDisabled('public_endpoint_url')"
        />
      </div>

      <div class="field-row">
        <label :for="`${uid}-bucket-name`">
          {{ dynamicLabel('bucketName') }}
          <span v-if="fieldHint('bucketName')" class="hint">{{ fieldHint('bucketName') }}</span>
        </label>
        <InputText v-model="form.bucket_name" :id="`${uid}-bucket-name`" :disabled="isFieldDisabled('bucket_name')" />
      </div>

      <div class="field-row">
        <label :for="`${uid}-access-key`">
          {{ dynamicLabel('accessKey') }}
          <span v-if="fieldHint('accessKey')" class="hint">{{ fieldHint('accessKey') }}</span>
        </label>
        <InputText v-model="form.access_key" :id="`${uid}-access-key`" :disabled="isFieldDisabled('access_key')" />
      </div>

      <div class="field-row">
        <label :for="`${uid}-secret-key`">
          {{ dynamicLabel('secretKey') }}
          <span v-if="fieldHint('secretKey')" class="hint">{{ fieldHint('secretKey') }}</span>
        </label>
        <InputText
          v-model="form.secret_key"
          :id="`${uid}-secret-key`"
          type="password"
          :disabled="isFieldDisabled('secret_key')"
          :placeholder="
            form.secret_key_configured
              ? t('adminSettings.storage.secretKeyConfigured')
              : t('adminSettings.storage.secretKeyPlaceholder')
          "
        />
      </div>

      <div class="field-row">
        <label :for="`${uid}-region`">
          {{ t('adminSettings.storage.region') }}
          <span v-if="fieldHint('region')" class="hint">{{ fieldHint('region') }}</span>
        </label>
        <InputText v-model="form.region" :id="`${uid}-region`" :disabled="isFieldDisabled('region')" />
      </div>

      <div class="field-row field-row--toggle">
        <label :for="`${uid}-use-ssl`">
          {{ t('adminSettings.storage.useSsl') }}
          <span v-if="fieldHint('useSsl')" class="hint">{{ fieldHint('useSsl') }}</span>
        </label>
        <ToggleSwitch v-model="form.use_ssl" :input-id="`${uid}-use-ssl`" :disabled="isFieldDisabled('use_ssl')" />
      </div>

      <Divider />

      <p class="section-label">{{ t('adminSettings.storage.backupSection') }}</p>
      <div class="field-row field-row--toggle">
        <label :for="`${uid}-backup-enabled`">{{ t('adminSettings.storage.backupEnabled') }}</label>
        <ToggleSwitch v-model="form.backup_enabled" :input-id="`${uid}-backup-enabled`" :disabled="!canWrite" />
      </div>

      <div class="field-row">
        <label :for="`${uid}-backup-path`">
          {{ t('adminSettings.storage.backupPath') }}
          <span class="hint">{{ fieldHint('backupPath') }}</span>
        </label>
        <InputText
          v-model="form.backup_path"
          :id="`${uid}-backup-path`"
          :disabled="!canWrite || !form.backup_enabled"
        />
      </div>

      <div class="field-row">
        <label :for="`${uid}-backup-cron`">
          {{ t('adminSettings.storage.backupCron') }}
          <span class="hint">{{ t('adminSettings.storage.hints.backupCron') }}</span>
        </label>
        <InputText
          v-model="form.backup_cron"
          :id="`${uid}-backup-cron`"
          :disabled="!canWrite || !form.backup_enabled"
          placeholder="0 2 * * *"
        />
      </div>

      <div class="field-row">
        <label :for="`${uid}-backup-retention-count`">
          {{ t('adminSettings.storage.backupRetentionCount') }}
          <span class="hint">{{ t('adminSettings.storage.hints.backupRetentionCount') }}</span>
        </label>
        <InputNumber
          v-model="form.backup_retention_count"
          :input-id="`${uid}-backup-retention-count`"
          :disabled="!canWrite || !form.backup_enabled"
          :min="1"
          :use-grouping="false"
        />
      </div>

      <div class="field-row">
        <label :for="`${uid}-disk-warning-percent`">
          {{ t('adminSettings.storage.diskWarningPercent') }}
          <span class="hint">{{ t('adminSettings.storage.diskWarningPercentHint') }}</span>
        </label>
        <InputNumber
          v-model="form.disk_warning_percent"
          :input-id="`${uid}-disk-warning-percent`"
          :disabled="!canWrite"
          :min="0"
          :max="100"
          suffix=" %"
          :use-grouping="false"
        />
      </div>
    </div>
  </AdminSettingsTabShell>

  <Dialog
    v-model:visible="migrateDialogVisible"
    :header="t('adminSettings.storage.migrateDialog.header')"
    modal
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <div v-if="migration.phase === 'idle'" class="migrate-confirm">
      <p>{{ t('adminSettings.storage.migrateDialog.confirmText') }}</p>
    </div>
    <div v-else-if="migrationInProgress" class="migrate-progress">
      <ProgressBar v-if="migration.percent === null" mode="indeterminate" />
      <ProgressBar v-else :value="migration.percent" />
      <p role="status" aria-live="polite">
        {{
          migration.current !== null && migration.total !== null
            ? t('adminSettings.storage.migrateDialog.progress', {
                current: migration.current,
                total: migration.total,
              })
            : t('adminSettings.storage.migrateDialog.preparing')
        }}
      </p>
      <p
        v-if="migration.currentKey"
        class="migrate-progress__key"
        :title="migration.currentKey"
        data-testid="migration-current-key"
      >
        {{ migration.currentKey }}
      </p>
      <p
        v-if="migration.phase === 'observing' && migration.startedBy"
        class="migrate-progress__hint"
      >
        {{ t('adminSettings.storage.migrateDialog.startedBy', { name: migration.startedBy }) }}
      </p>
      <p class="migrate-progress__hint">
        {{ t('adminSettings.storage.migrateDialog.runningHint') }}
      </p>
    </div>
    <div v-else-if="migration.phase === 'finishedElsewhere'" class="migrate-confirm">
      <p>{{ t('adminSettings.storage.migrateDialog.finishedElsewhere') }}</p>
    </div>
    <div v-else-if="migration.result" class="migrate-result">
      <p :class="migration.result.committed ? 'result-success' : 'result-warning'">
        {{
          migration.result.committed
            ? t('adminSettings.storage.migrateDialog.result.committed')
            : t('adminSettings.storage.migrateDialog.result.notCommitted')
        }}
      </p>
      <p>
        {{
          t('adminSettings.storage.migrateDialog.result.migrated', {
            count: migration.result.migrated_count,
          })
        }}
      </p>
      <p v-if="migration.result.failed_count > 0">
        {{
          t('adminSettings.storage.migrateDialog.result.failed', {
            count: migration.result.failed_count,
          })
        }}
      </p>
      <div v-if="migration.result.errors.length" class="result-errors">
        <p class="result-errors__label">
          {{ t('adminSettings.storage.migrateDialog.result.errors') }}:
        </p>
        <ul>
          <li v-for="err in migration.result.errors" :key="err">{{ err }}</li>
        </ul>
      </div>
    </div>
    <template #footer>
      <template v-if="migration.phase === 'idle'">
        <Button
          :label="t('common.cancel')"
          severity="contrast"
          text
          @click="migrateDialogVisible = false"
        />
        <Button
          :label="t('adminSettings.storage.migrateDialog.startMigration')"
          icon="mdi mdi-transfer"
          @click="onMigrate"
        />
      </template>
      <Button
        v-else
        :label="t('common.close')"
        severity="contrast"
        text
        @click="migrateDialogVisible = false"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.field-row {
  flex-direction: column;
  align-items: flex-start;
}

.migrate-confirm p {
  margin: 0;
}

.migrate-result {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);

  p {
    margin: 0;
  }
}

.migrate-progress {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);

  p {
    margin: 0;
  }

  &__key {
    font-family: monospace;
    font-size: var(--font-size-sm);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &__hint {
    font-size: var(--font-size-sm);
    color: var(--p-text-muted-color);
  }
}

.result-success {
  color: var(--p-green-600);
  font-weight: 600;
}

.result-warning {
  color: var(--p-orange-600);
  font-weight: 600;
}

.result-errors {
  margin-top: var(--space-1);

  &__label {
    font-weight: 600;
  }

  ul {
    margin: var(--space-1) 0 0;
    padding-left: var(--space-4);
    font-size: var(--font-size-sm);
    color: var(--p-red-600);
  }
}
</style>
