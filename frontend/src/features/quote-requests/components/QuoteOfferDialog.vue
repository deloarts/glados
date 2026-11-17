<script setup lang="ts">
// Records one supplier's offer as a whole: a unit price or "no offer" per
// line with lead time and minimum quantity, an alternative item the
// supplier offers instead of a line's own with its reason, the extra costs
// of the offer, how long it is valid and whether the supplier declined to
// quote.
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { currencyInputPrefix } from '@/core/utils/currency'
import { dateToParam, toLocalDayStart } from '@/core/utils/dates'
import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { formatUnit } from '@/shared/utils/units'
import { extraCostDraftError } from '@/shared/utils/extraCosts'
import ExtraCostsEditor from '@/shared/components/extra-costs/ExtraCostsEditor.vue'
import { saveQuoteRequestOffer } from '../api/saveQuoteRequestOffer'
import { useHostStore } from '@/core/host/stores/hostStore'
import { substituteKind } from '../utils/quoteRequestFormat'
import OfferFilesSection from './OfferFilesSection.vue'
import SubstituteItemSelect from './SubstituteItemSelect.vue'
import type { ExtraCostDraft } from '@/shared/utils/extraCosts'
import type { SubstituteItemOption } from '../api/searchSubstituteItems'
import type {
  QuoteRequestLineResponse,
  QuoteRequestResponse,
  QuoteRequestSupplierResponse,
  QuoteResponse,
} from '../types/quoteRequestsResponse'

const emit = defineEmits<{ saved: [request: QuoteRequestResponse] }>()

const { t } = useI18n()
const { submitting, errorMessage, run } = useSubmitAction()
const hostStore = useHostStore()

interface QuoteDraft {
  line: QuoteRequestLineResponse
  price: number | null
  noOffer: boolean
  leadTimeDays: number | null
  minQuantity: number | null
  /** The catalogue an alternative comes from, null when the line takes none. */
  altKind: 'BOUGHT' | 'SOURCE' | null
  altOpen: boolean
  altItem: SubstituteItemOption | null
  altReason: string
}

const visible = ref(false)
const request = ref<QuoteRequestResponse | null>(null)
const row = ref<QuoteRequestSupplierResponse | null>(null)
const quotes = ref<QuoteDraft[]>([])
const costs = ref<ExtraCostDraft[]>([])
const validUntil = ref<Date | null>(null)
const declined = ref(false)
const note = ref('')

const lineOptions = computed(() =>
  (request.value?.lines ?? [])
    .filter((line) => line.state !== 'dropped')
    .map((line) => ({ value: line.id, label: `${line.position}. ${line.item_name}` })),
)

function alternativeDraft(
  line: QuoteRequestLineResponse,
  quote: QuoteResponse | undefined,
): Pick<QuoteDraft, 'altKind' | 'altOpen' | 'altItem' | 'altReason'> {
  const itemId = quote?.substitute_bought_item_id ?? quote?.substitute_source_item_id ?? null
  return {
    altKind: substituteKind(line),
    altOpen: itemId !== null,
    altItem:
      itemId !== null
        ? { id: itemId, name: quote?.substitute_item_name ?? '', code: quote?.substitute_item_code ?? '' }
        : null,
    altReason: quote?.substitute_reason ?? '',
  }
}

/** The alternative a draft sends, or null when it names none. */
function alternativeOf(q: QuoteDraft): SubstituteItemOption | null {
  return q.altOpen && !q.noOffer && q.altKind !== null ? q.altItem : null
}

function clearAlternative(q: QuoteDraft): void {
  q.altOpen = false
  q.altItem = null
  q.altReason = ''
}

function ownItemId(line: QuoteRequestLineResponse): number | null {
  return line.line_type === 'BOUGHT' ? line.bought_item_id : line.source_item_id
}

function open(target: QuoteRequestResponse, supplier: QuoteRequestSupplierResponse): void {
  request.value = target
  row.value = supplier
  const byLine = new Map(supplier.quotes.map((q) => [q.line_id, q]))
  quotes.value = target.lines
    .filter((line) => line.state !== 'dropped')
    .map((line) => {
      const quote = byLine.get(line.id)
      return {
        line,
        price: quote?.unit_price != null ? quote.unit_price / 100 : null,
        noOffer: quote?.no_offer ?? false,
        leadTimeDays: quote?.lead_time_days ?? null,
        minQuantity: quote?.min_quantity ?? null,
        ...alternativeDraft(line, quote),
      }
    })
  costs.value = supplier.extra_costs.map((c) => ({
    kind: c.kind,
    amount: c.amount,
    label: c.label ?? '',
    note: c.note ?? '',
    lineId: c.line_id,
  }))
  validUntil.value = supplier.valid_until ? toLocalDayStart(supplier.valid_until) : null
  declined.value = supplier.declined_at !== null
  note.value = supplier.note ?? ''
  errorMessage.value = null
  visible.value = true
}

