<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import { storeToRefs } from 'pinia'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { formatISODateTime } from '@/core/utils/dates'
import { getAcknowledgementRecipients } from '../api/getAcknowledgementRecipients'
import type { Acknowledgement, AcknowledgementRecipient } from '../types/acknowledgementTypes'
import EmptyState from '@/shared/components/EmptyState.vue'

const { t } = useI18n()
const appToast = useAppToast()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const visible = defineModel<boolean>('visible', { required: true })

const props = defineProps<{
  acknowledgement: Acknowledgement | null
}>()

const recipients = ref<AcknowledgementRecipient[]>([])
const loading = ref(false)
watchLoadingBar(loading)

async function load(): Promise<void> {
  if (!props.acknowledgement) return
  loading.value = true
  try {
    recipients.value = await getAcknowledgementRecipients(props.acknowledgement.public_id)
  } catch {
    appToast.error(t('adminSettings.notifications.acknowledgements.recipients.loadFailed'))
  } finally {
    loading.value = false
  }
}

watch(visible, (open) => {
  if (open) void load()
})

// AcknowledgementsPanel already refetches the row list on the live
// 'announcements' signal, but this dialog is a separately-open overlay, so it
// needs its own way back in to pick up confirmations arriving while an
// admin is watching it.
defineExpose({ reload: load })
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('adminSettings.notifications.acknowledgements.recipients.title')"
    style="width: var(--dialog-width-md)"
  >
    <DataTable
      :value="recipients"
      data-key="user_id"
      size="small"
      :loading="loading"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
    >
      <template #empty>
        <EmptyState :message="t('adminSettings.notifications.acknowledgements.recipients.empty')" />
      </template>

      <Column
        field="full_name"
        :header="t('adminSettings.notifications.acknowledgements.recipients.name')"
      />
      <Column
        field="username"
        :header="t('adminSettings.notifications.acknowledgements.recipients.username')"
      />
      <Column :header="t('adminSettings.notifications.acknowledgements.recipients.acknowledgedAt')">
        <template #body="{ data }: { data: AcknowledgementRecipient }">
          <span v-if="data.acknowledged_at">{{ formatISODateTime(data.acknowledged_at) }}</span>
          <Tag
            v-else
            severity="warn"
            :value="t('adminSettings.notifications.acknowledgements.recipients.pending')"
          />
        </template>
      </Column>
    </DataTable>
  </Dialog>
</template>
