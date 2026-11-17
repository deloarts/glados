<script setup lang="ts">
// Marks a record an AI agent created, such as a draft order, with the name
// of the agent token in its tooltip, so a person sees which drafts came from
// an agent before committing them. Renders nothing for any other record.
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAgentProvenanceStore } from '../stores/agentProvenanceStore'
import type { AgentDraftKind } from '../types/agentTypes'

const props = defineProps<{
  kind: AgentDraftKind
  publicId: string
}>()

const { t } = useI18n()
const store = useAgentProvenanceStore()

const ref = computed(() => `${props.kind}:${props.publicId}`)

watch(ref, (value) => store.request(value), { immediate: true })

const record = computed(() => store.recordOf(ref.value))
</script>

<template>
  <Tag
    v-if="record"
    v-tooltip.top="t('agents.badge.tooltip', { token: record.token_name })"
    class="agent-badge"
    severity="info"
    icon="mdi mdi-robot-outline"
    :value="t('agents.badge.label')"
    data-testid="agent-badge"
  />
</template>

<style scoped lang="scss">
.agent-badge {
  margin-left: var(--space-2);
}
</style>
