<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { formatISODateTime } from '@/core/utils/dates'
import { extractApiError } from '@/core/utils/errors'
import { useLayoutStore } from '@/core/stores/layoutStore'
import EmptyState from '@/shared/components/EmptyState.vue'
import { getMeetingHistory } from '../api/meetingsApi'
import type { MeetingEventResponse } from '../types/meetingResponse'

/**
 * The history of a meeting, newest first: created and edited, cards, todos
 * and files added, changed or removed, printed, downloaded and sent, marked
 * invalid and restored. A print, download or send links to the snapshot of
 * what went out once `canOpenSnapshots` is set; the page then opens it from
 * the `open-snapshot` event.
 */
const props = withDefaults(defineProps<{ meetingId: number; meetingNumber: string; canOpenSnapshots?: boolean }>(), {
  canOpenSnapshots: false,
})

const emit = defineEmits<{ 'open-snapshot': [event: MeetingEventResponse] }>()
const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const events = ref<MeetingEventResponse[]>([])
const loading = ref(false)
const errorMessage = ref('')

watch(visible, async (open) => {
  if (!open) return
  loading.value = true
  errorMessage.value = ''
  try {
    events.value = await getMeetingHistory(props.meetingId)
  } catch (err) {
    events.value = []
    errorMessage.value = extractApiError(err) ?? t('meetings.errors.unknown')
  } finally {
    loading.value = false
  }
})

const DISTRIBUTION_KINDS = new Set(['printed', 'downloaded', 'sent'])

function hasSnapshot(event: MeetingEventResponse): boolean {
  return DISTRIBUTION_KINDS.has(event.kind) && typeof event.details?.snapshot_id === 'number'
}

function describe(event: MeetingEventResponse): string {
  const what = t(`meetings.history.kinds.${event.kind}`)
  return event.summary ? `${what}: ${event.summary}` : what
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('meetings.history.title', { number: meetingNumber })"
    :style="{ width: 'var(--dialog-width-lg)' }"
    data-testid="meeting-history-dialog"
  >
    <Message v-if="errorMessage" severity="error" size="small">{{ errorMessage }}</Message>
    <DataTable
      :value="events"
      :loading="loading"
      data-key="id"
      size="small"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
      scrollable
      scroll-height="28rem"
    >
      <template #empty>
        <EmptyState v-if="!loading" icon="mdi mdi-history" :message="t('meetings.history.empty')" />
      </template>
      <Column header="#" body-class="row-number" class="column-fit">
        <template #body="{ index }">{{ index + 1 }}</template>
      </Column>
      <Column :header="t('meetings.history.when')" class="column-fit">
        <template #body="{ data }: { data: MeetingEventResponse }">{{ formatISODateTime(data.at) }}</template>
      </Column>
      <Column :header="t('meetings.history.who')" class="column-fit">
        <template #body="{ data }: { data: MeetingEventResponse }">
          {{ data.actor?.full_name ?? t('meetings.unknownUser') }}
        </template>
      </Column>
      <Column :header="t('meetings.history.what')">
        <template #body="{ data }: { data: MeetingEventResponse }">{{ describe(data) }}</template>
      </Column>
      <Column class="column-fit">
        <template #body="{ data }: { data: MeetingEventResponse }">
          <Button
            v-if="canOpenSnapshots && hasSnapshot(data)"
            :label="t('meetings.history.snapshot')"
            icon="mdi mdi-eye-outline"
            size="small"
            text
            :data-testid="`meeting-history-snapshot-${data.id}`"
            @click="emit('open-snapshot', data)"
          />
        </template>
      </Column>
    </DataTable>
    <template #footer>
      <span class="footer-hint hint">{{ t('meetings.history.cardHint') }}</span>
      <Button :label="t('common.close')" severity="secondary" text @click="visible = false" />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.footer-hint {
  margin-right: auto;
}
</style>
