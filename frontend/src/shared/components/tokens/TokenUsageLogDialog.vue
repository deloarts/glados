<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { DataTablePageEvent, DataTableRowContextMenuEvent } from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'

import { formatISODateTime } from '@/core/utils/dates'
import { storeToRefs } from 'pinia'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useClipboard } from '@/core/composables/useClipboard'
import { useAppToast } from '@/core/composables/useAppToast'
import { extractApiError } from '@/core/utils/errors'
import type { TokenApi } from '@/shared/api/createTokenApi'
import type { TokenSummary, TokenUsageLogEntry } from '@/shared/types/tokenTypes'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import EmptyState from '@/shared/components/EmptyState.vue'

const PAGE_SIZE = 10

const { t } = useI18n()
const { copyToClipboard } = useClipboard()
const appToast = useAppToast()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const visible = defineModel<boolean>('visible', { required: true })

const props = defineProps<{
  token: TokenSummary | null
  api: TokenApi
  i18nPrefix: string
}>()

const entries = ref<TokenUsageLogEntry[]>([])
const total = ref(0)
const skip = ref(0)
const loading = ref(false)

watchLoadingBar(loading)

function tt(key: string, params?: Record<string, unknown>): string {
  return t(`${props.i18nPrefix}.${key}`, params ?? {})
}

async function load(): Promise<void> {
  if (!props.token) return
  loading.value = true
  try {
    const page = await props.api.getUsageLog(props.token.id, { skip: skip.value, limit: PAGE_SIZE })
    entries.value = page.items
    total.value = page.total
  } catch (e) {
    appToast.error(tt('errors.unknown'), extractApiError(e) ?? undefined)
  } finally {
    loading.value = false
  }
}

watch(visible, (open) => {
  if (open) {
    skip.value = 0
    void load()
  }
})

function onPage(event: DataTablePageEvent): void {
  skip.value = event.first
  void load()
}

const cm = ref()
const contextMenuItem = ref<TokenUsageLogEntry | null>(null)

function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
  cm.value?.show(event.originalEvent)
}

const contextMenuItems = computed<MenuItem[]>(() => {
  const entry = contextMenuItem.value
  if (!entry) return []

  return [
    {
      label: t('common.copyUuid'),
      icon: 'mdi mdi-content-copy',
      command: () => void copyToClipboard(entry.public_id),
    },
  ]
})
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="tt('usageLogTitle', { name: token?.name ?? '' })"
    style="width: var(--dialog-width-lg)"
  >
    <DataTable
      :value="entries"
      v-model:context-menu-selection="contextMenuItem"
      lazy
      paginator
      :rows="PAGE_SIZE"
      :total-records="total"
      :first="skip"
      data-key="id"
      size="small"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
      @page="onPage"
      @row-contextmenu="onRowContextMenu"
    >
      <template #empty>
        <EmptyState :message="tt('noUsage')" />
      </template>

      <Column :header="tt('usageColumns.status')" style="width: 7rem">
        <template #body="{ data }: { data: TokenUsageLogEntry }">
          <Tag
            :severity="data.status_code && data.status_code < 400 ? 'success' : 'danger'"
            :value="data.status_code !== null ? `HTTP ${data.status_code}` : getEmptyPlaceholder()"
          />
        </template>
      </Column>
      <Column field="method" :header="tt('usageColumns.method')" style="width: 6rem" />
      <Column field="path" :header="tt('usageColumns.path')">
        <template #body="{ data }: { data: TokenUsageLogEntry }">
          <span class="path-cell">{{ data.path }}</span>
        </template>
      </Column>
      <Column :header="tt('usageColumns.calledAt')" style="width: 11rem">
        <template #body="{ data }: { data: TokenUsageLogEntry }">
          {{ formatISODateTime(data.called_at) }}
        </template>
      </Column>
    </DataTable>

    <ContextMenu ref="cm" :model="contextMenuItems" @hide="contextMenuItem = null" />
  </Dialog>
</template>

<style scoped lang="scss">
.path-cell {
  font-family: monospace;
  font-size: var(--font-size-sm);
  word-break: break-all;
}
</style>
