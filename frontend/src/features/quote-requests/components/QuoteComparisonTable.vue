<script setup lang="ts">
// The lines of a quote request against the suppliers asked: each cell is a
// supplier's offer for a line, the cheapest per line marked, and the footer
// sums each offer with its extra costs, the cheapest complete offer marked.
// Choosing a cell picks that supplier for the line's award. A line added
// after the request went out to a supplier shows "not asked" there. A line
// that replaced another and a supplier's alternative item are marked with
// their reason; an alternative competes for the cheapest price like any
// offer. A line whose award was voided, because its order line was canceled
// or removed, is open again and says so; on a closed request it is taken
// back to work by reopening the request. Every disabled action names the
// reason in its tooltip: the missing permission, else the request's state.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { formatPrice } from '@/core/utils/currency'
import { formatDateOrDash } from '@/core/utils/dates'
import { formatUnit } from '@/shared/utils/units'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import {
  isQuoteRequestOpen,
  linesRestorable,
  quoteLineStateSeverity,
  reopenOffered,
  substituteKind,
} from '../utils/quoteRequestFormat'
import type {
  QuoteRequestLineResponse,
  QuoteRequestResponse,
  QuoteRequestSupplierResponse,
  QuoteResponse,
} from '../types/quoteRequestsResponse'

const props = defineProps<{
  request: QuoteRequestResponse
  /** Why the user may not change the request, '' when they may. */
  writeBlocked: string
  sendBlocked: string
}>()

/** The supplier row chosen per line for the next award. */
const selection = defineModel<Map<number, number>>('selection', { required: true })

const emit = defineEmits<{
  'enter-offer': [row: QuoteRequestSupplierResponse]
  'send-mail': [row: QuoteRequestSupplierResponse]
  'mark-sent': [row: QuoteRequestSupplierResponse]
  'remove-supplier': [row: QuoteRequestSupplierResponse]
  'drop-line': [line: QuoteRequestLineResponse]
  'restore-line': [line: QuoteRequestLineResponse]
  'remove-line': [line: QuoteRequestLineResponse]
  'substitute-line': [line: QuoteRequestLineResponse]
}>()

const { t } = useI18n()
const router = useRouter()

const statusLabel = computed(() => t(`quoteRequests.status.${props.request.status}`).toLowerCase())
/** Why the request takes no change in its state, '' while it is open. */
const stateBlocked = computed(() =>
  isQuoteRequestOpen(props.request) ? '' : t('quoteRequests.blocked.ended', { status: statusLabel.value }),
)
/** Why lines, suppliers and offers may not change, '' when they may. */
const editBlocked = computed(() => props.writeBlocked || stateBlocked.value)
const editable = computed(() => editBlocked.value === '')
/** Why a dropped line may not be taken back, '' when it may. */
const restoreBlocked = computed(() => {
  if (props.writeBlocked) return props.writeBlocked
  if (linesRestorable(props.request)) return ''
  if (reopenOffered(props.request)) return t('quoteRequests.blocked.reopenFirst')
  return t('quoteRequests.blocked.endedOnPurpose', { status: statusLabel.value })
})
const linesMissing = computed(() =>
  props.request.lines.length === 0 ? t('quoteRequests.blocked.noLines') : '',
)
const suppliers = computed(() => props.request.suppliers)

function quoteOf(row: QuoteRequestSupplierResponse, line: QuoteRequestLineResponse): QuoteResponse | null {
  return row.quotes.find((q) => q.line_id === line.id) ?? null
}

function notAsked(row: QuoteRequestSupplierResponse, line: QuoteRequestLineResponse): boolean {
  return row.not_asked_line_ids.includes(line.id)
}

function selectable(row: QuoteRequestSupplierResponse, line: QuoteRequestLineResponse): boolean {
  return editable.value && line.state === 'open' && !quoteOf(row, line)?.no_offer
}

function choose(row: QuoteRequestSupplierResponse, line: QuoteRequestLineResponse): void {
  if (!selectable(row, line)) return
  const next = new Map(selection.value)
  if (next.get(line.id) === row.id) next.delete(line.id)
  else next.set(line.id, row.id)
  selection.value = next
}

function isWinner(row: QuoteRequestSupplierResponse, line: QuoteRequestLineResponse): boolean {
  return line.state === 'awarded' && line.awarded_supplier_id === row.id
}

/** What happened to a voided award: its order was canceled or its line removed. */
function awardVoidedText(line: QuoteRequestLineResponse): string {
  const supplier =
    props.request.suppliers.find((row) => row.id === line.awarded_supplier_id)?.supplier_name ?? ''
  return line.order_number
    ? t('quoteRequests.comparison.awardVoided', { supplier, order: line.order_number })
    : t('quoteRequests.comparison.awardVoidedRemoved', { supplier })
}

