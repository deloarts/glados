<script setup lang="ts">
import { computed, reactive, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { toLocalDayStart } from '@/core/utils/dates'
import type { TodoOwnerOption } from '../utils/todoOwners'
import type { MeetingTodoRequest } from '../types/meetingRequest'
import type { MeetingTodoResponse } from '../types/meetingResponse'

/**
 * The fields of a todo: what is to be done, who owns it, users or contacts
 * of the meeting, when it is due and an optional note. Used to add a todo to
 * a card and to edit one in place.
 */
const props = defineProps<{
  todo?: MeetingTodoResponse | null
  ownerOptions: TodoOwnerOption[]
  saving?: boolean
}>()

const emit = defineEmits<{ submit: [body: MeetingTodoRequest]; cancel: [] }>()

const { t } = useI18n()
const uid = useId()

const form = reactive<{ title: string; owners: string[]; due: Date | null; note: string }>({
  title: '',
  owners: [],
  due: null,
  note: '',
})

function reset(): void {
  const todo = props.todo
  form.title = todo?.title ?? ''
  form.owners =
    todo?.owners.map((owner) => (owner.user ? `u:${owner.user.id}` : `c:${owner.contact_id}`)) ?? []
  form.due = todo?.due_date ? toLocalDayStart(todo.due_date) : null
  form.note = todo?.note ?? ''
}

watch(() => props.todo, reset, { immediate: true })

const groupedOptions = computed(() => {
  const groups = [
    { label: t('meetings.todos.users'), items: props.ownerOptions.filter((option) => option.kind === 'user') },
    { label: t('meetings.todos.contacts'), items: props.ownerOptions.filter((option) => option.kind === 'contact') },
  ]
  return groups.filter((group) => group.items.length)
})

function dateKey(day: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${day.getFullYear()}-${pad(day.getMonth() + 1)}-${pad(day.getDate())}`
}

function submit(): void {
  const title = form.title.trim()
  if (!title) return
  emit('submit', {
    title,
    note: form.note.trim() || null,
    due_date: form.due ? dateKey(form.due) : null,
    owners: form.owners.map((value) =>
      value.startsWith('u:') ? { user_id: Number(value.slice(2)) } : { contact_id: Number(value.slice(2)) },
    ),
  })
  if (!props.todo) reset()
}
</script>

<template>
  <form class="todo-form" data-testid="meeting-todo-form" @submit.prevent="submit">
    <InputText
      :id="`${uid}-title`"
      v-model="form.title"
      maxlength="300"
      size="small"
      :placeholder="t('meetings.todos.newTodo')"
      :aria-label="t('meetings.todos.title')"
      class="todo-title-input"
      data-testid="meeting-todo-title"
    />
    <MultiSelect
      v-model="form.owners"
      :options="groupedOptions"
      option-label="label"
      option-value="value"
      option-group-label="label"
      option-group-children="items"
      filter
      display="chip"
      size="small"
      :placeholder="t('meetings.todos.owners')"
      :aria-label="t('meetings.todos.owners')"
      class="todo-owners-input"
      data-testid="meeting-todo-owners"
    />
    <DatePicker
      v-model="form.due"
      size="small"
      show-icon
      show-clear
      :placeholder="t('meetings.todos.due')"
      :aria-label="t('meetings.todos.due')"
      class="todo-due-input"
    />
    <!-- The note and the buttons share the second line, the buttons at its end. -->
    <div class="todo-form-row">
      <InputText
        v-model="form.note"
        maxlength="4000"
        size="small"
        :placeholder="t('meetings.todos.notePlaceholder')"
        :aria-label="t('meetings.todos.note')"
        class="todo-note-input"
      />
      <div class="todo-form-actions">
        <Button
          v-if="todo"
          type="button"
          :label="t('common.cancel')"
          severity="secondary"
          text
          size="small"
          @click="emit('cancel')"
        />
        <Button
          type="submit"
          :label="todo ? t('meetings.todos.save') : t('meetings.todos.add')"
          :icon="todo ? 'mdi mdi-check' : 'mdi mdi-plus'"
          size="small"
          severity="secondary"
          :loading="saving"
          :disabled="!form.title.trim()"
          data-testid="meeting-todo-submit"
        />
      </div>
    </div>
  </form>
</template>

<style scoped lang="scss">
.todo-form {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.todo-title-input {
  flex: 2 1 14rem;
}

.todo-owners-input {
  flex: 1 1 12rem;
  min-width: 0;
}

.todo-due-input {
  flex: 0 1 10rem;
}

.todo-form-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex: 1 1 100%;
  min-width: 0;
}

.todo-note-input {
  flex: 1 1 auto;
  min-width: 0;
}

.todo-form-actions {
  display: flex;
  flex-shrink: 0;
  gap: var(--space-1);
}
</style>
