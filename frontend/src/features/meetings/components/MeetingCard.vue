<script setup lang="ts">
import { computed, nextTick, ref, useTemplateRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'

import { useAppToast } from '@/core/composables/useAppToast'
import { formatISODateTime } from '@/core/utils/dates'
import { apiErrorStatus, extractApiError } from '@/core/utils/errors'
import { deleteMeetingCard, updateMeetingCard } from '../api/meetingsApi'
import { useCardEditing } from '../composables/useCardEditing'
import { useCardHeartbeat } from '../composables/useCardPresence'
import { scopeIconClass } from '../utils/scopeIcons'
import type { TodoOwnerOption } from '../utils/todoOwners'
import MeetingCardDecisions from './MeetingCardDecisions.vue'
import MeetingCardEditor from './MeetingCardEditor.vue'
import MeetingCardHistoryDialog from './MeetingCardHistoryDialog.vue'
import MeetingCardMarkdown from './MeetingCardMarkdown.vue'
import MeetingCardTodos from './MeetingCardTodos.vue'
import MeetingMergeDialog from './MeetingMergeDialog.vue'
import MeetingScopePopover from './MeetingScopePopover.vue'
import type { MeetingCardResponse, MeetingResponse, MeetingScopeIcon } from '../types/meetingResponse'

/**
 * One card of the meeting notes: its scope with an optional icon, the
 * internal tag, who wrote and changed it, the text with its editor, its
 * decisions and its todos. The card saves on its own with its edit version,
 * keeps the text being written as a draft in the browser, announces its
 * editor to the other viewers and opens the merge when someone else saved
 * first.
 */
const props = defineProps<{
  meeting: MeetingResponse
  card: MeetingCardResponse
  canWrite: boolean
  /** Why the user may not change the notes, naming the missing permission. */
  writeBlocked: string
  /** The names of the other users editing this card now. */
  editors: string[]
  ownerOptions: TodoOwnerOption[]
  imageUrl: (fileId: number) => string | undefined
  imageVersion: number
  uploadImage: (file: File, cardId: number) => Promise<{ id: number; name: string } | null>
}>()

const emit = defineEmits<{
  updated: [card: MeetingCardResponse]
  changed: []
  deleted: [cardId: number]
}>()

defineSlots<{
  /** Extra tags after the internal tag, such as one for a change after sending. */
  tags?: () => unknown
}>()

const { t } = useI18n()
const toast = useAppToast()
const confirm = useConfirm()

const editable = computed(() => props.meeting.valid)
const canEdit = computed(() => editable.value && props.canWrite)
const owner = computed(() =>
  props.meeting.owner.kind === 'project' ? { project_id: props.meeting.owner.id } : { product_id: props.meeting.owner.id },
)

const editing = useCardEditing({
  meetingId: () => props.meeting.id,
  card: () => props.card,
  onSaved: (card) => emit('updated', card),
})
useCardHeartbeat(() => props.meeting.id, () => props.card.id, editing.editing)

const editor = useTemplateRef<{ focus: () => void }>('editor')
const scopePopover = useTemplateRef<{ open: (event: Event) => void }>('scopePopover')
const historyVisible = ref(false)

async function startEditing(): Promise<void> {
  if (!canEdit.value || editing.editing.value) return
  editing.start()
  await nextTick()
  editor.value?.focus()
}

defineExpose({ startEditing })

async function onSave(): Promise<void> {
  const saved = await editing.save()
  if (!saved && editing.error.value) {
    toast.error(scopeLabel.value, extractApiError(editing.error.value) ?? t('meetings.errors.unknown'))
  }
}

async function onSaveMerged(text: string): Promise<void> {
  await editing.saveMerged(text)
}

const mergeError = computed(() =>
  editing.error.value ? (extractApiError(editing.error.value) ?? t('meetings.errors.unknown')) : '',
)

const scopeLabel = computed(() => props.card.scope || t('meetings.card.noScope'))

async function onScopeApply(value: { scope: string | null; icon: MeetingScopeIcon | null }): Promise<void> {
  if (value.scope === props.card.scope && value.icon === props.card.scope_icon) return
  try {
    const saved = await updateMeetingCard(props.meeting.id, props.card.id, {
      scope: value.scope,
      scope_icon: value.icon,
      body: props.card.body,
      internal: props.card.internal,
      expected_edit_version: props.card.edit_version,
    })
    emit('updated', saved)
  } catch (err) {
    const message =
      apiErrorStatus(err) === 409 ? t('meetings.card.scopeConflict') : (extractApiError(err) ?? t('meetings.errors.unknown'))
    toast.error(scopeLabel.value, message)
    emit('changed')
  }
}

function askDelete(): void {
  confirm.require({
    header: t('meetings.card.deleteHeader'),
    message: t('meetings.card.deleteConfirm', { scope: scopeLabel.value }),
    icon: 'mdi mdi-delete-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary', text: true },
    acceptProps: { label: t('meetings.card.delete'), severity: 'danger', icon: 'mdi mdi-delete-outline' },
    accept: () => void runDelete(),
  })
}

