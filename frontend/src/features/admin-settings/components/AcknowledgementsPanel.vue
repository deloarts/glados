<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'
import { useAppToast } from '@/core/composables/useAppToast'

import { storeToRefs } from 'pinia'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useLiveStore } from '@/core/realtime/liveStore'
import { LiveResource } from '@/core/realtime/resources'
import { formatISODateTime } from '@/core/utils/dates'

import { deleteAcknowledgement } from '../api/deleteAcknowledgement'
import { getAcknowledgements } from '../api/getAcknowledgements'
import { setAcknowledgementEnabled } from '../api/setAcknowledgementEnabled'
import type { Acknowledgement } from '../types/acknowledgementTypes'
import type { AnnouncementSeverity } from '../types/adminSettingsTypes'
import AcknowledgementFormDialog from './AcknowledgementFormDialog.vue'
import AcknowledgementRecipientsDialog from './AcknowledgementRecipientsDialog.vue'
import EmptyState from '@/shared/components/EmptyState.vue'

const { t } = useI18n()
const confirm = useConfirm()
const appToast = useAppToast()
const liveStore = useLiveStore()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

defineProps<{ canWrite: boolean }>()

const acknowledgements = ref<Acknowledgement[]>([])
const loading = ref(false)
watchLoadingBar(loading)

const formVisible = ref(false)

const recipientsVisible = ref(false)
const recipientsAcknowledgement = ref<Acknowledgement | null>(null)
const recipientsDialog = ref<InstanceType<typeof AcknowledgementRecipientsDialog> | null>(null)

async function load(): Promise<void> {
  loading.value = true
  try {
    acknowledgements.value = await getAcknowledgements()
  } catch {
    appToast.error(t('adminSettings.notifications.acknowledgements.loadFailed'))
  } finally {
    loading.value = false
  }
}

onMounted(load)

// The admin sees confirmations arrive live, not just on the next manual
// reload: a recipient row change is coerced to an 'updated' signal on this
// same topic (see the API contract's live-signals section), so any signal
// here means "refetch", never carries row data itself.
const unsubscribeLive = liveStore.on(LiveResource.ANNOUNCEMENTS, () => {
  void load()
  if (recipientsVisible.value) void recipientsDialog.value?.reload()
})

onUnmounted(() => unsubscribeLive())

function onAdd(): void {
  formVisible.value = true
}

function onShowRecipients(ack: Acknowledgement): void {
  recipientsAcknowledgement.value = ack
  recipientsVisible.value = true
}

async function onToggleEnabled(ack: Acknowledgement, enabled: boolean): Promise<void> {
  try {
    const updated = await setAcknowledgementEnabled(ack.public_id, enabled)
    const index = acknowledgements.value.findIndex((a) => a.id === ack.id)
    if (index !== -1) acknowledgements.value[index] = updated
  } catch {
    appToast.error(t('adminSettings.notifications.acknowledgements.saveFailed'))
  }
}

/**
 * Confirm-dialog messages are one line: a 4000-char acknowledgement text
 * has no business filling the whole popup.
 */
function truncate(text: string, max = 80): string {
  return text.length > max ? `${text.slice(0, max)}…` : text
}

function onDelete(ack: Acknowledgement): void {
  async function onAccept(): Promise<void> {
    try {
      await deleteAcknowledgement(ack.public_id)
      appToast.success(t('adminSettings.notifications.acknowledgements.deleted'))
      await load()
    } catch {
      appToast.error(t('adminSettings.notifications.acknowledgements.saveFailed'))
    }
  }

  confirm.require({
    message: t('adminSettings.notifications.acknowledgements.deleteConfirm', {
      text: truncate(ack.text),
    }),
    header: t('common.delete'),
    icon: 'mdi mdi-delete-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('common.delete'), severity: 'danger' },
    accept: () => void onAccept(),
  })
}

/**
 * Tag's severity names differ slightly from Message's (see
 * announcements/utils/severity.ts's toMessageSeverity): Tag has no 'error',
 * it uses 'danger' natively, so only the 'warning' -> 'warn' rename applies
 * here.
 */
