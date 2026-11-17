<script setup lang="ts">
// Every status change the code makes on one machine, as the lifecycle model
// observed it: the status before and after, what triggered it, the rows and
// actions behind it and what the same trigger changes on other records. A
// cascade row, made by a request on another record, names that record.
import { useI18n } from 'vue-i18n'

import {
  resolveMachineLabel,
  resolveRowText,
  resolveStateLabel,
  resolveTriggerLabel,
} from '../utils/stateMachineLabels'
import type {
  StateMachineImplicationResponse,
  StateMachineResponse,
  StateMachineTransitionResponse,
} from '../types/stateMachinesResponse'

const props = defineProps<{
  machine: StateMachineResponse
}>()

const { t, te } = useI18n()

function stateText(machineKey: string, value: string | null): string {
  if (value === null) return t('stateMachines.transitions.created')
  return resolveStateLabel(t, te, machineKey, value)
}

function triggerText(transition: StateMachineTransitionResponse): string {
  return resolveTriggerLabel(t, te, transition.trigger)
}

function subjectText(transition: StateMachineTransitionResponse): string {
  return t('stateMachines.transitions.via', {
    machine: resolveMachineLabel(t, te, transition.subject),
  })
}

function conditionTexts(transition: StateMachineTransitionResponse): string[] {
  const rules = transition.rule_text_keys.flatMap((key) => {
    const rule = props.machine.rules.find((candidate) => candidate.text_key === key)
    return rule ? [resolveRowText(t, te, `rows.${key}`, rule.condition)] : []
  })
  const intents = transition.intent_text_keys.flatMap((key) => {
    const intent = props.machine.intents.find((candidate) => candidate.text_key === key)
    if (!intent?.condition) return []
    return [resolveRowText(t, te, `intentRows.${key}.condition`, intent.condition)]
  })
  return [...rules, ...intents]
}

function permissionTexts(transition: StateMachineTransitionResponse): string[] {
  const texts = transition.intent_text_keys.flatMap((key) => {
    const intent = props.machine.intents.find((candidate) => candidate.text_key === key)
    if (!intent?.permission) return []
    return [resolveRowText(t, te, `intentRows.${key}.permission`, intent.permission)]
  })
  return [...new Set(texts)]
}

function implicationText(implication: StateMachineImplicationResponse): string {
  return t('stateMachines.transitions.change', {
    machine: resolveMachineLabel(t, te, implication.machine),
    from: stateText(implication.machine, implication.from_state),
    to: stateText(implication.machine, implication.to_state),
  })
}

function rowKey(transition: StateMachineTransitionResponse): string {
  return `${transition.from_state ?? ''}>${transition.to_state}:${transition.trigger}:${transition.subject}`
}
</script>

<template>
  <div class="sm-transitions">
    <h4 class="sm-transitions-title">{{ t('stateMachines.transitions.title') }}</h4>
    <p class="sm-transitions-intro">{{ t('stateMachines.transitions.intro') }}</p>
    <table class="sm-table" data-testid="sm-transition-table">
      <thead>
        <tr>
          <th>{{ t('stateMachines.transitions.columns.from') }}</th>
          <th>{{ t('stateMachines.transitions.columns.to') }}</th>
          <th>{{ t('stateMachines.transitions.columns.trigger') }}</th>
          <th>{{ t('stateMachines.transitions.columns.condition') }}</th>
          <th>{{ t('stateMachines.transitions.columns.permission') }}</th>
          <th>{{ t('stateMachines.transitions.columns.implications') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="transition in machine.transitions"
          :key="rowKey(transition)"
          :data-trigger="transition.trigger"
          :class="{ 'sm-table-cascade': transition.cascade }"
        >
          <td class="sm-table-state">{{ stateText(machine.key, transition.from_state) }}</td>
          <td class="sm-table-state">{{ stateText(machine.key, transition.to_state) }}</td>
          <td>
            <span class="sm-table-trigger">{{ triggerText(transition) }}</span>
            <span v-if="transition.cascade" class="sm-table-subject" data-testid="sm-cascade">
              {{ subjectText(transition) }}
            </span>
          </td>
          <td>
            <ul class="sm-table-list">
              <li v-for="text in conditionTexts(transition)" :key="text">{{ text }}</li>
            </ul>
          </td>
          <td>
            <ul class="sm-table-list">
              <li v-for="text in permissionTexts(transition)" :key="text">{{ text }}</li>
            </ul>
          </td>
          <td>
            <ul class="sm-table-list">
              <li
                v-for="implication in transition.implications"
                :key="`${implication.machine}:${implication.from_state ?? ''}>${implication.to_state}`"
              >
                {{ implicationText(implication) }}
              </li>
            </ul>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped lang="scss">
.sm-transitions {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.sm-transitions-title {
  margin: 0;
  font-size: var(--font-size-md);
}

.sm-transitions-intro {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.sm-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);
}

.sm-table th,
.sm-table td {
  text-align: left;
  vertical-align: top;
  padding: var(--space-2) var(--space-2);
  border-bottom: 1px solid var(--p-content-border-color);
}

.sm-table th {
  color: var(--p-text-muted-color);
  font-weight: 600;
}

.sm-table-state {
  white-space: nowrap;
}

.sm-table-trigger {
  display: block;
  font-weight: 500;
}

.sm-table-subject {
  display: block;
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.sm-table-cascade .sm-table-trigger {
  font-weight: 400;
}

.sm-table-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
</style>
