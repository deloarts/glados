<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatISODate, formatISODateTime, toDayKey } from '@/core/utils/dates'
import { extractApiError } from '@/core/utils/errors'
import { localeEndonym } from '@/core/i18n/localeMessages'
import EmptyState from '@/shared/components/EmptyState.vue'
import { HelpDrawer } from '@/shared/help'
import { getMeetingSnapshot } from '../api/meetingsApi'
import type { MeetingResponse, MeetingSnapshotCardResponse, MeetingSnapshotResponse } from '../types/meetingResponse'
import { issueLabelText } from '../utils/meetingNotesReport'
import MeetingCardMarkdown from './MeetingCardMarkdown.vue'
import MeetingScopeChip from './MeetingScopeChip.vue'
import MeetingSnapshotChanges from './MeetingSnapshotChanges.vue'

/**
 * What one print, download or send contained, in two tabs: As Sent (or
 * Printed, Downloaded) shows its cards with their decisions and todos as
 * they went out, and Changes Since compares them with the notes today.
 */
const props = withDefaults(
  defineProps<{
    meeting: MeetingResponse
    snapshotId: number | null
    /** The tab the dialog opens on. */
    tab?: 'as' | 'changes'
    imageUrl?: (fileId: number) => string | undefined
    imageVersion?: number
  }>(),
  { tab: 'as', imageUrl: undefined, imageVersion: 0 },
)

const visible = defineModel<boolean>('visible', { default: false })
const explainVisible = ref(false)

const { t } = useI18n()

const snapshot = ref<MeetingSnapshotResponse | null>(null)
const loading = ref(false)
const errorMessage = ref('')
const activeTab = ref<'as' | 'changes'>('as')