function lineTotal(quote: QuoteResponse | null, line: QuoteRequestLineResponse): string | null {
  return quote?.unit_price != null ? formatPrice(Math.round(quote.unit_price * line.quantity)) : null
}

function replacedBy(line: QuoteRequestLineResponse): number | null {
  if (line.substituted_by_line_id === null) return null
  return props.request.lines.find((l) => l.id === line.substituted_by_line_id)?.position ?? null
}

/** Why the line takes no substitute, '' when it does. */
function substituteBlocked(line: QuoteRequestLineResponse): string {
  if (editBlocked.value) return editBlocked.value
  return substituteKind(line) ? '' : t('quoteRequests.substitute.notPossible')
}

function sentLabel(row: QuoteRequestSupplierResponse): string {
  return row.sent_at
    ? t('quoteRequests.comparison.sentAt', { date: formatDateOrDash(row.sent_at) })
    : t('quoteRequests.comparison.notSent')
}
</script>

<template>
  <div class="comparison-wrap">
    <table class="comparison" data-testid="quote-comparison">
      <thead>
        <tr>
          <th class="line-head">{{ t('quoteRequests.comparison.line') }}</th>
          <th v-for="row in suppliers" :key="row.id" class="supplier-head">
            <div class="supplier-name">
              <span>{{ row.supplier_name }}</span>
              <ArchivedOptionTag v-if="row.supplier_archived" />
              <Tag
                v-if="request.cheapest_complete_supplier_id === row.id"
                :value="t('quoteRequests.comparison.cheapestComplete')"
                severity="success"
              />
            </div>
            <div class="supplier-state">
              <span>{{ sentLabel(row) }}</span>
              <Tag
                v-if="row.declined_at"
                :value="t('quoteRequests.comparison.declined')"
                severity="danger"
              />
              <span v-if="row.valid_until">
                {{ t('quoteRequests.comparison.validUntil', { date: formatDateOrDash(row.valid_until) }) }}
              </span>
            </div>
            <div class="supplier-actions">
              <span
                v-tooltip.top="
                  sendBlocked || stateBlocked || linesMissing || t('quoteRequests.actions.sendMail')
                "
              >
                <Button
                  icon="mdi mdi-email-arrow-right-outline"
                  severity="secondary"
                  text
                  rounded
                  size="small"
                  :aria-label="t('quoteRequests.actions.sendMail')"
                  :disabled="!editable || sendBlocked !== '' || request.lines.length === 0"
                  @click="emit('send-mail', row)"
                />
              </span>
              <span v-tooltip.top="editBlocked || linesMissing || t('quoteRequests.actions.markSent')">
                <Button
                  icon="mdi mdi-email-check-outline"
                  severity="secondary"
                  text
                  rounded
                  size="small"
                  :aria-label="t('quoteRequests.actions.markSent')"
                  :disabled="!editable || request.lines.length === 0"
                  @click="emit('mark-sent', row)"
                />
              </span>
              <span v-tooltip.top="editBlocked || t('quoteRequests.actions.enterOffer')">
                <Button
                  icon="mdi mdi-cash-edit"
                  severity="secondary"
                  text
                  rounded
                  size="small"
                  :aria-label="t('quoteRequests.actions.enterOffer')"
                  :disabled="!editable"
                  data-testid="enter-offer"
                  @click="emit('enter-offer', row)"
                />
              </span>
              <span
                v-tooltip.top="
                  editBlocked ||
                  (row.has_awarded_lines
                    ? t('quoteRequests.actions.supplierWon')
                    : t('quoteRequests.actions.removeSupplier'))
                "
              >
                <Button
                  icon="mdi mdi-delete-outline"
                  severity="secondary"
                  text
                  rounded
                  size="small"
                  :aria-label="t('quoteRequests.actions.removeSupplier')"
                  :disabled="!editable || row.has_awarded_lines"
                  @click="emit('remove-supplier', row)"
                />
              </span>
            </div>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="line in request.lines" :key="line.id" :class="{ dropped: line.state === 'dropped' }">
          <td class="line-cell">
            <div class="line-title">
              <span class="muted">{{ line.position }}.</span>
              <span class="line-name">{{ line.item_name }}</span>
              <Tag
                :value="t(`quoteRequests.lineState.${line.state}`)"
                :severity="quoteLineStateSeverity(line.state)"
              />
            </div>
            <div v-if="line.substitute_reason" class="line-substitute">
              <Tag
                v-tooltip.top="line.substitute_reason"
                :value="t('quoteRequests.substitute.tag')"
                severity="warn"
                icon="mdi mdi-swap-horizontal"
              />
              <span class="muted small">{{ line.substitute_reason }}</span>
            </div>
            <div v-if="replacedBy(line) !== null" class="line-substitute muted small">
              {{ t('quoteRequests.substitute.replacedBy', { line: replacedBy(line) }) }}
            </div>
            <div v-if="line.award_voided" class="line-substitute muted small" data-testid="award-voided">
              <i class="mdi mdi-gavel" aria-hidden="true" />
              {{ awardVoidedText(line) }}
            </div>
            <div class="line-meta">
              <span v-if="line.item_code">{{ line.item_code }}</span>
              <span v-if="line.lot_number">{{ line.lot_number }}</span>
              <span v-if="line.project_number">{{ line.project_number }}</span>
              <span>{{ line.quantity }} {{ formatUnit(line.unit) }}</span>
              <span v-if="line.demands.length > 0">
                {{ t('quoteRequests.comparison.demands', { count: line.demands.length }) }}
              </span>
            </div>
            <div class="line-actions">
              <Button
                v-if="line.order_id !== null"
                :label="t('quoteRequests.comparison.order', { number: line.order_number })"
                icon="mdi mdi-open-in-app"
                severity="contrast"
                text
                size="small"
                @click="router.push(`/procurement/orders/${line.order_id}`)"
              />
              <template v-if="line.state === 'open'">
                <span v-tooltip.top="editBlocked || undefined">
                  <Button
                    :label="t('quoteRequests.actions.dropLine')"
                    severity="secondary"
                    text
                    size="small"
                    :disabled="!editable"
                    @click="emit('drop-line', line)"
                  />
                </span>
                <span v-tooltip.top="substituteBlocked(line) || undefined">
                  <Button
                    :label="t('quoteRequests.actions.substituteLine')"
                    severity="secondary"
                    text
                    size="small"
                    :disabled="!editable || substituteBlocked(line) !== ''"
                    data-testid="substitute-line"
                    @click="emit('substitute-line', line)"
                  />
                </span>
                <span v-tooltip.top="editBlocked || undefined">
                  <Button
                    :label="t('quoteRequests.actions.removeLine')"
                    severity="secondary"
                    text
                    size="small"
                    :disabled="!editable"
                    @click="emit('remove-line', line)"
                  />
                </span>
              </template>
              <span v-else-if="line.state === 'dropped'" v-tooltip.top="restoreBlocked || undefined">
                <Button
                  :label="t('quoteRequests.actions.restoreLine')"
                  severity="secondary"
                  text
                  size="small"
                  :disabled="restoreBlocked !== ''"
                  data-testid="restore-line"
                  @click="emit('restore-line', line)"
                />
              </span>
            </div>
          </td>
          <td
            v-for="row in suppliers"
            :key="row.id"
            class="offer-cell"
            :class="{
              cheapest: line.cheapest_supplier_id === row.id,
              chosen: selection.get(line.id) === row.id,
              winner: isWinner(row, line),
              selectable: selectable(row, line),
            }"
            :data-testid="`offer-${line.id}-${row.id}`"
            role="button"
            :tabindex="selectable(row, line) ? 0 : -1"
            :aria-pressed="selection.get(line.id) === row.id"
            :aria-disabled="!selectable(row, line)"
            @click="choose(row, line)"
            @keydown.enter.prevent="choose(row, line)"
            @keydown.space.prevent="choose(row, line)"
          >
            <template v-if="quoteOf(row, line)?.no_offer">
              <Tag :value="t('quoteRequests.comparison.noOffer')" severity="secondary" />
            </template>
            <template v-else-if="quoteOf(row, line)?.unit_price != null">
              <div class="price">{{ formatPrice(quoteOf(row, line)!.unit_price) }}</div>
              <div class="muted small">{{ lineTotal(quoteOf(row, line), line) }}</div>
              <div v-if="quoteOf(row, line)!.lead_time_days != null" class="muted small">
                {{ t('quoteRequests.comparison.leadTime', { days: quoteOf(row, line)!.lead_time_days }) }}
              </div>
              <div v-if="quoteOf(row, line)!.min_quantity != null" class="muted small">
                {{ t('quoteRequests.comparison.minQuantity', { quantity: quoteOf(row, line)!.min_quantity }) }}
              </div>
            </template>
            <span v-else class="muted">{{ t('quoteRequests.comparison.noPrice') }}</span>
            <div
              v-if="quoteOf(row, line)?.substitute_item_name"
              v-tooltip.top="quoteOf(row, line)!.substitute_reason ?? undefined"
              class="alternative"
              data-testid="offer-alternative"
            >
              <Tag
                :value="t('quoteRequests.substitute.alternative')"
                severity="warn"
                icon="mdi mdi-swap-horizontal"
              />
              <span class="alternative-name">{{ quoteOf(row, line)!.substitute_item_name }}</span>
              <span v-if="quoteOf(row, line)!.substitute_item_code" class="muted small">
                {{ quoteOf(row, line)!.substitute_item_code }}
              </span>
            </div>
            <Tag
              v-if="notAsked(row, line)"
              :value="t('quoteRequests.comparison.notAsked')"
              severity="warn"
              class="cell-tag"
            />
            <Tag
              v-if="isWinner(row, line)"
              :value="t('quoteRequests.comparison.won')"
              severity="success"
              icon="mdi mdi-check"
              class="cell-tag"
            />
            <i
              v-else-if="selection.get(line.id) === row.id"
              class="mdi mdi-gavel chosen-icon"
              :aria-label="t('quoteRequests.comparison.chosen')"
            />
          </td>
        </tr>
        <tr v-if="request.lines.length === 0">
          <td :colspan="suppliers.length + 1" class="muted empty">
            {{ t('quoteRequests.comparison.empty') }}
          </td>
        </tr>
      </tbody>
      <tfoot v-if="suppliers.length > 0">
        <tr>
          <th>{{ t('quoteRequests.comparison.linesTotal') }}</th>
          <td v-for="row in suppliers" :key="row.id">{{ formatPrice(row.lines_total) }}</td>
        </tr>
        <tr>
          <th>{{ t('quoteRequests.comparison.extraCosts') }}</th>
          <td v-for="row in suppliers" :key="row.id">{{ formatPrice(row.extra_costs_total) }}</td>
        </tr>
        <tr class="total-row">
          <th>{{ t('quoteRequests.comparison.total') }}</th>
          <td v-for="row in suppliers" :key="row.id">
            {{ formatPrice(row.total) }}
            <small class="muted">
              {{ t('quoteRequests.comparison.priced', { count: row.priced_lines }) }}
            </small>
          </td>
        </tr>
      </tfoot>
    </table>
    <p v-if="suppliers.length === 0" class="muted empty">
      {{ t('quoteRequests.comparison.noSuppliers') }}
    </p>
  </div>
