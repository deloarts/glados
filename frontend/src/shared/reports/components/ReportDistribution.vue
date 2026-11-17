<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { localeEndonym } from '@/core/i18n/localeMessages'
import type { AppLocale } from '@/core/i18n'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import { getReportJournal } from '../api'
import type { ReportJournalEntry, ReportPrintTarget } from '../api'

/**
 * The distribution of a record: every download and print of a report of
 * any of its revisions, newest first, from the export journal. The start of
 * each file's SHA-256 identifies a copy that turns up later.
 */

const props = defineProps<{ target: ReportPrintTarget }>()

const { t } = useI18n()

const rows = ref<ReportJournalEntry[]>([])
const loading = ref(false)
const failed = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    rows.value = await getReportJournal(props.target)
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
})

function size(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} kB`
}

function language(value: string): string {
  try {
    return localeEndonym(value as AppLocale)
  } catch {
    return value
  }
}
</script>

<template>
  <Message v-if="failed" severity="error">{{ t('reports.distribution.failed') }}</Message>
  <DataTable
    v-else
    :value="rows"
    :loading="loading"
    data-key="id"
    size="small"
    data-testid="report-distribution"
  >
    <template #empty>{{ t('reports.distribution.empty') }}</template>
    <Column :header="t('reports.distribution.when')" style="width: 11rem">
      <template #body="{ data }: { data: ReportJournalEntry }">
        <UserDateCell :date="data.created" :user-id="data.actor_id" :name="data.actor_full_name" with-time />
      </template>
    </Column>
    <Column :header="t('reports.distribution.what')">
      <template #body="{ data }: { data: ReportJournalEntry }">
        {{
          data.action === 'print'
            ? t('reports.distribution.printed', { copies: data.copies ?? 1 })
            : t('reports.distribution.downloaded')
        }}
      </template>
    </Column>
    <Column :header="t('reports.distribution.revision')" style="width: 6rem">
      <template #body="{ data }: { data: ReportJournalEntry }">{{ data.revision }}</template>
    </Column>
    <Column :header="t('reports.distribution.language')" style="width: 8rem">
      <template #body="{ data }: { data: ReportJournalEntry }">{{ language(data.language) }}</template>
    </Column>
    <Column :header="t('reports.distribution.file')" style="width: 10rem">
      <template #body="{ data }: { data: ReportJournalEntry }">
        <span v-tooltip.bottom="data.sha256" class="file">{{ size(data.byte_size) }}, {{ data.sha256.slice(0, 8) }}</span>
      </template>
    </Column>
  </DataTable>
</template>

<style scoped lang="scss">
.file {
  font-family: var(--font-family-mono, monospace);
  font-size: var(--font-size-sm);
}
</style>
