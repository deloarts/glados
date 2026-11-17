<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { routeForResource } from '@/features/scan'
import { useOrderFormatters } from '@/features/orders'
import { lotStatusSeverity, productionOrderStatusSeverity } from '@/features/production'
import { MadeItemThumbnailCell, useMadeItemLabel } from '@/features/made-items'
import { BoughtItemThumbnailCell } from '@/features/bought-items'
import { SourceItemThumbnailCell } from '@/features/source-items'

import type { GlobalSearchGroup, GlobalSearchHit, SearchResource } from '../types/globalSearchResponse'
import type { LotStatus, ProductionOrderStatus } from '@/features/production'

const props = defineProps<{
  group: GlobalSearchGroup
}>()

const emit = defineEmits<{
  select: [hit: GlobalSearchHit]
}>()

const { t } = useI18n()
const { orderStatusSeverity } = useOrderFormatters()
const { format: madeItemLabel } = useMadeItemLabel()
// Derived from the helper's signature, since the orders barrel does not
// export OrderStatus.
type OrderStatusValue = Parameters<typeof orderStatusSeverity>[0]

// One icon per sidebar section; resources in a section share its icon.
const GROUP_ICONS: Record<SearchResource, string> = {
  products: 'mdi-anvil',
  projects: 'mdi-anvil',
  'bought-items': 'mdi-book-open-page-variant',
  'made-items': 'mdi-book-open-page-variant',
  'source-items': 'mdi-book-open-page-variant',
  orders: 'mdi-cart',
  'production-lots': 'mdi-factory',
  'production-orders': 'mdi-factory',
  calculations: 'mdi-calculator-variant-outline',
  checklists: 'mdi-clipboard-check-outline',
  meetings: 'mdi-forum-outline',
  contacts: 'mdi-card-account-mail-outline',
}

const GROUP_LABEL_KEYS: Record<SearchResource, string> = {
  products: 'products',
  projects: 'projects',
  'bought-items': 'boughtItems',
  'made-items': 'madeItems',
  'source-items': 'sourceItems',
  orders: 'orders',
  'production-lots': 'productionLots',
  'production-orders': 'productionOrders',
  calculations: 'calculations',
  checklists: 'checklists',
  meetings: 'meetings',
  contacts: 'contacts',
}

// Where a calculation or checklist revision stands, by the status the search reports.
const DOCUMENT_STATUS_SEVERITY: Record<string, string> = {
  draft: 'secondary',
  released: 'success',
  invalid: 'danger',
}

const icon = computed(() => GROUP_ICONS[props.group.resource])
const title = computed(() => t(`search.groups.${GROUP_LABEL_KEYS[props.group.resource]}`))
const showAllRoute = computed(() => routeForResource(props.group.resource))
const showAll = computed(
  () => showAllRoute.value !== null && props.group.total > props.group.items.length,
)

interface ThumbnailSpec {
  kind: 'bought' | 'made' | 'source'
  itemId: number
  itemName: string
}

interface StatusTagSpec {
  value: string
  severity: string
}

interface RowModel {
  hit: GlobalSearchHit
  thumbnail: ThumbnailSpec | null
  primarySegments: string[]
  statusTag: StatusTagSpec | null
  secondarySegments: string[]
  marker: string | null
}

// A muted marker for related and fuzzy hits; none for the strict tiers.
function markerFor(hit: GlobalSearchHit): string | null {
  if (hit.match_kind === 'related' && hit.via_kind) return t(`search.row.via.${hit.via_kind}`)
  if (hit.match_kind === 'fuzzy') return t('search.row.fuzzy')
  return null
}

// Plain label and subtitle when details are missing.
function fallbackRow(hit: GlobalSearchHit): RowModel {
  return {
    hit,
    thumbnail: null,
    primarySegments: [hit.label],
    statusTag: null,
    secondarySegments: hit.subtitle ? [hit.subtitle] : [],
    marker: markerFor(hit),
  }
}