async function runDelete(): Promise<void> {
  try {
    await deleteMeetingCard(props.meeting.id, props.card.id, props.card.edit_version)
    editing.stop()
    toast.success(scopeLabel.value, t('meetings.toasts.cardDeleted'))
    emit('deleted', props.card.id)
  } catch (err) {
    toast.error(scopeLabel.value, extractApiError(err) ?? t('meetings.errors.unknown'))
    emit('changed')
  }
}

// A click on a link in the text follows the link instead of editing.
function onReadClick(event: MouseEvent): void {
  if (event.target instanceof Element && event.target.closest('a')) return
  void startEditing()
}

const editorNames = computed(() => props.editors.join(', '))
const draftSavedAt = computed(() =>
  editing.storedDraft.value ? formatISODateTime(editing.storedDraft.value.savedAt) : '',
)
const iconClass = computed(() => scopeIconClass(props.card.scope_icon))
</script>

<template>
  <article
    :id="`card-${card.id}`"
    class="meeting-card"
    :class="{ editing: editing.editing.value, internal: card.internal }"
    :data-testid="`meeting-card-${card.id}`"
  >
    <Message
      v-if="canEdit && editing.draftState.value !== 'none'"
      :severity="editing.draftState.value === 'stale' ? 'warn' : 'info'"
      size="small"
      data-testid="meeting-card-draft"
    >
      <span>
        {{
          editing.draftState.value === 'stale'
            ? t('meetings.draft.stale', { at: draftSavedAt })
            : t('meetings.draft.restorable', { at: draftSavedAt })
        }}
      </span>
      <span class="draft-actions">
        <Button
          v-if="editing.draftState.value === 'restorable'"
          :label="t('meetings.draft.restore')"
          size="small"
          text
          data-testid="meeting-draft-restore"
          @click="editing.restoreDraft()"
        />
        <Button
          v-else
          :label="t('meetings.draft.merge')"
          size="small"
          text
          data-testid="meeting-draft-merge"
          @click="editing.mergeDraft()"
        />
        <Button
          :label="t('meetings.draft.discard')"
          size="small"
          severity="secondary"
          text
          data-testid="meeting-draft-discard"
          @click="editing.discardDraft()"
        />
      </span>
    </Message>

    <header class="card-head">
      <span v-tooltip.top="canEdit ? t('meetings.card.changeScope') : writeBlocked || undefined">
        <Button
          :icon="iconClass ?? undefined"
          :label="card.scope || t('meetings.card.addScope')"
          icon-pos="left"
          severity="secondary"
          :text="!card.scope"
          :outlined="!!card.scope"
          size="small"
          class="scope-button"
          :disabled="!canEdit"
          data-testid="meeting-card-scope"
          @click="scopePopover?.open($event)"
        />
      </span>
      <Tag v-if="card.internal" :value="t('meetings.card.internal')" icon="mdi mdi-lock-outline" severity="help" />
      <slot name="tags" />
      <Tag
        v-if="editors.length"
        :value="t('meetings.card.isEditing', { names: editorNames }, editors.length)"
        icon="mdi mdi-pencil-outline"
        severity="info"
        data-testid="meeting-card-presence"
      />
      <span class="card-actions">
        <template v-if="editing.editing.value">
          <div class="internal-toggle">
            <ToggleSwitch
              v-model="editing.internal.value"
              :input-id="`card-${card.id}-internal`"
              data-testid="meeting-card-internal"
            />
            <label :for="`card-${card.id}-internal`">{{ t('meetings.card.internalToggle') }}</label>
          </div>
          <Button
            :label="t('meetings.card.save')"
            icon="mdi mdi-check"
            size="small"
            :loading="editing.saving.value"
            data-testid="meeting-card-save"
            @click="onSave"
          />
          <Button
            :label="t('common.cancel')"
            severity="secondary"
            text
            size="small"
            :disabled="editing.saving.value"
            data-testid="meeting-card-cancel"
            @click="editing.stop()"
          />
        </template>
        <span v-if="editable && !editing.editing.value" v-tooltip.top="writeBlocked || undefined">
          <Button
            icon="mdi mdi-pencil"
            size="small"
            severity="secondary"
            text
            :disabled="!canWrite"
            :aria-label="t('meetings.card.edit')"
            data-testid="meeting-card-edit"
            @click="startEditing"
          />
        </span>
        <Button
          icon="mdi mdi-history"
          size="small"
          severity="secondary"
          text
          v-tooltip.top="t('meetings.card.history')"
          :aria-label="t('meetings.card.history')"
          data-testid="meeting-card-history-button"
          @click="historyVisible = true"
        />
        <span v-if="editable" v-tooltip.top="writeBlocked || undefined">
          <Button
            icon="mdi mdi-delete-outline"
            size="small"
            severity="danger"
            text
            :disabled="!canWrite"
            :aria-label="t('meetings.card.delete')"
            data-testid="meeting-card-delete"
            @click="askDelete"
          />
        </span>
      </span>
    </header>

    <div v-if="editing.editing.value" class="card-edit">
      <MeetingCardEditor
        ref="editor"
        v-model="editing.body.value"
        :image-url="imageUrl"
        :image-version="imageVersion"
        :upload-image="(file: File) => uploadImage(file, card.id)"
      />
    </div>
    <template v-else>
      <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -- the role is button while the card is editable, which the rule cannot see. -->
      <div
        v-if="card.body"
        class="card-read"
        :class="{ clickable: canEdit }"
        :role="canEdit ? 'button' : undefined"
        :tabindex="canEdit ? 0 : undefined"
        :title="canEdit ? t('meetings.card.clickToEdit') : undefined"
        @click="onReadClick"
        @keydown.enter="startEditing"
        @keydown.space.prevent="startEditing"
      >
        <MeetingCardMarkdown :body="card.body" :image-url="imageUrl" :image-version="imageVersion" />
      </div>
      <p v-else class="empty-note">{{ t('meetings.card.empty') }}</p>
    </template>

    <div class="card-sections">
      <MeetingCardDecisions
        :meeting-id="meeting.id"
        :card="card"
        :can-write="canWrite"
        :write-blocked="writeBlocked"
        :editable="editable"
        @changed="emit('changed')"
      />
      <MeetingCardTodos
        :meeting-id="meeting.id"
        :card="card"
        :owner-options="ownerOptions"
        :can-write="canWrite"
        :write-blocked="writeBlocked"
        :editable="editable"
        @changed="emit('changed')"
      />
    </div>

    <MeetingScopePopover
      ref="scopePopover"
      :scope="card.scope"
      :icon="card.scope_icon"
      :owner="owner"
      @apply="onScopeApply"
    />
    <MeetingMergeDialog
      v-model:visible="editing.merge.visible"
      :theirs="editing.merge.theirs"
      :mine="editing.merge.mine"
      :saving="editing.saving.value"
      :error="mergeError"
      @save="onSaveMerged"
      @cancel="editing.closeMerge()"
    />
    <MeetingCardHistoryDialog
      v-model:visible="historyVisible"
      :meeting-id="meeting.id"
      :card="card"
      :can-restore="canEdit"
      :restore-blocked="editable ? writeBlocked : t('meetings.readOnly')"
      @restored="emit('updated', $event)"
    />
  </article>
</template>

<style scoped lang="scss">
.meeting-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-lg);
  // A faint tint sets each card apart from the notes panel behind it.
  background: color-mix(in srgb, var(--p-content-hover-background) 50%, var(--p-content-background));
  scroll-margin-top: var(--space-4);

  &.internal {
    border-style: dashed;
  }

  &.editing {
    border-color: var(--p-primary-color);
  }
}

.card-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.card-actions {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  margin-left: auto;
}

.draft-actions {
  display: inline-flex;
  gap: var(--space-1);
  margin-left: var(--space-2);
}

.card-read.clickable {
  cursor: text;
}

.card-edit {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.internal-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-right: var(--space-2);
  font-size: var(--font-size-sm);
}

.card-sections {
  display: flex;
  flex-direction: column;
  margin-top: var(--space-1);

  // A divider above the decisions and one above the todos, with room on
  // either side of each.
  > * {
    padding-block: var(--space-4) var(--space-1);
    border-top: 1px solid var(--p-content-border-color);
  }

  > * + * {
    margin-top: var(--space-3);
  }
}
</style>
