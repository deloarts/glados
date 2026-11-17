<script setup lang="ts">
// Takes accepted pieces of one delivery back. A miscount names its reason;
// damage found after receipt rejects the pieces instead, with a classified
// reason, what happens to them and optional photos. Either way the backend
// books a negative delivery row that names the corrected one, so the
// history keeps both rows.
import { computed, ref, toRef, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAppToast } from '@/core/composables/useAppToast'
import { extractApiError } from '@/core/utils/errors'
import { HelpDrawer } from '@/shared/help'
import { SCRAP_REASONS, scrapReasonLabelKey } from '@/shared/utils/scrapReasons'
import type { ScrapReason } from '@/shared/utils/scrapReasons'
import { useDeliveryPictures } from '../composables/useDeliveryPictures'
import { useOrdersStore } from '../stores/ordersStore'
import type { DeliveryRecord, OrderItemResponse, RejectionOutcome } from '../types/ordersResponse'
import { formatUnit, quantityFractionDigits } from '@/shared/utils/units'

export type CorrectionMode = 'miscount' | 'damage'

const props = withDefaults(
  defineProps<{
    visible: boolean
    item: OrderItemResponse | null
    record: DeliveryRecord | null
    /** What the dialog opens with: a miscount, or damage found after receipt. */
    initialMode?: CorrectionMode
  }>(),
  { initialMode: 'miscount' },
)

const emit = defineEmits<{
  'update:visible': [value: boolean]
  corrected: []
}>()

const { t } = useI18n()
const toast = useAppToast()
const ordersStore = useOrdersStore()
const uid = useId()
const { upload } = useDeliveryPictures(toRef(() => props.item?.order_id ?? null))

// The backend stores at most 1000 characters of the reason and of the note.
const REASON_MAX_LENGTH = 1000
const PICTURE_TYPES = 'image/jpeg,image/png,image/webp'

const mode = ref<CorrectionMode>('miscount')
const quantity = ref<number | null>(null)
const reason = ref('')
const rejectReason = ref<ScrapReason | null>(null)
const rejectOutcome = ref<RejectionOutcome | null>(null)
const rejectNote = ref('')
const pictures = ref<File[]>([])
const pictureInput = ref<HTMLInputElement | null>(null)
const saving = ref(false)
const error = ref<string | null>(null)
const explainVisible = ref(false)

const isDamage = computed(() => mode.value === 'damage')
const reasonOptions = computed(() =>
  SCRAP_REASONS.map((r) => ({ label: t(scrapReasonLabelKey(r)), value: r })),
)

// What the backend accepts: the row's accepted pieces less what earlier
// corrections of the row took back, and never more than the line still
// counts as delivered.
const maxQuantity = computed(() => {
  const record = props.record
  if (!record || !props.item) return 0
  const alreadyCorrected = (props.item.delivery_records ?? [])
    .filter((r) => r.corrects_delivery_id === record.id)
    .reduce((sum, r) => sum + Math.abs(r.quantity), 0)
  const openOnRow = Math.max(0, record.quantity - alreadyCorrected)
  return Math.min(openOnRow, props.item.quantity_delivered)
})
// A MADE line counts pieces of its lot and a counted unit counts whole
// things, so both take whole numbers, as the backend checks.
const fractionDigits = computed(() =>
  props.item?.line_type === 'MADE' ? 0 : quantityFractionDigits(props.item?.unit),
)
const minQuantity = computed(() => (fractionDigits.value === 0 ? 1 : 0.001))
const explained = computed(() =>
  isDamage.value
    ? !!rejectReason.value && !!rejectOutcome.value && rejectNote.value.length <= REASON_MAX_LENGTH
    : reason.value.trim().length > 0 && reason.value.length <= REASON_MAX_LENGTH,
)
const canSubmit = computed(
  () =>
    quantity.value !== null &&
    quantity.value >= minQuantity.value &&
    quantity.value <= maxQuantity.value &&
    explained.value,
)

watch(
  () => props.visible,
  (val) => {
    if (val) {
      mode.value = props.initialMode
      quantity.value = null
      reason.value = ''
      rejectReason.value = null
      rejectOutcome.value = null
      rejectNote.value = ''
      pictures.value = []
      error.value = null
    }
  },
)

function onPicturesPicked(event: Event): void {
  const input = event.target as HTMLInputElement
  pictures.value = [...pictures.value, ...Array.from(input.files ?? [])]
  input.value = ''
}