async function onSave(): Promise<void> {
  const target = request.value
  const supplier = row.value
  if (!target || !supplier) return
  const invalid = extraCostDraftError(costs.value)
  if (invalid) {
    errorMessage.value = t(invalid)
    return
  }
  await run(async () => {
    const saved = await saveQuoteRequestOffer(target.id, supplier.id, {
      quotes: quotes.value
        .filter(
          (q) => q.noOffer || q.price !== null || q.leadTimeDays !== null || alternativeOf(q) !== null,
        )
        .map((q) => {
          const alternative = alternativeOf(q)
          return {
            line_id: q.line.id,
            unit_price: q.noOffer || q.price === null ? null : Math.round(q.price * 100),
            no_offer: q.noOffer,
            lead_time_days: q.leadTimeDays,
            min_quantity: q.minQuantity,
            substitute_bought_item_id: alternative && q.altKind === 'BOUGHT' ? alternative.id : null,
            substitute_source_item_id: alternative && q.altKind === 'SOURCE' ? alternative.id : null,
            substitute_reason: alternative ? q.altReason.trim() || null : null,
          }
        }),
      extra_costs: costs.value.map((c) => ({
        kind: c.kind,
        amount: c.amount ?? 0,
        label: c.label.trim() || null,
        note: c.note.trim() || null,
        line_id: c.lineId,
      })),
      valid_until: dateToParam(validUntil.value),
      declined: declined.value,
      note: note.value.trim() || null,
    })
    visible.value = false
    emit('saved', saved)
  }, t('quoteRequests.offer.errors.unknown'))
}

