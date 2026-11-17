<script setup lang="ts">
// The rows of a derived machine's decision table, in the order the backend
// tries them: the first row whose condition holds gives the status.
import { useI18n } from 'vue-i18n'

import { resolveRowText, resolveStateLabel } from '../utils/stateMachineLabels'
import type { StateMachineRuleResponse } from '../types/stateMachinesResponse'

const props = defineProps<{
  machineKey: string
  rules: StateMachineRuleResponse[]
}>()

const { t, te } = useI18n()

function conditionText(rule: StateMachineRuleResponse): string {
  return resolveRowText(t, te, `rows.${rule.text_key}`, rule.condition)
}

function resultText(rule: StateMachineRuleResponse): string {
  if (rule.result_text_key) return resolveRowText(t, te, `rows.${rule.result_text_key}`, rule.result)
  return rule.results.map((value) => resolveStateLabel(t, te, props.machineKey, value)).join(', ')
}
</script>

<template>
  <div class="sm-rules">
    <h4 class="sm-rules-title">{{ t('stateMachines.rules.title') }}</h4>
    <p class="sm-rules-intro">{{ t('stateMachines.rules.intro') }}</p>
    <table class="sm-table" data-testid="sm-rule-table">
      <thead>
        <tr>
          <th class="sm-table-number">{{ t('stateMachines.rules.columns.number') }}</th>
          <th>{{ t('stateMachines.rules.columns.condition') }}</th>
          <th>{{ t('stateMachines.rules.columns.result') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="rule in rules" :key="rule.number" :data-rule="rule.number">
          <td class="sm-table-number">{{ rule.number }}</td>
          <td>{{ conditionText(rule) }}</td>
          <td class="sm-table-result">{{ resultText(rule) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped lang="scss">
.sm-rules {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.sm-rules-title {
  margin: 0;
  font-size: var(--font-size-md);
}

.sm-rules-intro {
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

.sm-table-number {
  width: 2.5rem;
  color: var(--p-text-muted-color);
}

.sm-table-result {
  font-weight: 500;
  white-space: nowrap;
}
</style>
