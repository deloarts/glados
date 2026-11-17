<script setup lang="ts">
// What a request on one record changes on the others: every cascade row of
// every machine, grouped by the record the request acted on and its
// trigger, in registry order.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import {
  resolveMachineLabel,
  resolveStateLabel,
  resolveTriggerLabel,
} from '../utils/stateMachineLabels'
import type { StateMachineResponse } from '../types/stateMachinesResponse'

const props = defineProps<{
  machines: StateMachineResponse[]
}>()

const { t, te } = useI18n()

interface Change {
  machine: string
  from: string | null
  to: string
}

interface Cascade {
  subject: string
  trigger: string
  changes: Change[]
}

const cascades = computed<Cascade[]>(() => {
  const order = props.machines.map((machine) => machine.key)
  const byRequest = new Map<string, Cascade>()
  for (const machine of props.machines) {
    for (const transition of machine.transitions) {
      if (!transition.cascade) continue
      const key = `${transition.subject}:${transition.trigger}`
      let cascade = byRequest.get(key)
      if (!cascade) {
        cascade = { subject: transition.subject, trigger: transition.trigger, changes: [] }
        byRequest.set(key, cascade)
      }
      cascade.changes.push({
        machine: machine.key,
        from: transition.from_state,
        to: transition.to_state,
      })
    }
  }
  return [...byRequest.values()].sort(
    (a, b) =>
      order.indexOf(a.subject) - order.indexOf(b.subject) ||
      triggerText(a.trigger).localeCompare(triggerText(b.trigger)),
  )
})

function triggerText(trigger: string): string {
  return resolveTriggerLabel(t, te, trigger)
}

function stateText(machineKey: string, value: string | null): string {
  if (value === null) return t('stateMachines.transitions.created')
  return resolveStateLabel(t, te, machineKey, value)
}

function changeText(change: Change): string {
  return t('stateMachines.transitions.change', {
    machine: resolveMachineLabel(t, te, change.machine),
    from: stateText(change.machine, change.from),
    to: stateText(change.machine, change.to),
  })
}
</script>

<template>
  <div class="sm-cascades">
    <h4 class="sm-cascades-title">{{ t('stateMachines.cascades.title') }}</h4>
    <p class="sm-cascades-intro">{{ t('stateMachines.cascades.intro') }}</p>
    <table class="sm-table" data-testid="sm-cascade-table">
      <thead>
        <tr>
          <th>{{ t('stateMachines.cascades.columns.record') }}</th>
          <th>{{ t('stateMachines.cascades.columns.trigger') }}</th>
          <th>{{ t('stateMachines.cascades.columns.changes') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="cascade in cascades"
          :key="`${cascade.subject}:${cascade.trigger}`"
          :data-subject="cascade.subject"
          :data-trigger="cascade.trigger"
        >
          <td class="sm-table-record">{{ resolveMachineLabel(t, te, cascade.subject) }}</td>
          <td class="sm-table-trigger">{{ triggerText(cascade.trigger) }}</td>
          <td>
            <ul class="sm-table-list">
              <li
                v-for="change in cascade.changes"
                :key="`${change.machine}:${change.from ?? ''}>${change.to}`"
              >
                {{ changeText(change) }}
              </li>
            </ul>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped lang="scss">
.sm-cascades {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.sm-cascades-title {
  margin: 0;
  font-size: var(--font-size-md);
}

.sm-cascades-intro {
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

.sm-table-record,
.sm-table-trigger {
  font-weight: 500;
  white-space: nowrap;
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
