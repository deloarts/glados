<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'

import type { MenuItem } from 'openvue/menuitem'

import { Permission } from '@/core/auth/permissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { usePermissions } from '@/core/composables/usePermissions'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { HelpButton } from '@/shared/help'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import {
  deleteTerminal,
  identifyTerminal,
  reloadTerminal,
  revokeTerminal,
  type TerminalBulkAction,
} from '../api/terminalsApi'
import TerminalApproveDialog from '../components/TerminalApproveDialog.vue'
import TerminalBroadcastDialog from '../components/TerminalBroadcastDialog.vue'
import TerminalBulkConfirmDialog from '../components/TerminalBulkConfirmDialog.vue'
import TerminalDetailsDialog from '../components/TerminalDetailsDialog.vue'
import TerminalDisplayOverrideDialog from '../components/TerminalDisplayOverrideDialog.vue'
import TerminalEditDialog from '../components/TerminalEditDialog.vue'
import TerminalsTable from '../components/TerminalsTable.vue'
import TerminalsWaitingDialog from '../components/TerminalsWaitingDialog.vue'
import { useTerminals } from '../composables/useTerminals'
import { matchesTerminalSearch } from '../utils/terminalStatus'

import type { TerminalBroadcastResponse, TerminalResponse } from '../types/terminalResponse'

const API_KEYS_PATH = '/settings/apiKeys'

const { t } = useI18n()
const confirm = useConfirm()
const toast = useAppToast()
const { withErrorToast, toastOnError } = useErrorToast()
const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()

const canManage = computed(() => hasPermission(Permission.MANAGE_TERMINALS))
const missingManage = computed(() => missing(Permission.MANAGE_TERMINALS))

const {
  terminals,
  pending,
  enrolled,
  approved,
  screens,
  broadcasts,
  hasTerminalKey,
  now,
  loading,
  start,
  load,
  upsert,
  remove,
  upsertBroadcast,
  loadTerminals,
} = useTerminals()

onMounted(start)

const search = ref('')
// The actions column is off by default, as on the other resource pages, and
// the row context menu offers the same actions.
const showActions = ref(false)
const visibleRows = computed(() =>
  enrolled.value.filter((terminal) => matchesTerminalSearch(terminal, search.value)),
)

function refresh(): void {
  load().catch(toastOnError())
}

const waitingVisible = ref(false)
const approveVisible = ref(false)
const approveTarget = ref<TerminalResponse | null>(null)
const editVisible = ref(false)
const editTarget = ref<TerminalResponse | null>(null)
const editField = ref<'name' | 'screen'>('name')
const broadcastVisible = ref(false)

// The dialogs that show one terminal read it from the list by id, so they
// follow the live stream while they are open.
const detailsVisible = ref(false)
const detailsId = ref<number | null>(null)
const detailsTarget = computed(() => terminals.value.find((row) => row.id === detailsId.value) ?? null)
const overrideVisible = ref(false)
const overrideId = ref<number | null>(null)
const overrideTarget = computed(
  () => terminals.value.find((row) => row.id === overrideId.value) ?? null,
)

function label(terminal: TerminalResponse): string {
  return terminal.name ?? terminal.pairing_code ?? t('terminals.unnamed')
}

function openApprove(terminal: TerminalResponse): void {
  approveTarget.value = terminal
  approveVisible.value = true
}

function onApproved(terminal: TerminalResponse): void {
  upsert(terminal)
  toast.success(label(terminal), t('terminals.toasts.approved'))
}

function openEdit(terminal: TerminalResponse, field: 'name' | 'screen'): void {
  editTarget.value = terminal
  editField.value = field
  editVisible.value = true
}

function onEdited(terminal: TerminalResponse): void {
  upsert(terminal)
  toast.success(
    label(terminal),
    editField.value === 'screen' ? t('terminals.toasts.screenChanged') : t('terminals.toasts.saved'),
  )
}

function openDetails(terminal: TerminalResponse): void {
  detailsId.value = terminal.id
  detailsVisible.value = true
}

