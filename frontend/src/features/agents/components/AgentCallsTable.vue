<script setup lang="ts">
// The agent call log as a server paged table: when an agent called, with
// which token, which tool, how it went and which drafts it created. The
// backend limits a user to the calls of their own tokens; with `admin` the
// table shows every call with the token's owner, which read:settings may see.
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { useLayoutStore } from '@/core/stores/layoutStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useServerTable } from '@/core/composables/useServerTable'
import { TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { formatISODateTime } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import EmptyState from '@/shared/components/EmptyState.vue'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import { getAgentCalls } from '../api/agentsApi'
import type { AgentCall, AgentCallOutcome } from '../types/agentTypes'

const props = defineProps<{
  admin?: boolean
}>()

const { t, te } = useI18n()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const OUTCOME_SEVERITY: Record<AgentCallOutcome, 'success' | 'danger' | 'warn'> = {
  ok: 'success',
  error: 'danger',
  refused: 'warn',
}

// The records a person can open; an order line opens through its order.
const OPENABLE_KINDS = new Set(['order', 'quote_request', 'lot'])

const loading = ref(false)
watchLoadingBar(loading)
const items = ref<AgentCall[]>([])
const total = ref(0)

const { first, rows, fetchItems, onPage } = useServerTable({
  fetchParams: ({ first, rows }) => ({ skip: first, limit: rows }),
  fetch: async (params) => {
    loading.value = true
    try {
      const page = await getAgentCalls(params)
      items.value = page.items
      total.value = page.total
    } finally {
      loading.value = false
    }
  },
})

fetchItems()

interface CreatedLink {
  key: string
  label: string
  to: string
}

function createdLinks(call: AgentCall): CreatedLink[] {
  return call.created_refs.flatMap((ref) => {
    const [kind, publicId] = ref.split(':', 2)
    if (!kind || !publicId || !OPENABLE_KINDS.has(kind)) return []
    const labelKey = `agents.calls.kinds.${kind}`
    return [{ key: ref, label: te(labelKey) ? t(labelKey) : kind, to: `/resolve/${publicId}` }]
  })
}

function argumentsText(call: AgentCall): string {
  const entries = Object.entries(call.arguments)
  if (entries.length === 0) return ''
  return entries.map(([key, value]) => `${key}: ${JSON.stringify(value)}`).join(' · ')
}

defineExpose({ reload: fetchItems, loading })
</script>

<template>
  <DataTable
    :value="items"
    data-key="public_id"
    lazy
    paginator
    :total-records="total"
    :first="first"
    :rows="rows"
    :rows-per-page-options="TABLE_ROWS_PER_PAGE_OPTIONS"
    scrollable
    scroll-height="flex"
    size="small"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    data-testid="agent-calls-table"
    @page="onPage"
  >
    <Column header="#" class="column-fit" body-class="row-number">
      <template #body="{ index }">{{ first + index + 1 }}</template>
    </Column>
    <Column :header="t('agents.calls.columns.calledAt')" class="column-fit">
      <template #body="{ data }: { data: AgentCall }">
        <UserDateCell v-if="props.admin" :date="data.called_at" :user-id="data.user_id" with-time />
        <template v-else>{{ formatISODateTime(data.called_at) }}</template>
      </template>
    </Column>
    <Column :header="t('agents.calls.columns.token')" class="column-fit">
      <template #body="{ data }: { data: AgentCall }">
        <span class="token-cell">
          {{ data.token_name }}
          <Tag
            v-if="data.token_kind === 'api_key'"
            :value="t('agents.calls.apiKey')"
            severity="secondary"
          />
        </span>
      </template>
    </Column>
    <Column field="tool" :header="t('agents.calls.columns.tool')" class="column-fit" />
    <Column :header="t('agents.calls.columns.outcome')" class="column-fit">
      <template #body="{ data }: { data: AgentCall }">
        <Tag
          :value="t(`agents.calls.outcomes.${data.outcome}`)"
          :severity="OUTCOME_SEVERITY[data.outcome]"
        />
      </template>
    </Column>
    <Column :header="t('agents.calls.columns.details')">
      <template #body="{ data }: { data: AgentCall }">
        <div class="details-cell">
          <span v-if="data.error" class="error-text">{{ data.error }}</span>
          <span v-if="argumentsText(data)" class="muted">{{ argumentsText(data) }}</span>
          <span v-if="!data.error && !argumentsText(data)" class="muted">
            {{ getEmptyPlaceholder() }}
          </span>
        </div>
      </template>
    </Column>
    <Column :header="t('agents.calls.columns.created')" class="column-fit">
      <template #body="{ data }: { data: AgentCall }">
        <span class="created-cell">
          <RouterLink v-for="link in createdLinks(data)" :key="link.key" :to="link.to">
            {{ link.label }}
          </RouterLink>
          <span v-if="createdLinks(data).length === 0" class="muted">
            {{ getEmptyPlaceholder() }}
          </span>
        </span>
      </template>
    </Column>
    <Column :header="t('agents.calls.columns.duration')" class="column-fit">
      <template #body="{ data }: { data: AgentCall }">
        {{ t('agents.calls.durationMs', { ms: data.duration_ms }) }}
      </template>
    </Column>

    <template #empty>
      <EmptyState :message="t('agents.calls.empty')" />
    </template>
  </DataTable>
</template>

<style scoped lang="scss">
.token-cell,
.created-cell {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}

.details-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
}

.error-text {
  color: var(--p-red-500);
}

.muted {
  color: var(--p-text-muted-color);
}
</style>
