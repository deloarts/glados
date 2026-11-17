<script setup lang="ts">
// Awards the chosen lines: per winning supplier the order the lines go onto,
// a new draft order or one of its existing drafts or partially ordered
// orders, and the extra costs to book on it. A supplier's offer costs are
// filled in; those of a line it did not win are left out. A line won with an
// alternative item names the item that goes onto the order. After the award
// it lists the orders and what the award did differently, such as a demand
// share cut to what it still needed.
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { extraCostDraftError } from '@/shared/utils/extraCosts'
import ExtraCostsEditor from '@/shared/components/extra-costs/ExtraCostsEditor.vue'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import { awardQuoteRequest } from '../api/awardQuoteRequest'
import { getSupplierDraftOrders } from '../api/getSupplierDraftOrders'
import type { ExtraCostDraft } from '@/shared/utils/extraCosts'
import type {
  QuoteRequestAwardResponse,
  QuoteRequestResponse,
  QuoteRequestSupplierResponse,
} from '../types/quoteRequestsResponse'

const emit = defineEmits<{ awarded: [result: QuoteRequestAwardResponse] }>()

const { t } = useI18n()
const router = useRouter()
const { submitting, errorMessage, run } = useSubmitAction()

interface WinnerDraft {
  row: QuoteRequestSupplierResponse
  lineIds: number[]
  targetOrderId: number | null
  drafts: { id: number; order_number: string }[]
  costs: ExtraCostDraft[]
}

const visible = ref(false)
const request = ref<QuoteRequestResponse | null>(null)
const awards = ref<Map<number, number>>(new Map())
const winners = ref<WinnerDraft[]>([])
const result = ref<QuoteRequestAwardResponse | null>(null)

function lineName(lineId: number): string {
  const line = request.value?.lines.find((l) => l.id === lineId)
  return line ? `${line.position}. ${line.item_name}` : `#${lineId}`
}

/** The line as it goes onto the winner's order, with the alternative item
 * the winner quoted instead of the line's own. */
function wonLineName(row: QuoteRequestSupplierResponse, lineId: number): string {
  const alternative = row.quotes.find((q) => q.line_id === lineId)?.substitute_item_name
  return alternative
    ? t('quoteRequests.award.withAlternative', { line: lineName(lineId), item: alternative })
    : lineName(lineId)
}

const orderOptions = (winner: WinnerDraft) => [
  { value: null, label: t('quoteRequests.award.newOrder') },
  ...winner.drafts.map((d) => ({ value: d.id, label: d.order_number })),
]

async function open(target: QuoteRequestResponse, chosen: Map<number, number>): Promise<void> {
  request.value = target
  awards.value = new Map(chosen)
  result.value = null
  errorMessage.value = null
  const byRow = new Map<number, number[]>()
  for (const [lineId, rowId] of chosen) byRow.set(rowId, [...(byRow.get(rowId) ?? []), lineId])
  winners.value = target.suppliers
    .filter((row) => byRow.has(row.id))
    .map((row) => {
      const lineIds = byRow.get(row.id) ?? []
      return {
        row,
        lineIds,
        targetOrderId: null,
        drafts: [],
        costs: row.extra_costs
          .filter((c) => c.line_id === null || lineIds.includes(c.line_id))
          .map((c) => ({
            kind: c.kind,
            amount: c.amount,
            label: c.label ?? '',
            note: c.note ?? '',
            lineId: c.line_id,
          })),
      }
    })
  visible.value = true
  for (const winner of winners.value) {
    try {
      winner.drafts = await getSupplierDraftOrders(winner.row.supplier_id)
    } catch {
      winner.drafts = []
    }
  }
}

const lineCount = computed(() => awards.value.size)

