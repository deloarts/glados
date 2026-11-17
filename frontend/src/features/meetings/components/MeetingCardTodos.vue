<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'

import { useAppToast } from '@/core/composables/useAppToast'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { formatISODate, todayKey } from '@/core/utils/dates'
import { extractApiError } from '@/core/utils/errors'
import { createMeetingTodo, deleteMeetingTodo, setMeetingTodoDone, updateMeetingTodo } from '../api/meetingsApi'
import { ownedOnlyByContacts } from '../utils/todoOwners'
import type { TodoOwnerOption } from '../utils/todoOwners'
import MeetingTodoForm from './MeetingTodoForm.vue'
import type { MeetingTodoRequest } from '../types/meetingRequest'
import type { MeetingCardResponse, MeetingTodoResponse } from '../types/meetingResponse'

/**
 * The todos of a card: what is to be done, by whom and when, ticked off for
 * everyone at once. Owners may tick their own todos without write:meetings.
 * A todo only contacts own is marked, since it shows on no todo page.
 */
const props = defineProps<{
  meetingId: number
  card: MeetingCardResponse
  ownerOptions: TodoOwnerOption[]
  canWrite: boolean
  /** Why editing is not allowed, naming the missing permission. */
  writeBlocked: string
  /** False on an invalid meeting, whose notes are read-only. */
  editable: boolean
}>()

const emit = defineEmits<{ changed: [] }>()

const { t } = useI18n()
const toast = useAppToast()
const confirm = useConfirm()
const currentUserStore = useCurrentUserStore()

const editingId = ref<number | null>(null)
const saving = ref(false)
const busy = ref<Set<number>>(new Set())
const today = todayKey()

const doneCount = computed(() => props.card.todos.filter((todo) => todo.done).length)

function isOwner(todo: MeetingTodoResponse): boolean {
  const userId = currentUserStore.user?.id
  return todo.owners.some((owner) => owner.user?.id === userId)
}

function canTick(todo: MeetingTodoResponse): boolean {
  return props.editable && (props.canWrite || isOwner(todo))
}

function dueClass(todo: MeetingTodoResponse): string {
  if (todo.done || !todo.due_date) return ''
  if (todo.due_date < today) return 'overdue'
  return todo.due_date === today ? 'due-today' : ''
}

function dueLabel(todo: MeetingTodoResponse): string {
  if (!todo.due_date) return t('meetings.todos.noDue')
  return todo.due_date === today ? t('meetings.todos.today') : formatISODate(todo.due_date)
}

async function run(label: string, action: () => Promise<unknown>): Promise<boolean> {
  try {
    await action()
    emit('changed')
    return true
  } catch (err) {
    toast.error(label, extractApiError(err) ?? t('meetings.errors.unknown'))
    return false
  }
}

async function onTick(todo: MeetingTodoResponse, done: boolean): Promise<void> {
  busy.value = new Set(busy.value).add(todo.id)
  await run(todo.title, () => setMeetingTodoDone(props.meetingId, todo.id, done))
  const next = new Set(busy.value)
  next.delete(todo.id)
  busy.value = next
}

async function onAdd(body: MeetingTodoRequest): Promise<void> {
  saving.value = true
  await run(body.title, () => createMeetingTodo(props.meetingId, props.card.id, body))
  saving.value = false
}

async function onEdit(todo: MeetingTodoResponse, body: MeetingTodoRequest): Promise<void> {
  saving.value = true
  if (await run(body.title, () => updateMeetingTodo(props.meetingId, todo.id, body))) editingId.value = null
  saving.value = false
}

function askDelete(todo: MeetingTodoResponse): void {
  confirm.require({
    header: t('meetings.todos.deleteHeader'),
    message: t('meetings.todos.deleteConfirm', { title: todo.title }),
    icon: 'mdi mdi-delete-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary', text: true },
    acceptProps: { label: t('meetings.todos.delete'), severity: 'danger', icon: 'mdi mdi-delete-outline' },
    accept: () => void run(todo.title, () => deleteMeetingTodo(props.meetingId, todo.id)),
  })
}
</script>

