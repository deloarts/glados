<script setup lang="ts">
// The lines of one quote request, the expansion row under the Quotes table,
// laid out like the items under an order: what is asked for, how much, the
// lowest offer so far, and for an awarded line the supplier that won it and
// the order it went onto. A dropped line is dimmed, and a line that
// replaced another shows why.
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'

import { useLayoutStore } from '@/core/stores/layoutStore'
import { formatPrice } from '@/core/utils/currency'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import EmptyState from '@/shared/components/EmptyState.vue'
import { formatUnit } from '@/shared/utils/units'
import { quoteLineStateSeverity } from '../utils/quoteRequestFormat'
import type {
  QuoteRequestLineResponse,
  QuoteRequestResponse,
} from '../types/quoteRequestsResponse'

const props = defineProps<{ request: QuoteRequestResponse }>()

const { t } = useI18n()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

function pricedQuotes(line: QuoteRequestLineResponse): number[] {
  return props.request.suppliers
    .flatMap((row) => row.quotes)
    .filter((q) => q.line_id === line.id && !q.no_offer && q.unit_price !== null)
    .map((q) => q.unit_price as number)
}

/** The lowest unit price any supplier offered for the line. */
function bestPrice(line: QuoteRequestLineResponse): number | null {
  const prices = pricedQuotes(line)
  return prices.length > 0 ? Math.min(...prices) : null
}

function supplierName(rowId: number | null): string | null {
  if (rowId === null) return null
  return props.request.suppliers.find((row) => row.id === rowId)?.supplier_name ?? null
}

function rowClass(line: QuoteRequestLineResponse): string | undefined {
  return line.state === 'dropped' ? 'row-dropped' : undefined
}
</script>

<template>
  <div class="items-panel fixed-layout-table nested-table">
    <DataTable
      :value="props.request.lines"
      data-key="id"
      size="small"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
      :row-class="rowClass"
      data-testid="quote-request-lines"
    >
      <template #empty>
        <EmptyState :message="t('quoteRequests.comparison.empty')" />
      </template>

      <Column :header="t('quoteRequests.lines.position')" style="width: 4rem">
        <template #body="{ data }: { data: QuoteRequestLineResponse }">
          {{ data.position }}
        </template>
      </Column>

      <Column :header="t('quoteRequests.lines.state')" style="width: 8rem">
        <template #body="{ data }: { data: QuoteRequestLineResponse }">
          <Tag
            :value="t(`quoteRequests.lineState.${data.state}`)"
            :severity="quoteLineStateSeverity(data.state)"
          />
        </template>
      </Column>

      <Column :header="t('quoteRequests.lines.quantity')" style="width: 8rem">
        <template #body="{ data }: { data: QuoteRequestLineResponse }">
          <span class="num-cell nowrap">{{ data.quantity }} {{ formatUnit(data.unit) }}</span>
        </template>
      </Column>

      <Column :header="t('quoteRequests.lines.project')" style="width: 10rem">
        <template #body="{ data }: { data: QuoteRequestLineResponse }">
          <div class="stack-cell">
            <RouterLink
              v-if="data.project_id !== null"
              class="strong link"
              :to="`/workspace/projects/${data.project_id}`"
              @click.stop
              >{{ data.project_number }}</RouterLink
            >
            <span v-else class="muted">{{ getEmptyPlaceholder() }}</span>
            <span v-if="data.lot_number" class="sub">{{ data.lot_number }}</span>
          </div>
        </template>
      </Column>

      <Column :header="t('quoteRequests.lines.item')" style="width: 18rem" body-class="wrap-cell">
        <template #body="{ data }: { data: QuoteRequestLineResponse }">
          <div class="stack-cell">
            <span class="strong">{{ data.item_name }}</span>
            <span v-if="data.item_code" class="sub">{{ data.item_code }}</span>
            <span
              v-if="data.substitute_reason"
              v-tooltip.top="data.substitute_reason"
              class="sub substitute"
            >
              <i class="mdi mdi-swap-horizontal" aria-hidden="true" />
              {{ t('quoteRequests.substitute.tag') }}
            </span>
            <span v-if="data.demands.length > 1" class="sub">
              {{ t('quoteRequests.comparison.demands', { count: data.demands.length }) }}
            </span>
          </div>
        </template>
      </Column>

      <Column :header="t('quoteRequests.lines.bestPrice')" style="width: 8rem">
        <template #body="{ data }: { data: QuoteRequestLineResponse }">
          <div class="stack-cell">
            <span class="num-cell" :class="{ muted: bestPrice(data) === null }">
              {{ formatPrice(bestPrice(data)) }}
            </span>
            <span class="sub">
              {{ t('quoteRequests.lines.offers', { count: pricedQuotes(data).length }) }}
            </span>
          </div>
        </template>
      </Column>

      <Column :header="t('quoteRequests.lines.awardedTo')" style="width: 12rem">
        <template #body="{ data }: { data: QuoteRequestLineResponse }">
          <div v-if="supplierName(data.awarded_supplier_id)" class="stack-cell">
            <span class="strong">{{ supplierName(data.awarded_supplier_id) }}</span>
            <span class="sub num-cell">{{ formatPrice(data.awarded_price) }}</span>
            <Tag
              v-if="data.award_voided"
              v-tooltip.top="t('quoteRequests.lines.voidedHint')"
              :value="t('quoteRequests.lines.voided')"
              severity="warn"
            />
          </div>
          <span v-else class="muted">{{ getEmptyPlaceholder() }}</span>
        </template>
      </Column>

      <Column :header="t('quoteRequests.lines.order')" style="width: 8rem">
        <template #body="{ data }: { data: QuoteRequestLineResponse }">
          <RouterLink
            v-if="data.order_id !== null"
            class="link nowrap"
            :to="`/procurement/orders/${data.order_id}`"
            @click.stop
            >{{ data.order_number }}</RouterLink
          >
          <span v-else class="muted">{{ getEmptyPlaceholder() }}</span>
        </template>
      </Column>

      <Column :header="t('quoteRequests.lines.note')" style="width: 14rem">
        <template #body="{ data }: { data: QuoteRequestLineResponse }">
          <span class="note-cell">{{ data.note || getEmptyPlaceholder() }}</span>
        </template>
      </Column>

      <!-- The trailing empty column absorbs the width the real columns do
           not need, see the fixed table layout below. -->
      <Column />
    </DataTable>
  </div>
</template>

<style scoped lang="scss">
// Under a fixed layout (.fixed-layout-table) every real column keeps its
// explicit width, so the surplus goes to the trailing empty column alone
// instead of being spread across all of them. The outer Quotes table is
// clickable, so .nested-table keeps its hover from greying these rows.
.items-panel {
  padding: var(--space-1) var(--space-1) var(--space-4);
}

// A dropped line is no longer asked for.
:deep(.row-dropped) > td {
  opacity: 0.6;
}

:deep(.wrap-cell) {
  white-space: normal;
}

.stack-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.strong {
  font-weight: 600;
}

.substitute {
  color: var(--p-orange-600);
}

.sub {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-xs);
}

.link {
  color: inherit;
  text-decoration: none;
  width: fit-content;

  &:hover {
    text-decoration: underline;
    color: var(--p-primary-color);
  }
}

.num-cell {
  font-variant-numeric: tabular-nums;
}

.nowrap {
  white-space: nowrap;
}

.muted {
  color: var(--p-text-muted-color);
}

.note-cell {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: bottom;
  color: var(--p-text-muted-color);
}
</style>