watch(
  visible,
  async (open) => {
    if (!open) return
    activeTab.value = props.tab
    const id = props.snapshotId
    snapshot.value = null
    errorMessage.value = ''
    if (id === null) return
    loading.value = true
    try {
      snapshot.value = await getMeetingSnapshot(props.meeting.id, id)
    } catch (err) {
      errorMessage.value = extractApiError(err) ?? t('meetings.errors.unknown')
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)

const header = computed(() => {
  const current = snapshot.value
  if (!current) return t('meetings.snapshot.title')
  return t(`meetings.snapshot.header.${current.kind}`, { at: formatISODateTime(current.created) })
})

const facts = computed(() => {
  const current = snapshot.value
  if (!current) return ''
  const parts = [
    current.actor?.full_name ?? t('meetings.unknownUser'),
    issueLabelText(current.issue, current.issue.draft ? null : toDayKey(current.created), t, formatISODate),
    localeEndonym(current.language),
    current.options.include_internal ? t('meetings.snapshot.internalIncluded') : t('meetings.snapshot.internalOmitted'),
    `sha256 ${current.sha256.slice(0, 8)}…${current.sha256.slice(-4)}`,
  ]
  return parts.join(' · ')
})

const cards = computed(() =>
  [...(snapshot.value?.cards ?? [])].sort((a, b) => a.position - b.position || a.id - b.id),
)

function decisionsOf(card: MeetingSnapshotCardResponse) {
  return [...card.decisions].sort((a, b) => a.position - b.position || a.id - b.id)
}

function todosOf(card: MeetingSnapshotCardResponse) {
  return [...card.todos].sort((a, b) => a.position - b.position || a.id - b.id)
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="{ width: 'var(--dialog-width-lg)' }"
    data-testid="meeting-snapshot-dialog"
  >
    <template #header>
      <div class="snapshot-header">
        <span class="p-dialog-title">{{ header }}</span>
        <Button
          type="button"
          class="snapshot-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('meetings.snapshot.explain')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('meetings.snapshot.explain')"
          @click="explainVisible = true"
        />
      </div>
    </template>
    <Message v-if="errorMessage" severity="error" size="small">{{ errorMessage }}</Message>
    <div v-else-if="loading" class="snapshot-loading"><ProgressBar mode="indeterminate" class="loading-bar" /></div>
    <template v-else-if="snapshot">
      <div class="snapshot-facts">
        <span class="hint">{{ facts }}</span>
        <span v-if="snapshot.kind === 'sent'" class="hint" data-testid="meeting-snapshot-recipients">
          {{ t('meetings.distribution.sentTo', { recipients: snapshot.recipients.join(', ') }) }}
          <template v-if="snapshot.cc.length">
            · {{ t('meetings.distribution.cc', { recipients: snapshot.cc.join(', ') }) }}
          </template>
        </span>
        <span v-if="snapshot.subject" class="hint">{{ t('mail.compose.subject') }}: {{ snapshot.subject }}</span>
        <span v-if="snapshot.attachments.length" class="hint">
          {{ t('meetings.snapshot.attachments', { files: snapshot.attachments.map((file) => file.file_name).join(', ') }) }}
        </span>
      </div>
      <Tabs v-model:value="activeTab">
        <TabList>
          <Tab value="as" data-testid="meeting-snapshot-tab-as">{{ t(`meetings.snapshot.tabs.${snapshot.kind}`) }}</Tab>
          <Tab value="changes" data-testid="meeting-snapshot-tab-changes">{{ t('meetings.snapshot.tabs.changes') }}</Tab>
        </TabList>
        <TabPanels>
          <TabPanel value="as">
            <div class="snapshot-cards" data-testid="meeting-snapshot-cards">
              <EmptyState v-if="!cards.length" icon="mdi mdi-note-off-outline" :message="t('meetings.snapshot.noCards')" />
              <article v-for="card in cards" :key="card.id" class="snapshot-card">
                <header class="snapshot-head">
                  <MeetingScopeChip :scope="card.scope" :icon="card.scope_icon" :internal="card.internal" />
                  <span class="hint">
                    {{
                      t('meetings.card.created', {
                        name: card.creator?.full_name ?? t('meetings.unknownUser'),
                        at: formatISODateTime(card.created),
                      })
                    }}
                  </span>
                  <span v-if="card.changed" class="hint">
                    {{
                      t('meetings.card.changed', {
                        name: card.changed_by?.full_name ?? t('meetings.unknownUser'),
                        at: formatISODateTime(card.changed),
                      })
                    }}
                  </span>
                </header>
                <MeetingCardMarkdown :body="card.body" :image-url="imageUrl" :image-version="imageVersion" />
                <ul v-if="card.decisions.length" class="snapshot-list">
                  <li v-for="decision in decisionsOf(card)" :key="decision.id">
                    <i class="mdi mdi-gavel" aria-hidden="true" /> {{ decision.text }}
                  </li>
                </ul>
                <ul v-if="card.todos.length" class="snapshot-list">
                  <li v-for="todo in todosOf(card)" :key="todo.id">
                    <i
                      :class="todo.done ? 'mdi mdi-checkbox-marked-outline' : 'mdi mdi-checkbox-blank-outline'"
                      aria-hidden="true"
                    />
                    {{ todo.title }} ·
                    {{ todo.owners.map((owner) => owner.name).join(', ') || t('meetings.todos.noOwner') }} ·
                    {{ todo.due_date ? formatISODate(todo.due_date) : t('meetings.todos.noDue') }}
                  </li>
                </ul>
              </article>
            </div>
          </TabPanel>
          <TabPanel value="changes">
            <MeetingSnapshotChanges :snapshot="snapshot" :meeting="meeting" />
          </TabPanel>
        </TabPanels>
      </Tabs>
    </template>
    <template #footer>
      <Button :label="t('common.close')" severity="secondary" text @click="visible = false" />
    </template>
  </Dialog>
  <HelpDrawer v-model:visible="explainVisible" slug="workspace/meeting-distribution" anchor="distribution" />
</template>

<style scoped lang="scss">
.snapshot-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.snapshot-explain-button :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.snapshot-loading {
  display: flex;
  justify-content: center;
  padding: var(--space-5) 0;
}

.loading-bar {
  width: 50%;
  --p-progressbar-height: 3px;
}

.snapshot-facts {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin-bottom: var(--space-2);
}

.snapshot-cards {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.snapshot-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-md);
}

.snapshot-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.snapshot-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
}
</style>
