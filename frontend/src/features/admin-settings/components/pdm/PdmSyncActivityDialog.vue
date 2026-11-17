<script setup lang="ts">
// The "Synchronize with PDM" activity dialog: what the sync is doing right
// now (requested and waiting for the scheduler, or the running poll with its
// phase, folder and progress) and the newest processed files across every
// run, refreshed every two seconds while it is open. Every field is always
// rendered, with a placeholder while nothing runs, so the dialog keeps its
// layout as a run starts and ends. Mounted with `v-if` by the tab, so
// mounting and unmounting switch the faster polling on and off.
import { computed, inject, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, routerKey } from 'vue-router'
import { storeToRefs } from 'pinia'

import { useLayoutStore } from '@/core/stores/layoutStore'
import { formatISODateTime, formatISOTime } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { usePdmSyncActivityStore } from '../../stores/pdmSyncActivityStore'
import { kindLabel } from '../../utils/pdmKind'
import { pdmEntryActionSeverity, pdmEntryItemRoute } from '../../utils/pdmSyncEntries'
import EmptyState from '@/shared/components/EmptyState.vue'

import type { PdmSyncRunEntry } from '../../types/adminSettingsTypes'

const { t } = useI18n()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
// Same defensive inject as PdmFilesDialog: a spec mounting this dialog
// without a router must not log an injection warning.
const router = inject(routerKey, null)

const store = usePdmSyncActivityStore()

const visible = defineModel<boolean>('visible', { required: true })
const emit = defineEmits<{ 'open-log': [] }>()

onMounted(() => {
  store.startPolling()
  store.setDialogOpen(true)
})

onUnmounted(() => {
  store.setDialogOpen(false)
  store.stopPolling()
})

const run = computed(() => store.activity?.run ?? null)
const entries = computed(() => store.activity?.recent_entries ?? [])

const statusText = computed(() => {
  if (run.value) {
    const phase = run.value.phase ?? 'walking'
    return t(`adminSettings.pdmSyncActivity.phase.${phase}`)
  }
  if (store.activity?.requested) return t('adminSettings.pdmSyncActivity.requested')
  return t('adminSettings.pdmSyncActivity.idle')
})

const runText = computed(() => {
  if (!run.value) return getEmptyPlaceholder()
  return t('adminSettings.pdmSyncActivity.startedAt', {
    trigger: t(`adminSettings.pdmSyncLog.runs.trigger.${run.value.trigger}`),
    time: formatISODateTime(run.value.started_at),
  })
})

const folderText = computed(() => run.value?.current_path || getEmptyPlaceholder())

const progressPercent = computed(() => {
  if (!run.value || run.value.files_queued === 0) return 0
  return Math.min(100, Math.round((run.value.files_processed / run.value.files_queued) * 100))
})

const progressText = computed(() => {
  if (!run.value || run.value.files_queued === 0) return getEmptyPlaceholder()
  return t('adminSettings.pdmSyncActivity.processed', {
    processed: run.value.files_processed,
    queued: run.value.files_queued,
  })
})

const counters = computed(() => {
  const r = run.value
  return [
    { key: 'filesSeen', value: r?.files_seen },
    { key: 'changed', value: r?.changed },
    { key: 'ingested', value: r?.ingested },
    { key: 'skipped', value: r?.skipped },
    { key: 'conflicts', value: r?.conflicts },
    { key: 'errors', value: r?.errors },
  ].map((counter) => ({ ...counter, text: counter.value ?? getEmptyPlaceholder() }))
})

function onOpenLog(): void {
  emit('open-log')
}

