<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'
import { useClipboard } from '@/core/composables/useClipboard'

import { useAdminSettingsStore } from '../stores/adminSettingsStore'
import { storeToRefs } from 'pinia'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { extractApiError } from '@/core/utils/errors'
import { formatDateTimeOrDash, formatISODateTime } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import type {
  BackupEntry,
  BackupList,
  BackupRunEntry,
  BackupWarning,
} from '../types/adminSettingsTypes'
import AdminSettingsTabShell from './AdminSettingsTabShell.vue'
import EmptyState from '@/shared/components/EmptyState.vue'

const { t } = useI18n()
const appToast = useAppToast()
const { copyToClipboard } = useClipboard()
const store = useAdminSettingsStore()
const { hasPermission } = usePermissions()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const canWrite = hasPermission(Permission.WRITE_SETTINGS)

const loading = ref(false)
const backups = ref<BackupList | null>(null)
const runningNow = ref(false)

watchLoadingBar(loading)

const restoreDialogVisible = ref(false)
const selectedSnapshot = ref<BackupEntry | null>(null)
const restoring = ref(false)
const downloadingKey = ref<string | null>(null)

async function loadBackups() {
  loading.value = true
  try {
    backups.value = await store.fetchBackups()
  } catch {
    backups.value = null
  } finally {
    loading.value = false
  }
}

async function onRunNow() {
  runningNow.value = true
  try {
    await store.triggerBackupNow()
    appToast.success(t('adminSettings.backups.runNowSuccess'))
    setTimeout(() => void loadBackups(), 3000)
  } catch (err) {
    const detail = extractApiError(err) ?? t('adminSettings.errors.unknown')
    appToast.error(t('adminSettings.backups.runNowFailed'), detail)
  } finally {
    runningNow.value = false
  }
}

async function onDownloadBackup(entry: BackupEntry) {
  downloadingKey.value = entry.key
  try {
    await store.downloadBackup(entry.key)
  } catch (err) {
    const detail = extractApiError(err) ?? t('adminSettings.errors.unknown')
    appToast.error(t('adminSettings.backups.db.downloadFailed'), detail)
  } finally {
    downloadingKey.value = null
  }
}

function openRestoreDialog(snapshot: BackupEntry) {
  selectedSnapshot.value = snapshot
  restoreDialogVisible.value = true
}

async function onRestore() {
  if (!selectedSnapshot.value) return
  restoring.value = true
  try {
    const result = await store.restoreFileSnapshot(selectedSnapshot.value.key)
    appToast.success(
      t('adminSettings.backups.files.restoreSuccess'),
      t('adminSettings.backups.files.restoreResult', { count: result.restored_count }),
    )
    restoreDialogVisible.value = false
  } catch (err) {
    const detail = extractApiError(err) ?? t('adminSettings.errors.unknown')
    appToast.error(t('adminSettings.backups.files.restoreFailed'), detail)
  } finally {
    restoring.value = false
  }
}

function formatTimestamp(raw: string): string {
  try {
    return formatISODateTime(raw)
  } catch {
    return raw
  }
}

const lastRun = computed<BackupRunEntry | null>(() => backups.value?.last_run ?? null)

const warnings = computed<BackupWarning[]>(() => backups.value?.warnings ?? [])

// A running row has no finished_at yet, so the summary line falls back to
// when it started.
const lastRunTimestamp = computed<string | null>(() => {
  const run = lastRun.value
  if (!run) return null
  return run.finished_at ?? run.started_at
})

const lastRunError = computed<string | null>(() => {
  const run = lastRun.value
  return run && run.status === 'failed' ? run.error : null
})

function backupRunStatusSeverity(status: BackupRunEntry['status']): string {
  switch (status) {
    case 'success':
      return 'success'
    case 'failed':
      return 'danger'
    case 'running':
      return 'info'
    default:
      return 'secondary'
  }
}

async function copyRestoreCommand(key: string) {
  const cmd = `docker compose run --rm backend restore --backup ${key}`
  await copyToClipboard(cmd, t('adminSettings.backups.db.copyRestoreCommandSuccess'))
}

onMounted(loadBackups)
</script>

