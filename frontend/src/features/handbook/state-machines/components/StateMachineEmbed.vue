<script setup lang="ts">
// Embedded in a handbook doc's markdown, pinned to the one machine the page
// is about. Fetching goes through the shared store, since one endpoint
// serves the whole registry. A machine with edges is drawn as a diagram; a
// derived machine lists the rows its status is worked out by, and any
// machine lists its user actions.
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

import { useStateMachinesStore } from '../stores/stateMachinesStore'
import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import StateMachineDiagram from './StateMachineDiagram.vue'
import StateMachineIntentTable from './StateMachineIntentTable.vue'
import StateMachineRuleTable from './StateMachineRuleTable.vue'

const props = defineProps<{
  /** Registry key from the backend, e.g. "lot_position_kind". */
  machineKey: string
}>()

const { t } = useI18n()
const store = useStateMachinesStore()
const { formatTime } = useLocaleFormat()

onMounted(() => {
  void store.fetch()
})

const machine = computed(
  () => store.machines.find((candidate) => candidate.key === props.machineKey) ?? null,
)

// Not every machine has a terminal state, so the legend only shows the
// swatch when this one does.
const hasTerminalState = computed(() => machine.value?.states.some((s) => s.terminal) ?? false)

const hasDiagram = computed(() => (machine.value?.edges.length ?? 0) > 0)

const lastFetchedLabel = computed(() => (store.lastFetched ? formatTime(store.lastFetched) : ''))
</script>

<template>
  <div class="sm-embed">
    <div v-if="store.loading && !store.loaded" class="sm-embed-skeleton">
      <Skeleton height="10rem" />
    </div>

    <Message v-else-if="store.error" severity="error" :closable="false">
      {{ store.error ?? t('stateMachines.errors.loadFailed') }}
    </Message>

    <Message v-else-if="!machine" severity="warn" :closable="false">
      {{ t('stateMachines.missing') }}
    </Message>

    <template v-else>
      <p class="sm-embed-kind" data-testid="sm-kind">{{ t(`stateMachines.kind.${machine.kind}`) }}</p>

      <div v-if="hasDiagram" class="sm-embed-legend">
        <span class="sm-embed-legend-item">
          <span class="sm-embed-swatch sm-embed-swatch-initial" />{{
            t('stateMachines.legend.initial')
          }}
        </span>
        <span v-if="hasTerminalState" class="sm-embed-legend-item">
          <span class="sm-embed-swatch sm-embed-swatch-terminal" />{{
            t('stateMachines.legend.terminal')
          }}
        </span>
        <span class="sm-embed-legend-item">
          <span class="sm-embed-swatch sm-embed-swatch-back" />{{
            t('stateMachines.legend.backEdge')
          }}
        </span>
      </div>

      <div v-if="hasDiagram" class="sm-embed-scroll">
        <StateMachineDiagram :machine="machine" />
      </div>

      <div v-if="machine.rules.length > 0" class="sm-embed-scroll">
        <StateMachineRuleTable :machine-key="machine.key" :rules="machine.rules" />
      </div>

      <div v-if="machine.intents.length > 0" class="sm-embed-scroll">
        <StateMachineIntentTable :machine-key="machine.key" :intents="machine.intents" />
      </div>

      <div class="sm-embed-footer">
        <p class="sm-embed-hint">{{ t('stateMachines.liveHint') }}</p>
        <div class="sm-embed-refresh">
          <span v-if="store.lastFetched" class="sm-embed-as-of">
            {{ t('stateMachines.asOf', { time: lastFetchedLabel }) }}
          </span>
          <Button
            icon="mdi mdi-refresh"
            :label="t('stateMachines.refresh')"
            severity="secondary"
            text
            size="small"
            :loading="store.loading"
            @click="store.refresh()"
          />
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped lang="scss">
.sm-embed {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin: 0 0 var(--space-4);
}

.sm-embed-kind {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.sm-embed-legend {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.sm-embed-legend-item {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}

.sm-embed-swatch {
  display: inline-block;
  width: 1.1rem;
  height: 0.75rem;
  border-radius: var(--p-border-radius-sm, 3px);
  border: 1.5px solid var(--p-content-border-color);
}

.sm-embed-swatch-initial {
  border-color: var(--p-primary-color);
  border-width: 2.5px;
}

.sm-embed-swatch-terminal {
  border-width: 1.25px;
  border-style: double;
}

.sm-embed-swatch-back {
  border-style: dashed;
}

.sm-embed-scroll {
  overflow-x: auto;
  width: 100%;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  padding: var(--space-3);
}

.sm-embed-footer {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.sm-embed-hint {
  margin: 0;
  font-size: var(--font-size-sm);
  font-style: italic;
  color: var(--p-text-muted-color);
  max-width: 34rem;
}

.sm-embed-refresh {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-shrink: 0;
}

.sm-embed-as-of {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  white-space: nowrap;
}
</style>
