<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'

import { useAppToast } from '@/core/composables/useAppToast'
import { extractApiError } from '@/core/utils/errors'
import { createMeetingDecision, deleteMeetingDecision, updateMeetingDecision } from '../api/meetingsApi'
import type { MeetingCardResponse, MeetingDecisionResponse } from '../types/meetingResponse'

/**
 * The decisions of a card, listed next to its todos. The printed notes
 * repeat them in a summary of their own.
 */
const props = defineProps<{
  meetingId: number
  card: MeetingCardResponse
  canWrite: boolean
  writeBlocked: string
  editable: boolean
}>()

const emit = defineEmits<{ changed: [] }>()

const { t } = useI18n()
const toast = useAppToast()
const confirm = useConfirm()

const newText = ref('')
const editingId = ref<number | null>(null)
const editText = ref('')
const saving = ref(false)

async function run(label: string, action: () => Promise<unknown>): Promise<boolean> {
  saving.value = true
  try {
    await action()
    emit('changed')
    return true
  } catch (err) {
    toast.error(label, extractApiError(err) ?? t('meetings.errors.unknown'))
    return false
  } finally {
    saving.value = false
  }
}

async function onAdd(): Promise<void> {
  const text = newText.value.trim()
  if (!text) return
  if (await run(text, () => createMeetingDecision(props.meetingId, props.card.id, { text }))) newText.value = ''
}

function startEdit(decision: MeetingDecisionResponse): void {
  editingId.value = decision.id
  editText.value = decision.text
}

async function onSaveEdit(decision: MeetingDecisionResponse): Promise<void> {
  const text = editText.value.trim()
  if (!text) return
  const body = { text, position: decision.position }
  if (await run(text, () => updateMeetingDecision(props.meetingId, decision.id, body))) editingId.value = null
}

function askDelete(decision: MeetingDecisionResponse): void {
  confirm.require({
    header: t('meetings.decisions.deleteHeader'),
    message: t('meetings.decisions.deleteConfirm'),
    icon: 'mdi mdi-delete-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary', text: true },
    acceptProps: { label: t('meetings.decisions.delete'), severity: 'danger', icon: 'mdi mdi-delete-outline' },
    accept: () => void run(decision.text, () => deleteMeetingDecision(props.meetingId, decision.id)),
  })
}
</script>

<template>
  <section class="card-section" data-testid="meeting-card-decisions">
    <header class="section-head">
      <i class="mdi mdi-gavel" aria-hidden="true" />
      <span class="section-title">{{ t('meetings.decisions.heading') }}</span>
    </header>
    <ol v-if="card.decisions.length" class="decision-list">
      <li v-for="(decision, index) in card.decisions" :key="decision.id" class="decision-row" data-testid="meeting-decision-row">
        <span class="decision-number">{{ index + 1 }}.</span>
        <template v-if="editingId === decision.id">
          <InputText
            v-model="editText"
            maxlength="2000"
            size="small"
            :aria-label="t('meetings.decisions.text')"
            class="decision-input"
            @keydown.enter.prevent="onSaveEdit(decision)"
          />
          <Button :label="t('common.cancel')" size="small" severity="secondary" text @click="editingId = null" />
          <Button
            :label="t('meetings.decisions.save')"
            icon="mdi mdi-check"
            size="small"
            severity="secondary"
            :loading="saving"
            @click="onSaveEdit(decision)"
          />
        </template>
        <template v-else>
          <span class="decision-text">{{ decision.text }}</span>
          <span v-if="editable" class="row-actions">
            <span v-tooltip.top="writeBlocked || undefined">
              <Button
                icon="mdi mdi-pencil"
                size="small"
                severity="secondary"
                text
                :disabled="!canWrite"
                :aria-label="t('meetings.decisions.edit')"
                @click="startEdit(decision)"
              />
            </span>
            <span v-tooltip.top="writeBlocked || undefined">
              <Button
                icon="mdi mdi-delete-outline"
                size="small"
                severity="danger"
                text
                :disabled="!canWrite"
                :aria-label="t('meetings.decisions.delete')"
                @click="askDelete(decision)"
              />
            </span>
          </span>
        </template>
      </li>
    </ol>
    <p v-else class="empty-note">{{ t('meetings.decisions.none') }}</p>
    <form v-if="editable" class="decision-add" @submit.prevent="onAdd">
      <InputText
        v-model="newText"
        maxlength="2000"
        size="small"
        :disabled="!canWrite"
        :placeholder="t('meetings.decisions.newDecision')"
        :aria-label="t('meetings.decisions.text')"
        class="decision-input"
        data-testid="meeting-decision-text"
      />
      <span v-tooltip.top="writeBlocked || undefined">
        <Button
          type="submit"
          :label="t('meetings.decisions.add')"
          icon="mdi mdi-plus"
          size="small"
          severity="secondary"
          :disabled="!canWrite || !newText.trim()"
          :loading="saving"
        />
      </span>
    </form>
  </section>
</template>

<style scoped lang="scss">
.card-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.section-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--p-text-muted-color);
}

.section-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  text-transform: uppercase;
}

.decision-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

// The number, the text and the actions on one line, the actions at the end.
.decision-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 2.25rem;
  padding: 0 var(--space-2);
  border-radius: var(--p-border-radius-sm);

  &:hover {
    background: var(--p-content-hover-background);
  }

  .row-actions {
    margin-left: auto;
  }
}

.decision-number {
  flex-shrink: 0;
  min-width: 1.25rem;
  color: var(--p-text-muted-color);
  font-variant-numeric: tabular-nums;
}

.decision-text {
  flex: 1 1 auto;
  min-width: 0;
  overflow-wrap: anywhere;
}

.decision-add {
  display: flex;
  gap: var(--space-2);
}

.decision-input {
  flex: 1 1 auto;
  min-width: 0;
}
</style>
