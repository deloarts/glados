<script setup lang="ts">
// Embedded in a handbook doc's markdown: the status changes of one machine,
// or with `cascades` the overview of what a request on one record changes on
// the others. Fetching goes through the shared store, like StateMachineEmbed.
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

import { useStateMachinesStore } from '../stores/stateMachinesStore'
import StateCascadeTable from './StateCascadeTable.vue'
import StateMachineTransitionTable from './StateMachineTransitionTable.vue'

const props = defineProps<{
  /** Registry key from the backend, e.g. "order_item_status". */
  machineKey?: string
  /** Shows the cascades across every machine instead of one machine. */
  cascades?: boolean
}>()

const { t } = useI18n()
const store = useStateMachinesStore()

onMounted(() => {
  void store.fetch()
})

const machine = computed(
  () => store.machines.find((candidate) => candidate.key === props.machineKey) ?? null,
)
</script>

<template>
  <div class="sm-transitions-embed">
    <div v-if="store.loading && !store.loaded">
      <Skeleton height="10rem" />
    </div>

    <Message v-else-if="store.error" severity="error" :closable="false">
      {{ store.error ?? t('stateMachines.errors.loadFailed') }}
    </Message>

    <div v-else-if="cascades" class="sm-transitions-embed-scroll">
      <StateCascadeTable :machines="store.machines" />
    </div>

    <Message v-else-if="!machine" severity="warn" :closable="false">
      {{ t('stateMachines.missing') }}
    </Message>

    <div v-else class="sm-transitions-embed-scroll">
      <StateMachineTransitionTable :machine="machine" />
    </div>

    <p v-if="store.loaded" class="sm-transitions-embed-hint">
      {{ t('stateMachines.transitions.computedHint') }}
    </p>
  </div>
</template>

<style scoped lang="scss">
.sm-transitions-embed {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin: 0 0 var(--space-4);
}

.sm-transitions-embed-scroll {
  overflow-x: auto;
  width: 100%;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  padding: var(--space-3);
}

.sm-transitions-embed-hint {
  margin: 0;
  font-size: var(--font-size-sm);
  font-style: italic;
  color: var(--p-text-muted-color);
  max-width: 34rem;
}
</style>