<template>
  <AdminSettingsTabShell>
    <template #controls>
      <Toolbar>
        <template #start>
          <Button
            :label="t('adminSettings.backups.runNow')"
            icon="mdi mdi-backup-restore"
            text
            severity="contrast"
            :loading="runningNow"
            :disabled="!canWrite"
            @click="onRunNow"
          />
          <Button
            :label="t('adminSettings.backups.refresh')"
            icon="mdi mdi-refresh"
            severity="contrast"
            text
            :loading="loading"
            @click="loadBackups"
          />
        </template>
      </Toolbar>
    </template>

    <template v-if="!loading">
      <!-- What the backup configuration lacks -->
      <div v-if="warnings.length" class="backup-warnings">
        <Message
          v-for="warning in warnings"
          :key="warning"
          severity="warn"
          :closable="false"
          :data-warning="warning"
        >
          {{ t(`adminSettings.backups.warnings.${warning}`) }}
        </Message>
      </div>

      <!-- Last backup summary -->
      <div v-if="backups" class="backup-section last-run">
        <h3 class="backup-section__title">{{ t('adminSettings.backups.lastRun.label') }}</h3>
        <div class="last-run__line">
          <span v-if="!lastRun" class="last-run__value">
            {{ t('adminSettings.backups.lastRun.never') }}
          </span>
          <template v-else>
            <span class="last-run__value">{{ formatTimestamp(lastRunTimestamp as string) }}</span>
            <Tag
              :value="t(`adminSettings.backups.status.${lastRun.status}`)"
              :severity="backupRunStatusSeverity(lastRun.status)"
              :class="{ 'last-run__status--running': lastRun.status === 'running' }"
            />
            <span class="last-run__trigger">
              ({{ t(`adminSettings.backups.trigger.${lastRun.trigger}`) }})
            </span>
          </template>
        </div>
        <Message v-if="lastRunError" severity="error" :closable="false" class="last-run__error">
          {{ lastRunError }}
        </Message>
      </div>

      <!-- Run History -->
      <div v-if="backups" class="backup-section">
        <h3 class="backup-section__title">{{ t('adminSettings.backups.history.title') }}</h3>
        <DataTable
          :value="backups.runs"
          size="small"
          :show-gridlines="isTableGridlinesEnabled"
          :striped-rows="isTableStripedEnabled"
        >
          <template #empty>
            <EmptyState :message="t('adminSettings.backups.history.empty')" />
          </template>
          <Column field="slot" :header="t('adminSettings.backups.history.slot')">
            <template #body="{ data }: { data: BackupRunEntry }">
              {{ formatTimestamp(data.slot) }}
            </template>
          </Column>
          <Column field="trigger" :header="t('adminSettings.backups.history.trigger')">
            <template #body="{ data }: { data: BackupRunEntry }">
              {{ t(`adminSettings.backups.trigger.${data.trigger}`) }}
            </template>
          </Column>
          <Column field="status" :header="t('adminSettings.backups.history.status')">
            <template #body="{ data }: { data: BackupRunEntry }">
              <Tag
                :value="t(`adminSettings.backups.status.${data.status}`)"
                :severity="backupRunStatusSeverity(data.status)"
              />
            </template>
          </Column>
          <Column field="started_at" :header="t('adminSettings.backups.history.started')">
            <template #body="{ data }: { data: BackupRunEntry }">
              {{ formatTimestamp(data.started_at) }}
            </template>
          </Column>
          <Column field="finished_at" :header="t('adminSettings.backups.history.finished')">
            <template #body="{ data }: { data: BackupRunEntry }">
              {{ formatDateTimeOrDash(data.finished_at) }}
            </template>
          </Column>
          <Column field="error" :header="t('adminSettings.backups.history.error')" class="key-col">
            <template #body="{ data }: { data: BackupRunEntry }">
              {{ data.error ?? getEmptyPlaceholder() }}
            </template>
          </Column>
        </DataTable>
      </div>

      <Message
        v-if="!backups || (backups.db.length === 0 && backups.files.length === 0)"
        severity="info"
        :closable="false"
      >
        {{ t('adminSettings.backups.notEnabled') }}
      </Message>

      <template v-else>
        <!-- DB Backups -->
        <div class="backup-section">
          <h3 class="backup-section__title">{{ t('adminSettings.backups.db.title') }}</h3>
          <DataTable
            :value="backups.db"
            size="small"
            :show-gridlines="isTableGridlinesEnabled"
            :striped-rows="isTableStripedEnabled"
          >
            <template #empty>
              <EmptyState :message="t('adminSettings.backups.db.empty')" />
            </template>
            <Column :header="t('common.actions')" style="width: 6rem">
              <template #body="{ data }: { data: BackupEntry }">
                <Button
                  icon="mdi mdi-download"
                  size="small"
                  severity="secondary"
                  text
                  :disabled="!canWrite"
                  :loading="downloadingKey === data.key"
                  v-tooltip.top.focus="t('adminSettings.backups.db.download')"
                  :aria-label="t('adminSettings.backups.db.download')"
                  @click="onDownloadBackup(data)"
                />
                <Button
                  icon="mdi mdi-content-copy"
                  size="small"
                  severity="secondary"
                  text
                  v-tooltip.top.focus="t('adminSettings.backups.db.copyRestoreCommand')"
                  :aria-label="t('adminSettings.backups.db.copyRestoreCommand')"
                  @click="copyRestoreCommand(data.key)"
                />
              </template>
            </Column>
            <Column
              field="timestamp"
              :header="t('adminSettings.backups.db.timestamp')"
              style="width: 13rem"
            >
              <template #body="{ data }">{{ formatTimestamp(data.timestamp) }}</template>
            </Column>
            <Column
              field="encrypted"
              :header="t('adminSettings.backups.db.encryption')"
              style="width: 10rem"
            >
              <template #body="{ data }: { data: BackupEntry }">
                <Tag
                  :value="
                    data.encrypted
                      ? t('adminSettings.backups.db.encrypted')
                      : t('adminSettings.backups.db.unencrypted')
                  "
                  :severity="data.encrypted ? 'secondary' : 'warn'"
                />
              </template>
            </Column>
            <Column field="key" :header="t('adminSettings.backups.db.key')" class="key-col" />
          </DataTable>
        </div>

        <!-- File Snapshots -->
        <div class="backup-section">
          <h3 class="backup-section__title">{{ t('adminSettings.backups.files.title') }}</h3>
          <DataTable
            :value="backups.files"
            size="small"
            :show-gridlines="isTableGridlinesEnabled"
            :striped-rows="isTableStripedEnabled"
          >
            <template #empty>
              <EmptyState :message="t('adminSettings.backups.files.empty')" />
            </template>
            <Column :header="t('common.actions')" style="width: 6rem">
              <template #body="{ data }">
                <Button
                  icon="mdi mdi-restore"
                  size="small"
                  severity="warn"
                  text
                  :disabled="!canWrite"
                  v-tooltip.top.focus="t('adminSettings.backups.files.restore')"
                  :aria-label="t('adminSettings.backups.files.restore')"
                  @click="openRestoreDialog(data)"
                />
              </template>
            </Column>
            <Column
              field="timestamp"
              :header="t('adminSettings.backups.files.timestamp')"
              style="width: 13rem"
            >
              <template #body="{ data }">{{ formatTimestamp(data.timestamp) }}</template>
            </Column>
            <Column field="key" :header="t('adminSettings.backups.files.key')" class="key-col" />
          </DataTable>
        </div>

        <!-- DB restore instructions -->
        <div class="restore-info">
          <h3 class="backup-section__title">{{ t('adminSettings.backups.db.restoreTitle') }}</h3>
          <p class="restore-info__text">{{ t('adminSettings.backups.db.restoreInfo') }}</p>
          <pre class="restore-info__code">