async function onAward(): Promise<void> {
  const target = request.value
  if (!target) return
  for (const winner of winners.value) {
    const invalid = extraCostDraftError(winner.costs)
    if (invalid) {
      errorMessage.value = t(invalid)
      return
    }
  }
  await run(async () => {
    const awarded = await awardQuoteRequest(target.id, {
      expected_edit_version: target.edit_version,
      awards: [...awards.value].map(([lineId, rowId]) => ({
        line_id: lineId,
        supplier_row_id: rowId,
      })),
      suppliers: winners.value.map((winner) => ({
        supplier_row_id: winner.row.id,
        target_order_id: winner.targetOrderId,
        extra_costs: winner.costs.map((c) => ({
          kind: c.kind,
          amount: c.amount ?? 0,
          label: c.label.trim() || null,
          note: c.note.trim() || null,
          line_id: c.lineId,
        })),
      })),
    })
    result.value = awarded
    emit('awarded', awarded)
  }, t('quoteRequests.award.errors.unknown'))
}

function openOrder(orderId: number): void {
  visible.value = false
  void router.push(`/procurement/orders/${orderId}`)
}

defineExpose({ open })
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('quoteRequests.award.title')"
    :style="{ width: 'var(--dialog-width-lg)' }"
  >
    <div v-if="result" class="award-result" data-testid="award-result">
      <p>{{ t('quoteRequests.award.done', { count: result.orders.length }) }}</p>
      <ul class="order-list">
        <li v-for="order in result.orders" :key="order.order_id">
          <Button
            :label="order.order_number"
            icon="mdi mdi-open-in-app"
            severity="contrast"
            text
            size="small"
            @click="openOrder(order.order_id)"
          />
          <span class="muted">{{ order.supplier_name }}</span>
          <Tag
            :value="t(order.created ? 'quoteRequests.award.created' : 'quoteRequests.award.added')"
            severity="secondary"
          />
        </li>
      </ul>
      <Message
        v-for="warning in result.warnings"
        :key="`${warning.line_id}-${warning.kind}`"
        severity="warn"
        :closable="false"
      >
        {{ warning.message }}
      </Message>
    </div>

    <div v-else class="award-form">
      <p class="intro">{{ t('quoteRequests.award.intro', { count: lineCount }) }}</p>
      <fieldset v-for="winner in winners" :key="winner.row.id" class="dialog-section">
        <legend>
          {{ winner.row.supplier_name }}
          <ArchivedOptionTag
            v-if="winner.row.supplier_archived"
            :tooltip="t('quoteRequests.award.archivedSupplier')"
          />
        </legend>
        <p class="lines">{{ winner.lineIds.map((id) => wonLineName(winner.row, id)).join(', ') }}</p>
        <div class="field">
          <label :id="`award-order-${winner.row.id}-label`" :for="`award-order-${winner.row.id}`">{{ t('quoteRequests.award.order') }}</label>
          <Select
            v-model="winner.targetOrderId"
            :input-id="`award-order-${winner.row.id}`"
            :aria-labelledby="`award-order-${winner.row.id}-label`"
            :options="orderOptions(winner)"
            option-label="label"
            option-value="value"
            fluid
          />
        </div>
        <div class="field">
          <span class="field-label">{{ t('quoteRequests.award.extraCosts') }}</span>
          <ExtraCostsEditor
            v-model="winner.costs"
            :line-options="winner.lineIds.map((id) => ({ value: id, label: lineName(id) }))"
            :disabled="submitting"
          />
        </div>
      </fieldset>
    </div>

    <template #footer>
      <Message v-if="errorMessage" severity="error" :closable="false" class="footer-error">
        {{ errorMessage }}
      </Message>
      <template v-if="result">
        <Button :label="t('common.close')" @click="visible = false" />
      </template>
      <template v-else>
        <Button
          :label="t('common.cancel')"
          severity="secondary"
          text
          :disabled="submitting"
          @click="visible = false"
        />
        <Button
          icon="mdi mdi-gavel"
          :label="t('quoteRequests.award.submit')"
          :loading="submitting"
          data-testid="award-submit"
          @click="onAward"
        />
      </template>
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.award-form,
.award-result {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.intro,
.lines {
  margin: 0;
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.field {
  margin-top: var(--space-2);

  label,
  .field-label {
    font-size: var(--font-size-sm);
  }
}

.order-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);

  li {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
}

.muted {
  color: var(--p-text-muted-color);
}

.footer-error {
  margin-right: auto;
}
</style>