function buildRow(hit: GlobalSearchHit): RowModel {
  const d = hit.details
  if (!d) return fallbackRow(hit)

  const marker = markerFor(hit)

  switch (hit.resource) {
    case 'bought-items': {
      const primary = [d.order_code_1, d.part_number].filter((s): s is string => !!s)
      return {
        hit,
        thumbnail: { kind: 'bought', itemId: hit.id, itemName: d.article_name ?? hit.label },
        primarySegments: primary.length > 0 ? primary : [hit.label],
        statusTag: null,
        secondarySegments: d.article_name ? [d.article_name] : [],
        marker,
      }
    }
    case 'made-items': {
      const primaryText = d.part_number
        ? madeItemLabel(d.part_number, d.revision)
        : (d.article_name ?? hit.label)
      const secondary: string[] = []
      if (d.article_name && d.article_name !== primaryText) secondary.push(d.article_name)
      return {
        hit,
        thumbnail: { kind: 'made', itemId: hit.id, itemName: d.article_name ?? hit.label },
        primarySegments: [primaryText],
        statusTag: null,
        secondarySegments: secondary,
        marker,
      }
    }
    case 'source-items': {
      return {
        hit,
        thumbnail: { kind: 'source', itemId: hit.id, itemName: hit.label },
        primarySegments: [hit.label],
        statusTag: null,
        secondarySegments: hit.subtitle ? [hit.subtitle] : [],
        marker,
      }
    }
    case 'orders': {
      const secondary: string[] = []
      if (d.supplier_name) secondary.push(d.supplier_name)
      secondary.push(t('search.row.items', { count: d.item_count ?? 0 }))
      return {
        hit,
        thumbnail: null,
        primarySegments: [hit.label],
        statusTag: d.status
          ? {
              value: t(`orders.status.${d.status}`),
              severity: orderStatusSeverity(d.status as OrderStatusValue),
            }
          : null,
        secondarySegments: secondary,
        marker,
      }
    }
    case 'production-lots': {
      const secondary: string[] = []
      const itemLabel = d.made_item_part_number
        ? madeItemLabel(d.made_item_part_number, d.made_item_revision)
        : d.made_item_article_name
      if (itemLabel) secondary.push(itemLabel)
      if (d.source_label) secondary.push(d.source_label)
      if (d.steps && d.steps.length > 0) secondary.push(d.steps.join(' › '))
      return {
        hit,
        thumbnail:
          d.made_item_id != null
            ? { kind: 'made', itemId: d.made_item_id, itemName: itemLabel ?? hit.label }
            : null,
        primarySegments: [hit.label],
        statusTag: d.status
          ? {
              value: t(`production.lots.status.${d.status}`),
              severity: lotStatusSeverity[d.status as LotStatus],
            }
          : null,
        secondarySegments: secondary,
        marker,
      }
    }
    case 'production-orders': {
      const itemLabel = d.made_item_part_number
        ? madeItemLabel(d.made_item_part_number, d.made_item_revision)
        : d.made_item_article_name
      const secondary: string[] = []
      if (itemLabel) secondary.push(itemLabel)
      secondary.push(d.execution_label ?? t('search.row.manual'))
      return {
        hit,
        thumbnail:
          d.made_item_id != null
            ? { kind: 'made', itemId: d.made_item_id, itemName: itemLabel ?? hit.label }
            : null,
        primarySegments: [hit.label],
        statusTag: d.status
          ? {
              value: t(`productionQueue.status.${d.status}`),
              severity: productionOrderStatusSeverity[d.status as ProductionOrderStatus],
            }
          : null,
        secondarySegments: secondary,
        marker,
      }
    }
    case 'calculations':
    case 'checklists':
      return {
        hit,
        thumbnail: null,
        primarySegments: [
          d.revision ? t('documents.reference', { number: hit.label, revision: d.revision }) : hit.label,
        ],
        statusTag: d.status
          ? { value: t(`documents.status.${d.status}`), severity: DOCUMENT_STATUS_SEVERITY[d.status] ?? 'secondary' }
          : null,
        secondarySegments: hit.subtitle ? [hit.subtitle] : [],
        marker,
      }
    default:
      return fallbackRow(hit)
  }
}