defineExpose({ open })
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('quoteRequests.offer.title', { supplier: row?.supplier_name ?? '' })"
    :style="{ width: 'var(--dialog-width-lg)' }"
  >
    <div class="offer-form">
      <fieldset class="dialog-section">
        <legend>{{ t('quoteRequests.offer.prices') }}</legend>
        <div v-for="quote in quotes" :key="quote.line.id" class="quote-row" data-testid="offer-line">
          <div class="quote-line">
            <span class="quote-name">{{ quote.line.position }}. {{ quote.line.item_name }}</span>
            <small class="quote-qty">
              {{ quote.line.quantity }} {{ formatUnit(quote.line.unit)
              }}<template v-if="quote.line.item_code"> · {{ quote.line.item_code }}</template>
            </small>
          </div>
          <div class="field">
            <label :for="`offer-price-${quote.line.id}`">{{ t('quoteRequests.offer.unitPrice') }}</label>
            <InputNumber
              v-model="quote.price"
              :input-id="`offer-price-${quote.line.id}`"
              :min="0"
              :min-fraction-digits="2"
              :max-fraction-digits="2"
              :prefix="currencyInputPrefix()"
              :disabled="quote.noOffer || submitting"
              fluid
            />
          </div>
          <div class="field">
            <label :for="`offer-lead-${quote.line.id}`">{{ t('quoteRequests.offer.leadTime') }}</label>
            <InputNumber
              v-model="quote.leadTimeDays"
              :input-id="`offer-lead-${quote.line.id}`"
              :min="0"
              :max="3650"
              :disabled="quote.noOffer || submitting"
              fluid
            />
          </div>
          <div class="field">
            <label :for="`offer-min-${quote.line.id}`">{{ t('quoteRequests.offer.minQuantity') }}</label>
            <InputNumber
              v-model="quote.minQuantity"
              :input-id="`offer-min-${quote.line.id}`"
              :min="0.001"
              :max-fraction-digits="3"
              :disabled="quote.noOffer || submitting"
              fluid
            />
          </div>
          <div class="no-offer">
            <Checkbox
              v-model="quote.noOffer"
              :input-id="`offer-none-${quote.line.id}`"
              binary
              :disabled="submitting"
            />
            <label :for="`offer-none-${quote.line.id}`">{{ t('quoteRequests.offer.noOffer') }}</label>
          </div>
          <div v-if="quote.altKind !== null && !quote.noOffer" class="alternative">
            <Button
              v-if="!quote.altOpen"
              class="add-alternative"
              icon="mdi mdi-swap-horizontal"
              :label="t('quoteRequests.offer.addAlternative')"
              severity="secondary"
              text
              size="small"
              :disabled="submitting"
              data-testid="offer-add-alternative"
              @click="quote.altOpen = true"
            />
            <template v-else>
              <div class="field">
                <label :id="`offer-alt-${quote.line.id}-label`" :for="`offer-alt-${quote.line.id}`">{{ t('quoteRequests.offer.alternative') }}</label>
                <SubstituteItemSelect
                  v-model="quote.altItem"
                  :kind="quote.altKind"
                  :exclude-id="ownItemId(quote.line)"
                  :input-id="`offer-alt-${quote.line.id}`"
                  :aria-labelledby="`offer-alt-${quote.line.id}-label`"
                  :disabled="submitting"
                />
              </div>
              <div class="field">
                <label :for="`offer-alt-reason-${quote.line.id}`">
                  {{ t('quoteRequests.offer.alternativeReason') }}
                </label>
                <InputText
                  :id="`offer-alt-reason-${quote.line.id}`"
                  v-model="quote.altReason"
                  :disabled="submitting"
                  fluid
                />
              </div>
              <Button
                v-tooltip.top="t('quoteRequests.offer.removeAlternative')"
                icon="mdi mdi-close"
                severity="secondary"
                text
                rounded
                size="small"
                :aria-label="t('quoteRequests.offer.removeAlternative')"
                :disabled="submitting"
                @click="clearAlternative(quote)"
              />
            </template>
          </div>
        </div>
      </fieldset>

      <fieldset class="dialog-section">
        <legend>{{ t('quoteRequests.offer.extraCosts') }}</legend>
        <ExtraCostsEditor
          v-model="costs"
          :line-options="lineOptions"
          :whole-label="t('quoteRequests.offer.wholeOffer')"
          :disabled="submitting"
        />
      </fieldset>

      <fieldset v-if="hostStore.storageEnabled && row" class="dialog-section">
        <legend>{{ t('quoteRequests.offer.documents') }}</legend>
        <OfferFilesSection :supplier-row-id="row.id" :can-write="!submitting" />
      </fieldset>

      <fieldset class="dialog-section">
        <legend>{{ t('quoteRequests.offer.details') }}</legend>
        <div class="details">
          <div class="details-row">
            <div class="field valid-until">
              <label for="offer-valid-until">{{ t('quoteRequests.offer.validUntil') }}</label>
              <DatePicker
                v-model="validUntil"
                input-id="offer-valid-until"
                show-button-bar
                show-clear
                fluid
              />
            </div>
            <div class="no-offer declined">
              <Checkbox v-model="declined" input-id="offer-declined" binary />
              <label for="offer-declined">{{ t('quoteRequests.offer.declined') }}</label>
            </div>
          </div>
          <div class="field">
            <label for="offer-note">{{ t('quoteRequests.offer.note') }}</label>
            <Textarea id="offer-note" v-model="note" rows="3" auto-resize fluid />
          </div>
        </div>
      </fieldset>
    </div>

    <template #footer>
      <Message v-if="errorMessage" severity="error" :closable="false" class="footer-error">
        {{ errorMessage }}
      </Message>
      <Button
        :label="t('common.cancel')"
        severity="secondary"
        text
        :disabled="submitting"
        @click="visible = false"
      />
      <Button
        icon="mdi mdi-content-save-outline"
        :label="t('common.save')"
        :loading="submitting"
        @click="onSave"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.offer-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.quote-row {
  display: grid;
  grid-template-columns: 1fr 9rem 7rem 7rem auto;
  gap: var(--space-2);
  align-items: end;
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--p-content-border-color);
}

.alternative {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
  gap: var(--space-2);
  align-items: end;

  > .add-alternative {
    justify-self: start;
  }
}

.quote-line {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.quote-name {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.quote-qty {
  color: var(--p-text-muted-color);
}

.field {
  label {
    font-size: var(--font-size-sm);
  }
}

.details {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

// The date and the declined switch share a row; the note gets the full
// width below them.
.details-row {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--space-2) var(--space-5);
}

.valid-until {
  width: 14rem;
}

.declined {
  // Centres the switch on the date input next to it.
  padding-bottom: var(--space-3);
  white-space: nowrap;
}

.no-offer {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding-bottom: var(--space-2);
  font-size: var(--font-size-sm);
}

.footer-error {
  margin-right: auto;
}

@media (max-width: $bp-md) {
  .quote-row {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
