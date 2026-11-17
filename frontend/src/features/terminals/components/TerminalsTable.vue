<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import type {
  DataTableRowClickEvent,
  DataTableRowContextMenuEvent,
} from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'

import { TABLE_DEFAULT_ROWS, TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { formatISODateTime } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import EmptyState from '@/shared/components/EmptyState.vue'
import WithValue from '@/shared/components/WithValue.vue'
import { disabledItemTooltipPt } from '@/shared/utils/menuItemTooltip'
import { displayPowerState, isOffline } from '../utils/terminalStatus'
import { displaySummary, hardwareSummary, osSummary } from '../utils/deviceDetails'

import type { TerminalResponse } from '../types/terminalResponse'

/**
 * The approved and revoked terminals with what their devices reported.
 * Clicking a row opens its details, and the row context menu offers every
 * action; the actions column shows only while Show Actions is on. A
 * revoked terminal can only be deleted, so the other actions are hidden on
 * its row and disabled in its menu; without the permission to manage
 * terminals every action except the details stays visible but disabled.
 */
const props = defineProps<{
  terminals: TerminalResponse[]
  /** The current time, so the offline badge follows the clock. */
  now: number
  /** Whether the actions column is shown, the Show Actions switch of the views bar. */
  showActions: boolean
  canManage: boolean
  /** The tooltip of a disabled button, naming the missing permission. */
  missingHint: string
}>()

const emit = defineEmits<{
  details: [terminal: TerminalResponse]
  rename: [terminal: TerminalResponse]
  'change-screen': [terminal: TerminalResponse]
  display: [terminal: TerminalResponse]
  reload: [terminal: TerminalResponse]
  identify: [terminal: TerminalResponse]
  revoke: [terminal: TerminalResponse]
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

type RowAction =
  | 'details'
  | 'rename'
  | 'change-screen'
  | 'display'
  | 'reload'
  | 'identify'
  | 'revoke'
  | 'delete'

interface RowActionDef {
  action: RowAction
  label: string
  icon: string
  severity: 'secondary' | 'danger'
  /** Whether the action needs the permission to manage terminals. */
  manages: boolean
  /** Whether a separator comes before the action in the context menu. */
  groupStart?: boolean
}

const ACTIONS = computed<RowActionDef[]>(() => [
  {
    action: 'details',
    label: t('terminals.actions.details'),
    icon: 'mdi mdi-information-outline',
    severity: 'secondary',
    manages: false,
  },
  {
    action: 'rename',
    label: t('terminals.actions.rename'),
    icon: 'mdi mdi-pencil',
    severity: 'secondary',
    manages: true,
    groupStart: true,
  },
  {
    action: 'change-screen',
    label: t('terminals.actions.changeScreen'),
    icon: 'mdi mdi-television-guide',
    severity: 'secondary',
    manages: true,
  },
  {
    action: 'display',
    label: t('terminals.actions.display'),
    icon: 'mdi mdi-power',
    severity: 'secondary',
    manages: true,
    groupStart: true,
  },
  {
    action: 'reload',
    label: t('terminals.actions.reload'),
    icon: 'mdi mdi-refresh',
    severity: 'secondary',
    manages: true,
  },
  {
    action: 'identify',
    label: t('terminals.actions.identify'),
    icon: 'mdi mdi-crosshairs-gps',
    severity: 'secondary',
    manages: true,
  },
  {
    action: 'revoke',
    label: t('terminals.actions.revoke'),
    icon: 'mdi mdi-cancel',
    severity: 'danger',
    manages: true,
  },
  {
    action: 'delete',
    label: t('terminals.actions.delete'),
    icon: 'mdi mdi-delete-outline',
    severity: 'danger',
    manages: true,
    groupStart: true,
  },
])

/** A revoked terminal shows nothing any more, so only its details and deleting it are left. */
function actionsFor(terminal: TerminalResponse): RowActionDef[] {
  if (terminal.status === 'revoked') {
    return ACTIONS.value.filter((def) => def.action === 'details' || def.action === 'delete')
  }
  return ACTIONS.value
}

function allowed(def: RowActionDef): boolean {
  return props.canManage || !def.manages
}

function run(action: RowAction, terminal: TerminalResponse): void {
  switch (action) {
    case 'details':
      emit('details', terminal)
      break
    case 'rename':
      emit('rename', terminal)
      break
    case 'change-screen':
      emit('change-screen', terminal)
      break
    case 'display':
      emit('display', terminal)
      break
    case 'reload':
      emit('reload', terminal)
      break
    case 'identify':
      emit('identify', terminal)
      break
    case 'revoke':
      emit('revoke', terminal)
      break
    case 'delete':
      emit('delete', terminal)
      break
  }
}

function statusSeverity(terminal: TerminalResponse): 'success' | 'danger' | 'warn' {
  if (terminal.status === 'approved') return 'success'
  if (terminal.status === 'revoked') return 'danger'
  return 'warn'
}

function offline(terminal: TerminalResponse): boolean {
  return isOffline(terminal, props.now)
}

function power(terminal: TerminalResponse) {
  return displayPowerState(terminal, props.now)
}

// A click on the action buttons, disabled ones included, is not a click on the row.
function onRowClick(event: DataTableRowClickEvent): void {
  const target = event.originalEvent.target
  if (target instanceof Element && target.closest('.row-actions')) return
  emit('details', event.data as TerminalResponse)
}

const cm = ref()
const contextMenuTarget = ref<TerminalResponse | null>(null)

function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
  cm.value?.show(event.originalEvent)
}

// The fixed shape: the details, then editing, then the steps a display
// takes, then Delete. A missing permission names itself as the title of the
// disabled entry; an action the terminal's state rules out is just disabled.
const contextMenuItems = computed<MenuItem[]>(() => {
  const terminal = contextMenuTarget.value
  if (!terminal) return []
  const offered = actionsFor(terminal)
  return ACTIONS.value.flatMap((def): MenuItem[] => [
    ...(def.groupStart ? [{ separator: true }] : []),
    {
      label: def.label,
      icon: def.icon,
      disabled: !allowed(def) || !offered.includes(def),
      title: allowed(def) ? undefined : props.missingHint,
      command: () => run(def.action, terminal),
    },
  ])
})

/** The display follows the times of the terminal's infoscreen, which the infoscreens page sets. */
function powerHint(terminal: TerminalResponse): string | undefined {
  return terminal.infoscreen_name
    ? t('terminals.power.followsScreen', { screen: terminal.infoscreen_name })
    : undefined
}
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
    row-hover
    class="clickable-rows"
    v-model:context-menu-selection="contextMenuTarget"
    data-testid="enrolled-terminals"
    @row-click="onRowClick"
    @row-contextmenu="onRowContextMenu"
  >
    <template #empty>
      <EmptyState :message="t('terminals.enrolled.empty')" />
    </template>

    <Column header="#" class="column-fit" body-class="row-number">
      <template #body="{ index }">{{ first + index + 1 }}</template>
    </Column>
    <Column v-if="showActions" :header="t('terminals.columns.actions')" class="column-fit">
      <template #body="{ data }: { data: TerminalResponse }">
        <div class="row-actions">
          <span
            v-for="def in actionsFor(data)"
            :key="def.action"
            v-tooltip.top="allowed(def) ? def.label : missingHint"
          >
            <Button
              :icon="def.icon"
              size="small"
              :severity="def.severity"
              text
              :disabled="!allowed(def)"
              :aria-label="def.label"
              :data-testid="`terminal-${def.action}`"
              @click="run(def.action, data)"
            />
          </span>
        </div>
      </template>
    </Column>
    <Column :header="t('terminals.columns.name')" class="column-fit">
      <template #body="{ data }: { data: TerminalResponse }">
        <span v-if="data.name">{{ data.name }}</span>
        <span v-else class="text-muted">{{ t('terminals.unnamed') }}</span>
      </template>
    </Column>
    <Column :header="t('terminals.columns.location')" class="column-fit">
      <template #body="{ data }: { data: TerminalResponse }">
        <span v-if="data.location" class="location">{{ data.location }}</span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <Column :header="t('terminals.columns.status')" class="column-fit">
      <template #body="{ data }: { data: TerminalResponse }">
        <div class="tags">
          <Tag :value="t(`terminals.status.${data.status}`)" :severity="statusSeverity(data)" />
          <Tag
            v-if="offline(data)"
            :value="t('terminals.badges.offline')"
            severity="secondary"
            icon="mdi mdi-lan-disconnect"
            v-tooltip.top="t('terminals.badges.offlineTooltip')"
            data-testid="terminal-offline"
          />
          <Tag
            v-if="data.duplicate_detected_at"
            :value="t('terminals.badges.duplicate')"
            severity="danger"
            icon="mdi mdi-content-duplicate"
            v-tooltip.top="
              t('terminals.badges.duplicateTooltip', {
                date: formatISODateTime(data.duplicate_detected_at),
              })
            "
            data-testid="terminal-duplicate"
          />
        </div>
      </template>
    </Column>
    <Column :header="t('terminals.columns.display')" class="column-fit">
      <template #body="{ data }: { data: TerminalResponse }">
        <WithValue :value="power(data)" v-slot="{ value: state }">
          <div
            v-if="state"
            v-tooltip.top="powerHint(data)"
            class="power"
            data-testid="terminal-power"
          >
            <Tag
              :value="t(`terminals.power.${state.power}`)"
              :severity="state.power === 'on' ? 'success' : 'secondary'"
              :icon="state.power === 'on' ? 'mdi mdi-monitor' : 'mdi mdi-monitor-off'"
            />
            <small v-if="state.manual && state.until" class="power-until" data-testid="terminal-power-override">
              {{ t('terminals.power.manualUntil', { date: formatISODateTime(state.until) }) }}
            </small>
            <small v-else-if="state.until" class="power-until">
              {{ t('terminals.power.until', { date: formatISODateTime(state.until) }) }}
            </small>
          </div>
          <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
        </WithValue>
      </template>
    </Column>
    <Column :header="t('terminals.columns.mode')" class="column-fit">
      <template #body="{ data }: { data: TerminalResponse }">
        {{ t(`terminals.modes.${data.mode}`) }}
      </template>
    </Column>
    <Column :header="t('terminals.columns.screen')" class="column-fit">
      <template #body="{ data }: { data: TerminalResponse }">
        <span v-if="data.infoscreen_name">{{ data.infoscreen_name }}</span>
        <span v-else class="text-muted">{{ t('terminals.noScreen') }}</span>
      </template>
    </Column>
    <Column :header="t('terminals.columns.hardware')" class="column-fit">
      <template #body="{ data }: { data: TerminalResponse }">
        <span v-if="hardwareSummary(data.device)">{{ hardwareSummary(data.device) }}</span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <Column :header="t('terminals.columns.monitor')" class="column-fit">
      <template #body="{ data }: { data: TerminalResponse }">
        <span v-if="displaySummary(data.device)">{{ displaySummary(data.device) }}</span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <Column :header="t('terminals.columns.os')" class="column-fit">
      <template #body="{ data }: { data: TerminalResponse }">
        <span v-if="osSummary(data.device)">{{ osSummary(data.device) }}</span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <Column :header="t('terminals.columns.versions')" class="column-fit">
      <template #body="{ data }: { data: TerminalResponse }">
        <div class="versions">
          <span>{{ t('terminals.versionWeb', { version: data.frontend_version ?? getEmptyPlaceholder() }) }}</span>
          <span>{{ t('terminals.versionBridge', { version: data.bridge_version ?? getEmptyPlaceholder() }) }}</span>
        </div>
      </template>
    </Column>
    <Column :header="t('terminals.columns.lastSeen')" class="column-fit">
      <template #body="{ data }: { data: TerminalResponse }">
        <template v-if="data.last_seen_at">{{ formatISODateTime(data.last_seen_at) }}</template>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <!-- Takes the width the content-wide columns leave, so the table spans
         its card without stretching them. -->
    <Column />
  </DataTable>

  <ContextMenu
    ref="cm"
    :model="contextMenuItems"
    :pt="disabledItemTooltipPt"
    @hide="contextMenuTarget = null"
  />
</template>

<style scoped lang="scss">
.tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.versions {
  display: flex;
  flex-direction: column;
  font-size: var(--font-size-sm);
}

.location {
  font-size: var(--font-size-sm);
}

.power {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-1);
}

.power-until {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-xs);
  white-space: nowrap;
}
</style>
