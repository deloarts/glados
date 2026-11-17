<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import type { DataTableRowContextMenuEvent } from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'

import { TABLE_DEFAULT_ROWS, TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { formatISODateTime } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import EmptyState from '@/shared/components/EmptyState.vue'
import { disabledItemTooltipPt } from '@/shared/utils/menuItemTooltip'
import { screenSize } from '../utils/terminalStatus'

import type { TerminalResponse } from '../types/terminalResponse'

/**
 * Terminals that registered and wait for someone to type their pairing
 * code. The code is shown so the person can tell which row belongs to the
 * TV in front of them; approving still means typing it. The short list
 * keeps its actions column, and the row context menu offers the same two
 * actions.
 */
const props = defineProps<{
  terminals: TerminalResponse[]
  canManage: boolean
  /** The tooltip of a disabled button, naming the missing permission. */
  missingHint: string
}>()

const emit = defineEmits<{
  approve: [terminal: TerminalResponse]
  delete: [terminal: TerminalResponse]
}>()

const { t } = useI18n()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

// The page shown; a search or a live change that leaves fewer rows than the
// page starts at goes back to the first page.
const first = ref(0)
const pageRows = ref(TABLE_DEFAULT_ROWS)
watch(
  () => props.terminals.length,
  (count) => {
    if (first.value >= count) first.value = 0
  },
)

const cm = ref()
const contextMenuTarget = ref<TerminalResponse | null>(null)

function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
  cm.value?.show(event.originalEvent)
}

const contextMenuItems = computed<MenuItem[]>(() => {
  const terminal = contextMenuTarget.value
  if (!terminal) return []
  const title = props.canManage ? undefined : props.missingHint
  return [
    {
      label: t('terminals.actions.approve'),
      icon: 'mdi mdi-check',
      disabled: !props.canManage,
      title,
      command: () => emit('approve', terminal),
    },
    { separator: true },
    {
      label: t('terminals.actions.delete'),
      icon: 'mdi mdi-delete-outline',
      disabled: !props.canManage,
      title,
      command: () => emit('delete', terminal),
    },
  ]
})
</script>

<template>
  <DataTable
    :value="terminals"
    data-key="id"
    v-model:first="first"
    v-model:rows="pageRows"
    paginator
    always-show-paginator
    :rows-per-page-options="TABLE_ROWS_PER_PAGE_OPTIONS"
    scrollable
    scroll-height="flex"
    size="small"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    v-model:context-menu-selection="contextMenuTarget"
    data-testid="pending-terminals"
    @row-contextmenu="onRowContextMenu"
  >
    <template #empty>
      <EmptyState :message="t('terminals.pending.empty')" />
    </template>

    <Column header="#" class="column-fit" body-class="row-number">
      <template #body="{ index }">{{ first + index + 1 }}</template>
    </Column>
    <Column :header="t('terminals.columns.actions')" class="column-fit">
      <template #body="{ data }: { data: TerminalResponse }">
        <div class="row-actions">
          <span v-tooltip.top="canManage ? undefined : missingHint">
            <Button
              :label="t('terminals.actions.approve')"
              icon="mdi mdi-check"
              size="small"
              severity="success"
              text
              :disabled="!canManage"
              data-testid="terminal-approve"
              @click="emit('approve', data)"
            />
          </span>
          <span v-tooltip.top="canManage ? t('terminals.actions.delete') : missingHint">
            <Button
              icon="mdi mdi-delete-outline"
              size="small"
              severity="danger"
              text
              :disabled="!canManage"
              :aria-label="t('terminals.actions.delete')"
              data-testid="terminal-delete"
              @click="emit('delete', data)"
            />
          </span>
        </div>
      </template>
    </Column>
    <Column :header="t('terminals.columns.code')" class="column-fit">
      <template #body="{ data }: { data: TerminalResponse }">
        <span class="pairing-code">{{ data.pairing_code ?? getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <Column :header="t('terminals.columns.ip')" class="column-fit">
      <template #body="{ data }: { data: TerminalResponse }">
        <span v-if="data.last_ip" class="mono">{{ data.last_ip }}</span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <Column :header="t('terminals.columns.screenSize')" class="column-fit">
      <template #body="{ data }: { data: TerminalResponse }">
        {{ screenSize(data) ?? getEmptyPlaceholder() }}
      </template>
    </Column>
    <Column :header="t('terminals.columns.firstSeen')" class="column-fit">
      <template #body="{ data }: { data: TerminalResponse }">
        {{ formatISODateTime(data.first_seen_at) }}
      </template>
    </Column>
    <Column :header="t('terminals.columns.expires')" class="column-fit">
      <template #body="{ data }: { data: TerminalResponse }">
        <template v-if="data.pairing_expires_at">{{ formatISODateTime(data.pairing_expires_at) }}</template>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <!-- The long user agent comes last and takes the width the other columns
         leave, wrapping inside it. -->
    <Column :header="t('terminals.columns.userAgent')">
      <template #body="{ data }: { data: TerminalResponse }">
        <span v-if="data.user_agent" class="user-agent">{{ data.user_agent }}</span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
  </DataTable>

  <ContextMenu
    ref="cm"
    :model="contextMenuItems"
    :pt="disabledItemTooltipPt"
    @hide="contextMenuTarget = null"
  />
</template>

<style scoped lang="scss">
.pairing-code {
  font-family: monospace;
  font-size: var(--font-size-md);
  font-weight: 600;
  letter-spacing: 0.15em;
}

.mono {
  font-family: monospace;
}

.user-agent {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
}
</style>