<template>
  <section class="card-section" data-testid="meeting-card-todos">
    <header class="section-head">
      <i class="mdi mdi-checkbox-marked-circle-outline" aria-hidden="true" />
      <span class="section-title">{{ t('meetings.todos.heading') }}</span>
      <Tag
        v-if="card.todos.length"
        :value="t('meetings.todos.doneCount', { done: doneCount, total: card.todos.length })"
        severity="secondary"
      />
    </header>

    <ul v-if="card.todos.length" class="todo-list">
      <li
        v-for="todo in card.todos"
        :key="todo.id"
        class="todo-row"
        :class="{ done: todo.done, editing: editingId === todo.id }"
        data-testid="meeting-todo-row"
      >
        <template v-if="editingId === todo.id">
          <MeetingTodoForm
            :todo="todo"
            :owner-options="ownerOptions"
            :saving="saving"
            @submit="onEdit(todo, $event)"
            @cancel="editingId = null"
          />
        </template>
        <template v-else>
          <span v-tooltip.top="canTick(todo) || !editable ? undefined : writeBlocked || undefined">
            <Checkbox
              :model-value="todo.done"
              binary
              :input-id="`todo-${todo.id}`"
              :disabled="!canTick(todo) || busy.has(todo.id)"
              :aria-label="todo.done ? t('meetings.todos.reopen') : t('meetings.todos.markDone')"
              :data-testid="`meeting-todo-done-${todo.id}`"
              @update:model-value="onTick(todo, Boolean($event))"
            />
          </span>
          <div class="todo-main">
            <label :for="`todo-${todo.id}`" class="todo-title">{{ todo.title }}</label>
            <small v-if="todo.note" class="text-muted">{{ todo.note }}</small>
            <small v-if="todo.done && todo.done_by" class="text-muted">
              {{ t('meetings.todos.doneBy', { name: todo.done_by.full_name }) }}
            </small>
          </div>
          <span class="todo-owners">
            <Tag
              v-for="(owner, index) in todo.owners"
              :key="index"
              :value="owner.name"
              :icon="owner.user ? 'mdi mdi-account-outline' : 'mdi mdi-card-account-mail-outline'"
              severity="secondary"
            />
            <Tag
              v-if="ownedOnlyByContacts(todo)"
              v-tooltip.top="t('meetings.todos.contactOnlyHint')"
              :value="t('meetings.todos.contactOnly')"
              icon="mdi mdi-eye-off-outline"
              severity="info"
              data-testid="meeting-todo-contact-only"
            />
          </span>
          <span class="todo-due" :class="dueClass(todo)">
            <i class="mdi mdi-calendar-outline" aria-hidden="true" />
            {{ dueLabel(todo) }}
          </span>
          <span v-if="editable" class="row-actions">
            <span v-tooltip.top="writeBlocked || undefined">
              <Button
                icon="mdi mdi-pencil"
                size="small"
                severity="secondary"
                text
                :disabled="!canWrite"
                :aria-label="t('meetings.todos.edit')"
                @click="editingId = todo.id"
              />
            </span>
            <span v-tooltip.top="writeBlocked || undefined">
              <Button
                icon="mdi mdi-delete-outline"
                size="small"
                severity="danger"
                text
                :disabled="!canWrite"
                :aria-label="t('meetings.todos.delete')"
                @click="askDelete(todo)"
              />
            </span>
          </span>
        </template>
      </li>
    </ul>
    <p v-else class="empty-note">{{ t('meetings.todos.none') }}</p>

    <template v-if="editable">
      <MeetingTodoForm v-if="canWrite" :owner-options="ownerOptions" :saving="saving" @submit="onAdd" />
      <span v-else v-tooltip.top="writeBlocked || undefined" class="todo-add">
        <Button :label="t('meetings.todos.add')" icon="mdi mdi-plus" size="small" severity="secondary" disabled />
      </span>
    </template>
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

.todo-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.todo-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  min-height: 2.25rem;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--p-border-radius-sm);

  &:not(.editing):hover {
    background: var(--p-content-hover-background);
  }

  &.done .todo-title {
    color: var(--p-text-muted-color);
    text-decoration: line-through;
  }
}

.todo-main {
  display: flex;
  flex-direction: column;
  flex: 1 1 12rem;
  min-width: 0;
}

.todo-owners {
  display: inline-flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.todo-due {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  white-space: nowrap;

  &.overdue {
    color: var(--p-red-500);
    font-weight: 600;
  }

  &.due-today {
    color: var(--p-orange-500);
    font-weight: 600;
  }
}

.todo-add {
  align-self: flex-end;
}
</style>