const rows = computed<RowModel[]>(() => props.group.items.map(buildRow))
</script>

<template>
  <Panel class="search-result-group">
    <template #header>
      <div class="group-header">
        <i class="mdi" :class="icon" aria-hidden="true" />
        <span class="group-title">{{ title }}</span>
        <Tag :value="group.total" severity="secondary" class="group-count" />
      </div>
    </template>

    <ul class="hit-list">
      <li v-for="row in rows" :key="row.hit.id">
        <button type="button" class="hit-row" @click="emit('select', row.hit)">
          <BoughtItemThumbnailCell
            v-if="row.thumbnail?.kind === 'bought'"
            :item-id="row.thumbnail.itemId"
            :item-name="row.thumbnail.itemName"
            size="2.5rem"
          />
          <MadeItemThumbnailCell
            v-else-if="row.thumbnail?.kind === 'made'"
            :item-id="row.thumbnail.itemId"
            :item-name="row.thumbnail.itemName"
            size="2.5rem"
          />
          <SourceItemThumbnailCell
            v-else-if="row.thumbnail?.kind === 'source'"
            :item-id="row.thumbnail.itemId"
            :item-name="row.thumbnail.itemName"
            size="2.5rem"
          />

          <div class="hit-text">
            <span class="hit-label">
              <template v-for="(segment, index) in row.primarySegments" :key="index">
                <span v-if="index > 0" class="info-sep" />
                {{ segment }}
              </template>
              <Tag
                v-if="row.statusTag"
                :value="row.statusTag.value"
                :severity="row.statusTag.severity"
                class="hit-status-tag"
              />
            </span>
            <span v-if="row.secondarySegments.length > 0 || row.marker" class="hit-subtitle">
              <template v-for="(segment, index) in row.secondarySegments" :key="index">
                <span v-if="index > 0" class="info-sep" />
                {{ segment }}
              </template>
              <template v-if="row.marker">
                <span v-if="row.secondarySegments.length > 0" class="info-sep" />
                <span class="hit-marker">{{ row.marker }}</span>
              </template>
            </span>
          </div>
        </button>
      </li>
    </ul>

    <RouterLink v-if="showAll" :to="showAllRoute!" class="show-all-link">
      {{ t('search.showAll', { count: group.total }) }}
    </RouterLink>
  </Panel>
</template>

<style scoped lang="scss">
.search-result-group {
  display: flex;
  flex-direction: column;
}

.group-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
}

.group-title {
  font-weight: 600;
}

.group-count {
  margin-left: auto;
}

.hit-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.hit-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border: none;
  border-radius: var(--p-content-border-radius);
  background: none;
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.15s;

  &:hover {
    background-color: var(--p-content-hover-background);
  }

  &:focus-visible {
    outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
    outline-offset: -2px;
  }
}

.hit-text {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
  flex: 1;
}

.hit-label {
  display: flex;
  align-items: center;
  font-weight: 600;
  font-size: var(--font-size-sm);
}

.hit-status-tag {
  margin-left: var(--space-2);
}

.hit-subtitle {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.hit-marker {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  font-style: italic;
}

.info-sep {
  display: inline-block;
  width: 1px;
  height: 1.1rem;
  background: var(--p-surface-300);
  margin: 0 var(--space-2);
  vertical-align: middle;
  flex-shrink: 0;
}

.show-all-link {
  display: inline-block;
  margin-top: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--p-primary-color);

  &:hover {
    text-decoration: underline;
  }
}
</style>