function openOverride(terminal: TerminalResponse): void {
  overrideId.value = terminal.id
  overrideVisible.value = true
}

function onOverrideSaved(terminal: TerminalResponse, cleared: boolean): void {
  upsert(terminal)
  toast.success(
    label(terminal),
    cleared ? t('terminals.toasts.overrideCleared') : t('terminals.toasts.overrideSet'),
  )
}

async function signal(
  terminal: TerminalResponse,
  call: (id: number) => Promise<TerminalResponse>,
  message: string,
): Promise<void> {
  const updated = await withErrorToast(() => call(terminal.id), {
    summary: label(terminal),
    fallbackMessage: t('terminals.errors.unknown'),
  })
  if (!updated) return
  upsert(updated)
  toast.success(label(updated), message)
}

function onReload(terminal: TerminalResponse): void {
  void signal(terminal, reloadTerminal, t('terminals.toasts.reloaded'))
}

function onIdentify(terminal: TerminalResponse): void {
  void signal(terminal, identifyTerminal, t('terminals.toasts.identified'))
}

function onRevoke(terminal: TerminalResponse): void {
  confirm.require({
    header: t('terminals.confirm.revokeHeader'),
    message: t('terminals.confirm.revokeMessage', { name: label(terminal) }),
    icon: 'mdi mdi-cancel',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('terminals.actions.revoke'), severity: 'danger' },
    accept: () => void signal(terminal, revokeTerminal, t('terminals.toasts.revoked')),
  })
}

function onDelete(terminal: TerminalResponse): void {
  async function onAccept(): Promise<void> {
    const done = await withErrorToast(
      async () => {
        await deleteTerminal(terminal.id)
        return true
      },
      { summary: label(terminal), fallbackMessage: t('terminals.errors.unknown') },
    )
    if (!done) return
    remove(terminal.id)
    toast.success(label(terminal), t('terminals.toasts.deleted'))
  }

  confirm.require({
    header: t('terminals.confirm.deleteHeader'),
    message: t('terminals.confirm.deleteMessage', { name: label(terminal) }),
    icon: 'mdi mdi-delete-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('terminals.actions.delete'), severity: 'danger' },
    accept: () => void onAccept(),
  })
}

// Actions on all terminals. Reload, identify and revoke reach the approved
// terminals; delete removes every terminal, waiting and revoked ones too.
const allMenu = ref()
const bulkVisible = ref(false)
const bulkAction = ref<TerminalBulkAction | null>(null)

function bulkCount(action: TerminalBulkAction): number {
  return action === 'delete' ? terminals.value.length : approved.value.length
}

function openBulk(action: TerminalBulkAction): void {
  bulkAction.value = action
  bulkVisible.value = true
}

const allMenuItems = computed<MenuItem[]>(() =>
  (
    [
      ['reload', 'mdi mdi-refresh'],
      ['identify', 'mdi mdi-crosshairs-gps'],
      ['revoke', 'mdi mdi-cancel'],
      ['delete', 'mdi mdi-delete-outline'],
    ] as const
  ).map(([action, icon]) => ({
    label: t(`terminals.bulk.${action}.item`, { count: bulkCount(action) }),
    icon,
    disabled: bulkCount(action) === 0,
    command: () => openBulk(action),
  })),
)

function toggleAllMenu(event: Event): void {
  allMenu.value?.toggle(event)
}

function onBulkDone(action: TerminalBulkAction, count: number): void {
  toast.success(
    t('terminals.bulk.toastSummary'),
    t(`terminals.bulk.${action}.done`, { count }, count),
  )
  loadTerminals().catch(toastOnError())
}

function onBroadcastSent(broadcast: TerminalBroadcastResponse): void {
  upsertBroadcast(broadcast)
  toast.success(
    t('terminals.broadcast.title'),
    t('terminals.broadcast.sent', { count: broadcast.reach_count }, broadcast.reach_count),
  )
}

function onBroadcastEnded(broadcast: TerminalBroadcastResponse): void {
  upsertBroadcast(broadcast)
  toast.success(t('terminals.broadcast.title'), t('terminals.broadcast.ended'))
}
</script>