docker compose run --rm backend restore --backup &lt;key&gt;</pre
          >
        </div>
      </template>
    </template>
  </AdminSettingsTabShell>

  <!-- File restore confirmation -->
  <Dialog
    v-model:visible="restoreDialogVisible"
    :header="t('adminSettings.backups.files.restoreDialog.header')"
    modal
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <p>{{ t('adminSettings.backups.files.restoreDialog.confirmText') }}</p>
    <p v-if="selectedSnapshot" class="restore-key">{{ selectedSnapshot.key }}</p>
    <template #footer>
      <Button
        :label="t('common.cancel')"
        severity="contrast"
        text
        @click="restoreDialogVisible = false"
      />
      <Button
        :label="t('adminSettings.backups.files.restoreDialog.confirm')"
        icon="mdi mdi-restore"
        severity="warn"
        :loading="restoring"
        @click="onRestore"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.backup-warnings {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-bottom: var(--space-5);
}

.backup-section {
  margin-bottom: var(--space-6);

  &__title {
    font-size: var(--font-size-md);
    font-weight: 600;
    margin: 0 0 var(--space-3);
  }
}

.key-col {
  font-family: monospace;
  font-size: var(--font-size-sm);
  word-break: break-all;
}

.last-run {
  &__line {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  &__value {
    font-size: var(--font-size-sm);
  }

  &__trigger {
    color: var(--p-text-muted-color);
    font-size: var(--font-size-sm);
  }

  &__error {
    margin-top: var(--space-2);
  }

  &__status--running {
    animation: last-run-pulse 1.4s ease-in-out infinite;
  }
}

@keyframes last-run-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.55;
  }
}

.restore-info {
  margin-top: var(--space-2);

  &__text {
    margin: 0 0 var(--space-2);
    color: var(--p-text-muted-color);
    font-size: var(--font-size-sm);
  }

  &__code {
    background: var(--p-content-hover-background);
    padding: var(--space-3) var(--space-4);
    border-radius: var(--p-content-border-radius);
    font-size: var(--font-size-sm);
    overflow-x: auto;
    margin: 0;
  }
}

.restore-key {
  font-family: monospace;
  font-size: var(--font-size-sm);
  background: var(--p-content-hover-background);
  padding: var(--space-2) var(--space-2);
  border-radius: var(--p-content-border-radius);
  margin: var(--space-2) 0 0;
  word-break: break-all;
}
</style>