function itemRoute(row: PdmSyncRunEntry): string | null {
  return pdmEntryItemRoute(row)
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    maximizable
    :header="t('adminSettings.pdmSyncActivity.dialogTitle')"
    :style="{ width: 'var(--dialog-width-full)' }"
    content-class="pdm-sync-activity-content"
  >
    <section class="status" aria-live="polite">
      <div class="status-line">
        <i
          v-if="store.busy"
          class="mdi mdi-loading mdi-spin status-icon"
          aria-hidden="true"
        />
        <i v-else class="mdi mdi-check-circle-outline status-icon" aria-hidden="true" />
        <strong>{{ statusText }}</strong>
      </div>

      <dl class="details">
        <dt>{{ t('adminSettings.pdmSyncActivity.fields.run') }}</dt>
        <dd>{{ runText }}</dd>
        <dt>{{ t('adminSettings.pdmSyncActivity.fields.folder') }}</dt>
        <dd class="truncate-cell" v-tooltip.top="run?.current_path || undefined">{{ folderText }}</dd>
        <dt>{{ t('adminSettings.pdmSyncActivity.fields.progress') }}</dt>
        <dd class="progress">
          <ProgressBar
            class="sync-progress-bar"
            :value="progressPercent"
            :show-value="false"
            :aria-label="t('adminSettings.pdmSyncActivity.progressLabel')"
          />
          <span class="status-meta">{{ progressText }}</span>
        </dd>
      </dl>

      <dl class="counters">
        <div v-for="counter in counters" :key="counter.key" class="counter">
          <dt>{{ t(`adminSettings.pdmSyncActivity.counters.${counter.key}`) }}</dt>
          <dd>{{ counter.text }}</dd>
        </div>
      </dl>
    </section>

    <section class="recent">
      <div class="recent-header">
        <h3>{{ t('adminSettings.pdmSyncActivity.recentTitle') }}</h3>
        <Button
          :label="t('adminSettings.pdmSyncActivity.openLog')"
          icon="mdi mdi-history"
          text
          severity="contrast"
          @click="onOpenLog"
        />
      </div>

      <DataTable
        :value="entries"
        data-key="id"
        size="small"
        :show-gridlines="isTableGridlinesEnabled"
        :striped-rows="isTableStripedEnabled"
        class="recent-table fixed-layout-table ellipsis-cells"
      >
        <template #empty>
          <EmptyState :message="t('adminSettings.pdmSyncActivity.empty')" />
        </template>

        <Column :header="t('adminSettings.pdmSyncActivity.columns.time')" style="width: 7rem">
          <template #body="{ data }: { data: PdmSyncRunEntry }">{{ formatISOTime(data.created_at) }}</template>
        </Column>
        <Column :header="t('adminSettings.pdmSyncActivity.columns.file')" style="width: 22rem">
          <template #body="{ data }: { data: PdmSyncRunEntry }">
            <div class="file-cell" v-tooltip.top="data.path">
              <span>{{ data.name }}</span>
              <small>{{ data.path }}</small>
            </div>
          </template>
        </Column>
        <Column :header="t('adminSettings.pdmSyncActivity.columns.kind')" style="width: 10rem">
          <template #body="{ data }: { data: PdmSyncRunEntry }">{{ kindLabel(data.kind) }}</template>
        </Column>
        <Column :header="t('adminSettings.pdmSyncActivity.columns.action')" style="width: 9rem">
          <template #body="{ data }: { data: PdmSyncRunEntry }">
            <Tag
              :value="t(`adminSettings.pdmSyncLog.entries.action.${data.action}`)"
              :severity="pdmEntryActionSeverity(data.action)"
            />
          </template>
        </Column>
        <Column :header="t('adminSettings.pdmSyncActivity.columns.item')" style="width: 8rem">
          <template #body="{ data }: { data: PdmSyncRunEntry }">
            <RouterLink v-if="router && itemRoute(data)" :to="itemRoute(data)!" class="item-link">
              {{ t('adminSettings.pdmSyncLog.entries.itemLink', { id: data.item_id }) }}
            </RouterLink>
            <span v-else>{{ getEmptyPlaceholder() }}</span>
          </template>
        </Column>
        <Column :header="t('adminSettings.pdmSyncActivity.columns.message')">
          <template #body="{ data }: { data: PdmSyncRunEntry }">
            <span class="truncate-cell" v-tooltip.top="data.message">{{ data.message }}</span>
          </template>
        </Column>
      </DataTable>
    </section>
  </Dialog>
</template>

<style scoped lang="scss">
:global(.pdm-sync-activity-content) {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.status {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.status-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.status-icon {
  font-size: var(--font-size-lg);
}

.status-meta {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.details {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  align-items: center;
  column-gap: var(--space-4);
  row-gap: var(--space-2);
  margin: 0;

  dt {
    color: var(--p-text-muted-color);
    font-size: var(--font-size-sm);
  }

  dd {
    margin: 0;
    min-width: 0;
  }
}

.progress {
  display: flex;
  align-items: center;
  gap: var(--space-3);

  .sync-progress-bar {
    flex: 1 1 auto;
    --p-progressbar-height: 0.5rem;
  }

  .status-meta {
    flex: 0 0 18rem;
    white-space: nowrap;
  }
}

.counters {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-5);
  margin: 0;

  .counter {
    display: flex;
    flex-direction: column;
  }

  dt {
    color: var(--p-text-muted-color);
    font-size: var(--font-size-xs);
  }

  dd {
    margin: 0;
    font-size: var(--font-size-lg);
    font-weight: 600;
  }
}

.recent-header {
  display: flex;
  align-items: center;
  justify-content: space-between;

  h3 {
    margin: 0;
    font-size: var(--font-size-md);
  }
}

.file-cell {
  display: flex;
  flex-direction: column;
  min-width: 0;

  span,
  small {
    overflow: hidden;
    text-overflow: ellipsis;
  }

  small {
    color: var(--p-text-muted-color);
  }
}

.truncate-cell {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