<template>

  <PageLayout>
    <template #controls>
      <ControlsBar>
        <template #start>
          <Button
            :label="t('terminals.controls.waiting')"
            icon="mdi mdi-timer-sand"
            severity="contrast"
            text
            :badge="pending.length > 0 ? String(pending.length) : undefined"
            badge-severity="warn"
            data-testid="terminals-waiting"
            @click="waitingVisible = true"
          />
          <span v-tooltip.bottom="missingManage || undefined">
            <Button
              :label="t('terminals.controls.all')"
              icon="mdi mdi-monitor-multiple"
              severity="contrast"
              text
              :disabled="!canManage"
              aria-haspopup="true"
              aria-controls="terminals-all-menu"
              data-testid="terminals-all"
              @click="toggleAllMenu"
            />
          </span>
          <span v-tooltip.bottom="missingManage || undefined">
            <Button
              :label="t('terminals.controls.message')"
              icon="mdi mdi-message-alert-outline"
              severity="contrast"
              text
              :disabled="!canManage"
              :badge="broadcasts.length > 0 ? String(broadcasts.length) : undefined"
              badge-severity="info"
              data-testid="terminals-message"
              @click="broadcastVisible = true"
            />
          </span>
        </template>
        <template #handbook>
          <HelpButton rounded />
        </template>
      </ControlsBar>
      <Menu id="terminals-all-menu" ref="allMenu" :model="allMenuItems" popup />
    </template>
    <template #views>
      <ViewsBar
        id-prefix="terminals"
        :syncing="loading"
        :show-actions="showActions"
        :has-active-filters="search !== ''"
        v-model:search="search"
        :search-placeholder="t('terminals.controls.search')"
        @sync="refresh"
        @clear="search = ''"
        @toggle-show-actions="showActions = !showActions"
      />
    </template>
    <template #menu>
      <Message
        v-if="hasTerminalKey === false"
        severity="info"
        :closable="false"
        data-testid="terminals-key-hint"
      >
        {{ t('terminals.keyHint.message') }}
        <RouterLink :to="API_KEYS_PATH">{{ t('terminals.keyHint.link') }}</RouterLink>
      </Message>
    </template>

    <TerminalsTable
      :terminals="visibleRows"
      :now="now"
      :show-actions="showActions"
      :can-manage="canManage"
      :missing-hint="missingManage"
      @details="openDetails"
      @rename="openEdit($event, 'name')"
      @change-screen="openEdit($event, 'screen')"
      @display="openOverride"
      @reload="onReload"
      @identify="onIdentify"
      @revoke="onRevoke"
      @delete="onDelete"
    />
  </PageLayout>

  <TerminalsWaitingDialog
    v-model:visible="waitingVisible"
    :terminals="pending"
    :can-manage="canManage"
    :missing-hint="missingManage"
    @approve="openApprove"
    @delete="onDelete"
  />
  <TerminalApproveDialog
    v-model:visible="approveVisible"
    :terminal="approveTarget"
    :screens="screens"
    @approved="onApproved"
  />
  <TerminalEditDialog
    v-model:visible="editVisible"
    :terminal="editTarget"
    :field="editField"
    :screens="screens"
    @saved="onEdited"
  />
  <TerminalDetailsDialog v-model:visible="detailsVisible" :terminal="detailsTarget" :now="now" />
  <TerminalDisplayOverrideDialog
    v-model:visible="overrideVisible"
    :terminal="overrideTarget"
    :now="now"
    @saved="onOverrideSaved"
  />
  <TerminalBulkConfirmDialog
    v-model:visible="bulkVisible"
    :action="bulkAction"
    :count="bulkAction ? bulkCount(bulkAction) : 0"
    @done="onBulkDone"
  />
  <TerminalBroadcastDialog
    v-model:visible="broadcastVisible"
    :broadcasts="broadcasts"
    :terminals="approved"
    :screens="screens"
    :can-manage="canManage"
    :missing-hint="missingManage"
    @sent="onBroadcastSent"
    @ended="onBroadcastEnded"
  />
</template>
