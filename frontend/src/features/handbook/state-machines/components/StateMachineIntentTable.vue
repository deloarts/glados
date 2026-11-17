<script setup lang="ts">
// The user actions of a machine: the statuses each starts from, what else it
// needs, the permission it adds and what it does.
import { useI18n } from 'vue-i18n'

import {
  resolveActionLabel,
  resolveRowText,
  resolveStateLabel,
} from '../utils/stateMachineLabels'
import type { StateMachineIntentResponse } from '../types/stateMachinesResponse'

const props = defineProps<{
  machineKey: string
  intents: StateMachineIntentResponse[]
}>()

const { t, te } = useI18n()

function actionText(intent: StateMachineIntentResponse): string {
  if (intent.target) {
    return t('stateMachines.intents.setStatus', {
      status: resolveStateLabel(t, te, props.machineKey, intent.target),
    })
  }
  return resolveActionLabel(t, te, intent.action)
}

function allowedFromText(intent: StateMachineIntentResponse): string {
  if (!intent.allowed_from) return t('stateMachines.intents.anyStatus')
  return intent.allowed_from
    .map((value) => resolveStateLabel(t, te, props.machineKey, value))
    .join(', ')
}

function rowText(intent: StateMachineIntentResponse, field: string, fallback: string): string {
  if (!fallback) return ''
  return resolveRowText(t, te, `intentRows.${intent.text_key}.${field}`, fallback)
}
</script>

<template>
  <div class="sm-intents">
    <h4 class="sm-intents-title">{{ t('stateMachines.intents.title') }}</h4>
    <table class="sm-table" data-testid="sm-intent-table">
      <thead>
        <tr>
          <th>{{ t('stateMachines.intents.columns.action') }}</th>
          <th>{{ t('stateMachines.intents.columns.allowedFrom') }}</th>
          <th>{{ t('stateMachines.intents.columns.condition') }}</th>
          <th>{{ t('stateMachines.intents.columns.permission') }}</th>
          <th>{{ t('stateMachines.intents.columns.effect') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="intent in intents" :key="intent.text_key" :data-action="intent.action">
          <td class="sm-table-action">{{ actionText(intent) }}</td>
          <td>{{ allowedFromText(intent) }}</td>
          <td>{{ rowText(intent, 'condition', intent.condition) }}</td>
          <td>{{ rowText(intent, 'permission', intent.permission) }}</td>
          <td>{{ rowText(intent, 'effect', intent.effect) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped lang="scss">
.sm-intents {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.sm-intents-title {
  margin: 0;
  font-size: var(--font-size-md);
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

.sm-table-action {
  font-weight: 500;
  white-space: nowrap;
}
</style>