function removePicture(index: number): void {
  pictures.value = pictures.value.filter((_, i) => i !== index)
}

/** The row the correction just booked: the newest one naming the record. */
function bookedRow(corrected: OrderItemResponse, recordId: number): DeliveryRecord | undefined {
  return (corrected.delivery_records ?? [])
    .filter((r) => r.corrects_delivery_id === recordId)
    .reduce<DeliveryRecord | undefined>((newest, r) => (!newest || r.id > newest.id ? r : newest), undefined)
}

async function submit(): Promise<void> {
  if (!props.item || !props.record || !canSubmit.value || quantity.value === null) return
  saving.value = true
  error.value = null
  try {
    const corrected = await ordersStore.correctDelivery(
      props.item.order_id,
      props.item.id,
      props.record.id,
      isDamage.value
        ? {
            quantity: quantity.value,
            rejection: {
              rejection_reason: rejectReason.value!,
              rejection_outcome: rejectOutcome.value!,
              rejection_note: rejectNote.value.trim() || undefined,
            },
            expected_edit_version: props.item.edit_version,
          }
        : {
            quantity: quantity.value,
            reason: reason.value.trim(),
            expected_edit_version: props.item.edit_version,
          },
    )
    if (isDamage.value) {
      const row = bookedRow(corrected, props.record.id)
      const failed = row ? await upload(props.item.id, row.id, pictures.value) : pictures.value.length
      toast.success(t('orders.delivery.correct.title'), t('orders.delivery.correct.rejectionSuccess'))
      if (failed > 0) {
        toast.warn(
          t('orders.delivery.correct.title'),
          t('orders.delivery.correct.picturesFailed', { count: failed }),
        )
      }
    } else {
      toast.success(t('orders.delivery.correct.title'), t('orders.delivery.correct.success'))
    }
    emit('corrected')
    emit('update:visible', false)
  } catch (e) {
    error.value = extractApiError(e) ?? t('orders.items.errors.unknown')
  } finally {
    saving.value = false
  }
}

defineExpose({ mode, canSubmit })
</script>

