<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatISODateTime } from '@/core/utils/dates'
import { getBoughtItems } from '@/features/bought-items'
import { sourceItemsApi } from '@/features/source-items'
import { getMadeItems } from '@/features/made-items'
import { useMadeItemLabel } from '@/features/made-items'
import { lotEventActorName, lotEventIcon, lotEventLabel } from '../../utils/lotEventLabels'

import type { LotEventResponse } from '../../../types/productionLotsResponse'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { localizeLabel } from '@/shared/utils/localizeLabel'

const props = defineProps<{
  events: LotEventResponse[]
  loading: boolean
  requiredDeliveryDate: string | null
}>()

const { t, te } = useI18n()
const { format: madeItemLabel } = useMadeItemLabel()

// Late only against the lot's required delivery date.
function isLateEvent(occurredAt: string): boolean {
  if (!props.requiredDeliveryDate) return false
  return occurredAt.slice(0, 10) > props.requiredDeliveryDate
}

// ── Resolve a material-source-switch event's item ids to a label ───────
// The event carries only raw ids, and the lot only knows its current source.
// Older events stored the source item id under "base_item_id".

type ItemKind = 'bought' | 'source' | 'made'

interface MaterialSourceTarget {
  kind: ItemKind
  id: number
}

function materialSourceTarget(event: LotEventResponse): MaterialSourceTarget | null {
  if (event.event_type !== 'lot_material_source_switched' || !event.payload) return null
  const payload = event.payload
  if (typeof payload.bought_item_id === 'number')
    return { kind: 'bought', id: payload.bought_item_id }
  const sourceItemId = payload.source_item_id ?? payload.base_item_id
  if (typeof sourceItemId === 'number') return { kind: 'source', id: sourceItemId }
  if (typeof payload.made_item_id === 'number') return { kind: 'made', id: payload.made_item_id }
  return null
}

const itemLabels = ref<Map<string, string>>(new Map())

function materialSourceLabel(event: LotEventResponse): string | null {
  const target = materialSourceTarget(event)
  return target ? (itemLabels.value.get(`${target.kind}:${target.id}`) ?? null) : null
}

async function fetchLabel(target: MaterialSourceTarget): Promise<string> {
  if (target.kind === 'bought') {
    const page = await getBoughtItems({ id: target.id, limit: 1 })
    const item = page.items[0]
    return item
      ? `${item.part_number ?? getEmptyPlaceholder()} · ${item.article_name}`
      : `#${target.id}`
  }
  if (target.kind === 'made') {
    const page = await getMadeItems({ id: target.id, limit: 1 })
    const item = page.items[0]
    return item ? `${madeItemLabel(item.part_number, item.revision)} · ${item.article_name}` : `#${target.id}`
  }
  const page = await sourceItemsApi.list({ id: target.id, limit: 1 })
  const item = page.items[0]
  return item
    ? `${localizeLabel(item.type_name)} · ${item.material}${item.dimension ? ` ${item.dimension}` : ''}`
    : `#${target.id}`
}

watch(
  () => props.events,
  async (events) => {
    const toFetch = new Map<string, MaterialSourceTarget>()
    for (const event of events) {
      const target = materialSourceTarget(event)
      if (!target) continue
      const key = `${target.kind}:${target.id}`
      if (!itemLabels.value.has(key)) toFetch.set(key, target)
    }
    if (toFetch.size === 0) return
    const resolved = await Promise.all(
      [...toFetch.entries()].map(
        async ([key, target]) =>
          [key, await fetchLabel(target).catch(() => `#${target.id}`)] as const,
      ),
    )
    const next = new Map(itemLabels.value)
    for (const [key, label] of resolved) next.set(key, label)
    itemLabels.value = next
  },
  { immediate: true },
)
</script>

<template>
  <ul v-if="loading && events.length === 0" class="audit-list">
    <li v-for="n in 4" :key="n" class="audit-item">
      <Skeleton shape="circle" size="1.1rem" />
      <div class="audit-item-content">
        <Skeleton width="8rem" height="0.9rem" />
        <Skeleton width="14rem" height="0.83rem" />
        <Skeleton width="10rem" height="0.75rem" />
      </div>
    </li>
  </ul>

  <div v-else-if="events.length === 0" class="empty-note">
    {{ t('production.lots.detail.audit.empty') }}
  </div>

  <ul v-else class="audit-list">
    <li v-for="event in events" :key="event.id" class="audit-item">
      <i class="mdi audit-item-icon" :class="lotEventIcon(event.event_type)" aria-hidden="true" />
      <div class="audit-item-content">
        <div class="audit-item-row">
          <span class="audit-item-label">{{ lotEventLabel(event.event_type, { t, te }) }}</span>
          <Tag
            v-if="isLateEvent(event.occurred_at)"
            :value="t('production.lots.detail.audit.late')"
            severity="danger"
            icon="mdi mdi-alert"
            v-tooltip.top="
              t('production.lots.detail.audit.lateTooltip', { date: requiredDeliveryDate })
            "
          />
        </div>
        <div class="audit-item-summary">{{ event.summary }}</div>
        <div v-if="materialSourceLabel(event)" class="audit-item-resolved">
          {{ t('production.lots.detail.audit.materialSourceItem') }}:
          {{ materialSourceLabel(event) }}
        </div>
        <div class="audit-item-meta">
          <span>{{ formatISODateTime(event.occurred_at) }}</span>
          <span>{{ lotEventActorName(event) }}</span>
        </div>
      </div>
    </li>
  </ul>
</template>

<style scoped lang="scss">
.audit-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.audit-item {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-1);
  border-bottom: 1px solid var(--p-content-border-color);

  &:last-child {
    border-bottom: none;
  }
}

.audit-item-icon {
  font-size: var(--font-size-lg);
  color: var(--p-text-muted-color);
  margin-top: var(--space-1);
}

.audit-item-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
  flex: 1;
}

.audit-item-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.audit-item-label {
  font-weight: 600;
  font-size: var(--font-size-sm);
}

.audit-item-summary {
  font-size: var(--font-size-sm);
  color: var(--p-text-color);
  // The lot_updated summary is a multi-line list.
  white-space: pre-line;
}

.audit-item-resolved {
  font-size: var(--font-size-sm);
  color: var(--p-primary-color);
}

.audit-item-meta {
  display: flex;
  gap: var(--space-3);
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}
</style>
