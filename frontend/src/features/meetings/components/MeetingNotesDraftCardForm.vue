<script setup lang="ts">
import { computed, useId } from 'vue'
import { useI18n } from 'vue-i18n'

import { toLocalDayStart } from '@/core/utils/dates'
import { SCOPE_ICON_VALUES, scopeIconClass } from '../utils/scopeIcons'
import { ownerLeftOut } from '../utils/meetingNotesDraft'
import type { PersonChoice, ReviewCard } from '../utils/meetingNotesDraft'

/**
 * One card of a draft of meeting notes under review: whether it is kept,
 * its scope and icon, its text, whether it is internal, its decisions and
 * its todos. The agent's note for the reviewer shows above it and is never
 * applied. A todo's owners are the names the notes carry; how each is
 * matched is decided once for the whole draft in the people section, and an
 * owner left out there is marked here.
 */
const card = defineModel<ReviewCard>({ required: true })
const props = defineProps<{
  index: number
  people: Record<string, PersonChoice>
  /** The label of each name as it is matched now. */
  personLabel: (written: string) => string
}>()

const { t } = useI18n()
const uid = useId()

const iconOptions = computed(() =>
  SCOPE_ICON_VALUES.map((value) => ({ value, label: t(`meetings.scopeIcons.${value}`), icon: scopeIconClass(value) })),
)

function dayKey(day: Date): string {
  const month = String(day.getMonth() + 1).padStart(2, '0')
  const date = String(day.getDate()).padStart(2, '0')
  return `${day.getFullYear()}-${month}-${date}`
}

function dueOf(index: number): Date | null {
  const due = card.value.todos[index]?.due_date
  return due ? toLocalDayStart(due) : null
}

function setDue(index: number, value: Date | Date[] | (Date | null)[] | null | undefined): void {
  const todo = card.value.todos[index]
  if (!todo) return
  todo.due_date = value instanceof Date ? dayKey(value) : null
}

function addDecision(): void {
  card.value.decisions.push('')
}

function removeDecision(index: number): void {
  card.value.decisions.splice(index, 1)
}

function addTodo(): void {
  card.value.todos.push({ title: '', note: null, due_date: null, owners: [] })
}

function removeTodo(index: number): void {
  card.value.todos.splice(index, 1)
}
</script>

<template>
  <div class="draft-card" :class="{ excluded: !card.include }" :data-testid="`draft-card-${index}`">
    <div class="draft-card-head">
      <ToggleSwitch
        v-model="card.include"
        :input-id="`${uid}-include`"
        :data-testid="`draft-card-include-${index}`"
      />
      <label :for="`${uid}-include`" class="draft-card-title">
        {{ t('meetings.drafts.cardTitle', { number: index + 1 }) }}
      </label>
      <Tag v-if="!card.include" :value="t('meetings.drafts.leftOut')" severity="secondary" />
    </div>

    <Message v-if="card.review_note" severity="warn" :data-testid="`draft-card-note-${index}`">
      <span class="note-label">{{ t('meetings.drafts.agentNote') }}</span>
      {{ card.review_note }}
    </Message>

    <template v-if="card.include">
      <div class="form-grid">
        <div class="field">
          <label :for="`${uid}-scope`">{{ t('meetings.drafts.scope') }}</label>
          <InputText v-model="card.scope" :id="`${uid}-scope`" maxlength="80" fluid />
        </div>
        <div class="field">
          <label :id="`${uid}-icon-label`" :for="`${uid}-icon`">{{ t('meetings.drafts.icon') }}</label>
          <Select
            :id="`${uid}-icon`"
            v-model="card.scope_icon"
            :aria-labelledby="`${uid}-icon-label`"
            :options="iconOptions"
            option-label="label"
            option-value="value"
            show-clear
            fluid
          >
            <template #option="{ option }">
              <i :class="option.icon" aria-hidden="true" class="option-icon" />
              {{ option.label }}
            </template>
          </Select>
        </div>
      </div>

      <div class="field">
        <label :for="`${uid}-body`">{{ t('meetings.drafts.body') }}</label>
        <Textarea v-model="card.body" :id="`${uid}-body`" auto-resize rows="4" fluid />
        <small class="field-hint">{{ t('meetings.drafts.bodyHint') }}</small>
      </div>

      <div class="field toggle-field">
        <ToggleSwitch v-model="card.internal" :input-id="`${uid}-internal`" />
        <label :for="`${uid}-internal`">{{ t('meetings.drafts.internal') }}</label>
      </div>

      <div class="sub-list">
        <span class="field-label">{{ t('meetings.drafts.decisions') }}</span>
        <p v-if="!card.decisions.length" class="empty-note">{{ t('meetings.drafts.noDecisions') }}</p>
        <div v-for="(_, d) in card.decisions" :key="d" class="sub-row">
          <InputText v-model="card.decisions[d]" maxlength="2000" fluid :aria-label="t('meetings.drafts.decision')" />
          <Button
            icon="mdi mdi-delete-outline"
            text
            severity="secondary"
            :aria-label="t('meetings.drafts.removeDecision')"
            @click="removeDecision(d)"
          />
        </div>
        <Button
          :label="t('meetings.drafts.addDecision')"
          icon="mdi mdi-plus"
          text
          severity="contrast"
          size="small"
          @click="addDecision"
        />
      </div>

      <div class="sub-list">
        <span class="field-label">{{ t('meetings.drafts.todos') }}</span>
        <p v-if="!card.todos.length" class="empty-note">{{ t('meetings.drafts.noTodos') }}</p>
        <div v-for="(todo, i) in card.todos" :key="i" class="todo-row" :data-testid="`draft-todo-${index}-${i}`">
          <div class="sub-row">
            <InputText v-model="todo.title" maxlength="300" fluid :aria-label="t('meetings.drafts.todoTitle')" />
            <DatePicker
              :model-value="dueOf(i)"
              show-icon
              show-clear
              class="due"
              :aria-label="t('meetings.drafts.dueDate')"
              @update:model-value="setDue(i, $event)"
            />
            <Button
              icon="mdi mdi-delete-outline"
              text
              severity="secondary"
              :aria-label="t('meetings.drafts.removeTodo')"
              @click="removeTodo(i)"
            />
          </div>
          <div v-if="todo.owners.length" class="owners">
            <span class="hint">{{ t('meetings.drafts.owners') }}</span>
            <Tag
              v-for="owner in todo.owners"
              :key="owner"
              :value="ownerLeftOut(owner, props.people) ? t('meetings.drafts.ownerLeftOut', { name: owner }) : personLabel(owner)"
              :severity="ownerLeftOut(owner, props.people) ? 'secondary' : 'info'"
            />
          </div>
        </div>
        <Button
          :label="t('meetings.drafts.addTodo')"
          icon="mdi mdi-plus"
          text
          severity="contrast"
          size="small"
          @click="addTodo"
        />
      </div>
    </template>
  </div>
</template>

<style scoped lang="scss">
.draft-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);

  &.excluded {
    opacity: 0.7;
  }
}

.draft-card-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.draft-card-title {
  font-weight: 600;
}

.note-label {
  font-weight: 600;
  margin-right: var(--space-1);
}

.option-icon {
  margin-right: var(--space-2);
}

.toggle-field {
  flex-direction: row;
  align-items: center;
  gap: var(--space-2);
}

.sub-list {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-2);

  > .sub-row,
  > .todo-row {
    align-self: stretch;
  }
}

.sub-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.todo-row {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.due {
  flex: 0 0 11rem;
}

.owners {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-1);
}
</style>