function tagSeverity(severity: AnnouncementSeverity): 'info' | 'warn' | 'danger' {
  return severity === 'warning' ? 'warn' : severity
}

// The "New Acknowledgement" button sits in the Notifications tab's controls
// bar next to Save/Add Webhook, so the tab drives this panel's create
// dialog through this handle, the same pattern as WebhookSubscriptionsPanel.
defineExpose({ openCreate: onAdd })
</script>

<template>
  <div class="acknowledgements-panel">
    <p class="panel-description">
      {{ t('adminSettings.notifications.acknowledgements.description') }}
    </p>

    <DataTable
      :value="acknowledgements"
      data-key="id"
      size="small"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
    >
      <template #empty>
        <EmptyState :message="t('adminSettings.notifications.acknowledgements.noAcknowledgements')" />
      </template>

      <Column :header="t('adminSettings.notifications.acknowledgements.columns.text')">
        <template #body="{ data }: { data: Acknowledgement }">
          <span class="text-cell" v-tooltip.top="data.text">{{ data.text }}</span>
        </template>
      </Column>
      <Column
        :header="t('adminSettings.notifications.acknowledgements.columns.severity')"
        style="width: 8rem"
      >
        <template #body="{ data }: { data: Acknowledgement }">
          <Tag
            :severity="tagSeverity(data.severity)"
            :value="t(`adminSettings.notifications.severities.${data.severity}`)"
          />
        </template>
      </Column>
      <Column
        :header="t('adminSettings.notifications.acknowledgements.columns.showWhen')"
        style="width: 9rem"
      >
        <template #body="{ data }: { data: Acknowledgement }">
          {{
            data.show_when === 'immediately'
              ? t('adminSettings.notifications.acknowledgements.showWhenOptions.immediately')
              : t('adminSettings.notifications.acknowledgements.showWhenOptions.nextLogin')
          }}
        </template>
      </Column>
      <Column
        :header="t('adminSettings.notifications.acknowledgements.columns.enabled')"
        style="width: 6rem"
      >
        <template #body="{ data }: { data: Acknowledgement }">
          <ToggleSwitch
            :model-value="data.enabled"
            :disabled="!canWrite"
            @update:model-value="(val) => onToggleEnabled(data, val)"
          />
        </template>
      </Column>
      <Column
        :header="t('adminSettings.notifications.acknowledgements.columns.created')"
        style="width: 11rem"
      >
        <template #body="{ data }: { data: Acknowledgement }">
          {{ formatISODateTime(data.created_at) }}
        </template>
      </Column>
      <Column
        :header="t('adminSettings.notifications.acknowledgements.columns.progress')"
        style="width: 7rem"
      >
        <template #body="{ data }: { data: Acknowledgement }">
          {{ data.recipients_acknowledged }} / {{ data.recipients_total }}
        </template>
      </Column>
      <Column style="width: 8rem">
        <template #body="{ data }: { data: Acknowledgement }">
          <div class="row-actions">
            <Button
              icon="mdi mdi-account-multiple-outline"
              size="small"
              severity="secondary"
              text
              v-tooltip.top.focus="t('adminSettings.notifications.acknowledgements.recipients.title')"
              :aria-label="t('adminSettings.notifications.acknowledgements.recipients.title')"
              @click="onShowRecipients(data)"
            />
            <Button
              icon="mdi mdi-delete-outline"
              size="small"
              severity="danger"
              text
              :disabled="!canWrite"
              v-tooltip.top.focus="t('common.delete')"
              :aria-label="t('common.delete')"
              @click="onDelete(data)"
            />
          </div>
        </template>
      </Column>
    </DataTable>

    <AcknowledgementFormDialog v-model:visible="formVisible" @saved="load" />

    <AcknowledgementRecipientsDialog
      ref="recipientsDialog"
      v-model:visible="recipientsVisible"
      :acknowledgement="recipientsAcknowledgement"
    />
  </div>
</template>

<style scoped lang="scss">
.acknowledgements-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.panel-description {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.text-cell {
  display: block;
  max-width: 28rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