<template>
  <Dialog
    :visible="visible"
    @update:visible="emit('update:visible', $event)"
    modal
    :style="{ width: 'var(--dialog-width-sm)' }"
  >
    <template #header>
      <div class="correct-header">
        <span class="p-dialog-title">{{ t('orders.delivery.correct.title') }}</span>
        <Button
          type="button"
          class="correct-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('orders.delivery.correct.explain')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('orders.delivery.correct.explain')"
          @click="explainVisible = true"
        />
      </div>
    </template>
    <div class="correct-body">
      <div class="field">
        <span :id="`${uid}-mode-label`">{{ t('orders.delivery.correct.mode') }}</span>
        <div class="mode-options" role="radiogroup" :aria-labelledby="`${uid}-mode-label`">
          <div class="mode-option">
            <RadioButton
              v-model="mode"
              :input-id="`${uid}-mode-miscount`"
              value="miscount"
              :name="`${uid}-mode`"
              data-testid="correct-mode-miscount"
            />
            <label :for="`${uid}-mode-miscount`">{{
              t('orders.delivery.correct.modeOptions.miscount')
            }}</label>
          </div>
          <div class="mode-option">
            <RadioButton
              v-model="mode"
              :input-id="`${uid}-mode-damage`"
              value="damage"
              :name="`${uid}-mode`"
              data-testid="correct-mode-damage"
            />
            <label :for="`${uid}-mode-damage`">{{
              t('orders.delivery.correct.modeOptions.damage')
            }}</label>
          </div>
        </div>
      </div>
      <div class="field">
        <label for="correct-quantity">{{ t('orders.delivery.correct.quantity') }}</label>
        <InputNumber
          v-model="quantity"
          input-id="correct-quantity"
          :min="minQuantity"
          :max="maxQuantity"
          :max-fraction-digits="fractionDigits"
          :suffix="` / ${maxQuantity} ${formatUnit(item?.unit)}`"
          data-testid="correct-quantity"
        />
      </div>
      <div v-if="!isDamage" class="field">
        <label for="correct-reason">{{ t('orders.delivery.correct.reason') }}</label>
        <Textarea
          id="correct-reason"
          v-model="reason"
          rows="3"
          auto-resize
          :maxlength="REASON_MAX_LENGTH"
          data-testid="correct-reason"
        />
      </div>
      <template v-else>
        <div class="field">
          <label :id="`${uid}-reject-reason-label`" :for="`${uid}-reject-reason`"
            >{{ t('orders.delivery.reject.reason') }} *</label
          >
          <Select
            v-model="rejectReason"
            :input-id="`${uid}-reject-reason`"
            :aria-labelledby="`${uid}-reject-reason-label`"
            :options="reasonOptions"
            option-label="label"
            option-value="value"
            :placeholder="t('orders.delivery.reject.reasonPlaceholder')"
            fluid
            data-testid="correct-reject-reason"
          />
        </div>
        <div class="field">
          <span :id="`${uid}-outcome-label`">{{ t('orders.delivery.reject.outcome') }} *</span>
          <div class="mode-options" role="radiogroup" :aria-labelledby="`${uid}-outcome-label`">
            <div class="mode-option">
              <RadioButton
                v-model="rejectOutcome"
                :input-id="`${uid}-outcome-redeliver`"
                value="redeliver"
                :name="`${uid}-outcome`"
                data-testid="correct-outcome-redeliver"
              />
              <label :for="`${uid}-outcome-redeliver`">{{
                t('orders.delivery.reject.outcomeOptions.redeliver')
              }}</label>
            </div>
            <div class="mode-option">
              <RadioButton
                v-model="rejectOutcome"
                :input-id="`${uid}-outcome-lost`"
                value="lost"
                :name="`${uid}-outcome`"
                data-testid="correct-outcome-lost"
              />
              <label :for="`${uid}-outcome-lost`">{{
                t('orders.delivery.reject.outcomeOptions.lost')
              }}</label>
            </div>
          </div>
        </div>
        <Message
          v-if="rejectOutcome === 'lost' && item?.line_type !== 'MADE'"
          severity="info"
          size="small"
          :closable="false"
        >
          {{ t('orders.delivery.reject.lostHint') }}
        </Message>
        <div class="field">
          <label :for="`${uid}-reject-note`">{{ t('orders.delivery.reject.note') }}</label>
          <Textarea
            :id="`${uid}-reject-note`"
            v-model="rejectNote"
            rows="2"
            auto-resize
            :maxlength="REASON_MAX_LENGTH"
            data-testid="correct-reject-note"
          />
        </div>
        <div class="field">
          <span>{{ t('orders.delivery.correct.pictures') }}</span>
          <small>{{ t('orders.delivery.correct.picturesHint') }}</small>
          <ul v-if="pictures.length" class="picked-pictures">
            <li v-for="(picture, index) in pictures" :key="`${picture.name}-${index}`">
              <i class="mdi mdi-image-outline" aria-hidden="true" />
              <span class="picked-name">{{ picture.name }}</span>
              <Button
                icon="mdi mdi-close"
                size="small"
                severity="secondary"
                text
                rounded
                :aria-label="t('orders.items.deliveryHistory.removePicture')"
                @click="removePicture(index)"
              />
            </li>
          </ul>
          <Button
            :label="t('orders.items.deliveryHistory.addPicture')"
            icon="mdi mdi-camera-outline"
            severity="secondary"
            outlined
            size="small"
            class="add-picture"
            data-testid="correct-add-picture"
            @click="pictureInput?.click()"
          />
          <input
            ref="pictureInput"
            type="file"
            class="hidden-input"
            aria-hidden="true"
            tabindex="-1"
            multiple
            :accept="PICTURE_TYPES"
            data-testid="correct-picture-input"
            @change="onPicturesPicked"
          />
        </div>
      </template>
      <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>
    </div>

    <template #footer>
      <Button
        :label="t('common.cancel')"
        severity="secondary"
        outlined
        :disabled="saving"
        @click="emit('update:visible', false)"
      />
      <Button
        :label="
          isDamage ? t('orders.delivery.correct.submitRejection') : t('orders.delivery.correct.submit')
        "
        :icon="isDamage ? 'mdi mdi-package-variant-remove' : 'mdi mdi-undo-variant'"
        severity="warn"
        :loading="saving"
        :disabled="!canSubmit"
        data-testid="correct-submit"
        @click="submit"
      />
    </template>
  </Dialog>

  <HelpDrawer v-model:visible="explainVisible" slug="procurement/delivery-correction" />
</template>

<style scoped lang="scss">
.correct-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.correct-explain-button :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.correct-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.field {
  gap: var(--space-2);
}

.mode-options {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.mode-option {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.picked-pictures {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin: 0;
  padding: 0;
  list-style: none;
}

.picked-pictures li {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

.picked-name {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.add-picture {
  width: fit-content;
}

.hidden-input {
  display: none;
}
</style>