</template>

<style scoped lang="scss">
.comparison-wrap {
  overflow: auto;
  height: 100%;
}

.comparison {
  border-collapse: collapse;
  min-width: 100%;
  font-size: var(--font-size-sm);

  th,
  td {
    border: 1px solid var(--p-content-border-color);
    padding: var(--space-2) var(--space-2);
    vertical-align: top;
    text-align: left;
  }

  thead th {
    position: sticky;
    top: 0;
    background: var(--p-content-background);
    z-index: 1;
  }
}

.line-head {
  min-width: 18rem;
}

.supplier-head {
  min-width: 11rem;
}

.supplier-name,
.line-title {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex-wrap: wrap;
  font-weight: 600;
}

.supplier-state,
.line-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1) var(--space-2);
  color: var(--p-text-muted-color);
  font-weight: 400;
  margin-top: var(--space-1);
}

.supplier-actions,
.line-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  margin-top: var(--space-1);
}

.line-name {
  overflow-wrap: anywhere;
}

.line-substitute {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  margin-top: var(--space-1);
}

.alternative {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-1);
  margin-top: var(--space-1);
}

.alternative-name {
  font-weight: 600;
  overflow-wrap: anywhere;
}

.offer-cell {
  position: relative;
  min-width: 9rem;

  &.selectable {
    cursor: pointer;
  }

  &.selectable:hover {
    background: var(--p-content-hover-background);
  }

  &.cheapest .price {
    color: var(--p-green-600);
    font-weight: 600;
  }

  &.chosen {
    outline: 2px solid var(--p-primary-color);
    outline-offset: -2px;
  }

  &.winner {
    background: var(--p-highlight-background);
  }
}

.cell-tag {
  margin-top: var(--space-1);
}

.chosen-icon {
  position: absolute;
  top: 0.35rem;
  right: 0.35rem;
  color: var(--p-primary-color);
}

.dropped td {
  opacity: 0.6;
}

.total-row {
  font-weight: 600;
}

.muted {
  color: var(--p-text-muted-color);
}

.small {
  font-size: var(--font-size-xs);
}

.empty {
  padding: var(--space-4);
  text-align: center;
}
</style>
