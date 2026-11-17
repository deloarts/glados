<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAppToast } from '@/core/composables/useAppToast'
import { formatISODateTime } from '@/core/utils/dates'
import { extractApiError } from '@/core/utils/errors'
import { getMeetingCardRevisions, restoreMeetingCardRevision } from '../api/meetingsApi'
import { lineDiff } from '../utils/lineDiff'
import MeetingLineDiff from './MeetingLineDiff.vue'
import MeetingScopeChip from './MeetingScopeChip.vue'
import type { MeetingCardResponse, MeetingCardRevisionResponse } from '../types/meetingResponse'

/**
 * The versions of a card, newest first, each shown as the lines it changed
 * against the version before. Saves by the same person within ten minutes
 * count as one version. Restore This Version saves the old text as a new
 * version, so nothing is lost.
 */
const props = defineProps<{
  meetingId: number
  card: MeetingCardResponse
  canRestore: boolean
  restoreBlocked: string
}>()

const emit = defineEmits<{ restored: [card: MeetingCardResponse] }>()
const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const toast = useAppToast()

const revisions = ref<MeetingCardRevisionResponse[]>([])
const selected = ref(0)
const loading = ref(false)
const restoring = ref(false)
const errorMessage = ref('')

watch(visible, async (open) => {
  if (!open) return
  loading.value = true
  errorMessage.value = ''
  selected.value = 0
  try {
    revisions.value = await getMeetingCardRevisions(props.meetingId, props.card.id)
  } catch (err) {
    revisions.value = []
    errorMessage.value = extractApiError(err) ?? t('meetings.errors.unknown')
  } finally {
    loading.value = false
  }
})

const current = computed(() => revisions.value[selected.value] ?? null)
const previous = computed(() => revisions.value[selected.value + 1] ?? null)
const diff = computed(() => lineDiff(previous.value?.body ?? '', current.value?.body ?? ''))

function describe(revision: MeetingCardRevisionResponse): string {
  return [
    revision.scope ? t('meetings.cardHistory.scope', { scope: revision.scope }) : t('meetings.card.noScope'),
    revision.scope_icon ? t(`meetings.scopeIcons.${revision.scope_icon}`) : t('meetings.cardHistory.noIcon'),
    revision.internal ? t('meetings.card.internal') : t('meetings.cardHistory.notInternal'),
  ].join(', ')
}

const metaChange = computed(() => {
  if (!current.value || !previous.value) return null
  const before = describe(previous.value)
  const after = describe(current.value)
  return before === after ? null : `${before} → ${after}`
})

function versionNumber(index: number): number {
  return revisions.value.length - index
}

async function onRestore(): Promise<void> {
  const revision = current.value
  if (!revision || selected.value === 0) return
  restoring.value = true
  errorMessage.value = ''
  try {
    const card = await restoreMeetingCardRevision(props.meetingId, props.card.id, revision.id, props.card.edit_version)
    toast.success(
      card.scope || t('meetings.card.noScope'),
      t('meetings.cardHistory.restored', { version: versionNumber(selected.value) }),
    )
    visible.value = false
    emit('restored', card)
  } catch (err) {
    errorMessage.value = extractApiError(err) ?? t('meetings.errors.unknown')
  } finally {
    restoring.value = false
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('meetings.cardHistory.title', { scope: card.scope || t('meetings.card.noScope') })"
    :style="{ width: 'var(--dialog-width-lg)' }"
    data-testid="meeting-card-history"
  >
    <p class="card-origin hint" data-testid="meeting-card-origin">
      <span>
        {{ t('meetings.card.created', { name: card.creator?.full_name ?? t('meetings.unknownUser'), at: formatISODateTime(card.created) }) }}
      </span>
      <span v-if="card.changed">
        {{
          t('meetings.card.changed', {
            name: card.changed_by?.full_name ?? t('meetings.unknownUser'),
            at: formatISODateTime(card.changed),
          })
        }}
      </span>
    </p>
    <div v-if="loading" class="empty-note">{{ t('meetings.cardHistory.loading') }}</div>
    <div v-else-if="revisions.length" class="history-split">
      <div class="revision-list" role="listbox" :aria-label="t('meetings.cardHistory.versions')">
        <button
          v-for="(revision, index) in revisions"
          :key="revision.id"
          type="button"
          role="option"
          class="revision"
          :class="{ selected: index === selected }"
          :aria-selected="index === selected"
          :data-testid="`meeting-revision-${index}`"
          @click="selected = index"
        >
          <span class="revision-title">
            {{ t('meetings.cardHistory.version', { version: versionNumber(index) }) }}
            <Tag v-if="index === 0" :value="t('meetings.cardHistory.current')" severity="success" />
          </span>
          <small class="text-muted">
            {{ revision.author?.full_name ?? t('meetings.unknownUser') }} · {{ formatISODateTime(revision.saved_at) }}
          </small>
        </button>
      </div>
      <div v-if="current" class="revision-detail">
        <div class="revision-head">
          <MeetingScopeChip :scope="current.scope" :icon="current.scope_icon" :internal="current.internal" />
          <span class="hint">
            {{
              previous
                ? t('meetings.cardHistory.changesFrom', {
                    from: versionNumber(selected + 1),
                    to: versionNumber(selected),
                  })
                : t('meetings.cardHistory.firstVersion')
            }}
          </span>
        </div>
        <Message v-if="metaChange" severity="info" size="small">{{ metaChange }}</Message>
        <MeetingLineDiff :lines="diff" />
      </div>
    </div>
    <div v-else class="empty-note">{{ t('meetings.cardHistory.none') }}</div>

    <template #footer>
      <span class="footer-hint hint">{{ t('meetings.cardHistory.mergeHint') }}</span>
      <Message v-if="errorMessage" severity="error" size="small" class="footer-error">{{ errorMessage }}</Message>
      <Button :label="t('common.close')" severity="secondary" text @click="visible = false" />
      <span v-tooltip.top="restoreBlocked || undefined">
        <Button
          :label="t('meetings.cardHistory.restore')"
          icon="mdi mdi-restore"
          :loading="restoring"
          :disabled="!canRestore || selected === 0 || !current"
          data-testid="meeting-revision-restore"
          @click="onRestore"
        />
      </span>
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.card-origin {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1) var(--space-4);
  margin: 0 0 var(--space-3);
}

.history-split {
  display: grid;
  grid-template-columns: 14rem minmax(0, 1fr);
  gap: var(--space-4);
}

.revision-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  max-height: 28rem;
  overflow-y: auto;
}

.revision {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-1);
  padding: var(--space-2);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-md);
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;

  &.selected {
    border-color: var(--p-primary-color);
    background: var(--p-highlight-background);
  }
}

.revision-title {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-weight: 600;
}

.revision-detail {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
}

.revision-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.footer-hint {
  margin-right: auto;
}

.footer-error {
  flex: 1 1 auto;
  align-self: center;
}
</style>
