<script setup lang="ts">
import { computed, inject } from 'vue'
import { useI18n } from 'vue-i18n'

import { dateToParam as toDateParam } from '@/core/utils/dates'
import ClickableOrderNumber from './ClickableOrderNumber.vue'
import { LOTS_TABLE_STEP_CONTEXT_KEY } from './lotsTableStepContext'
import {
  formatMinutesDuration,
  deliveryNoteLine,
  pickupLine,
  plannedAttributionTooltip,
  plannedDateTooltip,
  positionStatusTooltip,
  stepMethodLabel,
} from '../../../utils/lotStepDisplay'
import {
  groupBreakdownTooltip,
  groupMethodLabel,
  groupNoteLine,
  groupPerPiece,
  groupSetupMinutes,
  groupTotalMinutes,
} from '../../utils/lotPositionGroups'
import { lotPositionStatusKey, lotPositionStatusSeverityFor } from '../../../utils/lotStatus'

import type { StepCellKind } from '../../utils/lotStepColumns'
import type { LotStepGroup } from '../../utils/lotPositionGroups'
import type { LotSummaryResponse } from '../../../types/productionLotsResponse'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { InQuotationTag } from '@/features/quote-requests'

const props = defineProps<{
  kind: StepCellKind
  lot: LotSummaryResponse
  group?: LotStepGroup
}>()

const { t, locale } = useI18n()
const ctx = inject(LOTS_TABLE_STEP_CONTEXT_KEY)!

// The step that carries the position-level facts (status, planned/delivery
// info, machine/order), identical across every step of a group, since the
// backend denormalizes them onto each step of the same position.
const primary = computed(() => props.group?.primary)
const isCombined = computed(() => (props.group?.steps.length ?? 0) > 1)

const plannedInfo = computed(() => ctx.stepPlannedInfo(props.lot, primary.value))
const confirmedInfo = computed(() => ctx.stepConfirmedDelivery(props.lot, primary.value))
const editTarget = computed(() => ctx.stepPlannedEditTarget(props.lot, primary.value))
const sourceOrderInfo = computed(() => ctx.stepSourceOrderInfo(props.lot, primary.value))
const position = computed(() => ctx.stepPosition(props.lot, primary.value))

const methodLabel = computed(() =>
  props.group ? groupMethodLabel(props.group, locale.value) : '',
)
const buttonLabel = computed(() => {
  if (!props.group) return ''
  return isCombined.value ? `${methodLabel.value} (${props.group.steps.length})` : methodLabel.value
})
const combinedTooltip = computed(() =>
  props.group ? groupBreakdownTooltip(props.group, position.value, t) : undefined,
)
const attributionTooltip = computed(() =>
  plannedInfo.value ? plannedAttributionTooltip(plannedInfo.value, t) : undefined,
)
const statusTooltip = computed(() =>
  primary.value ? positionStatusTooltip(primary.value, position.value, t) : undefined,
)
const dateTooltip = computed(() =>
  plannedInfo.value ? plannedDateTooltip(plannedInfo.value, t) : undefined,
)

const setupMinutes = computed(() => (props.group ? groupSetupMinutes(props.group) : null))
const perPiece = computed(() => (props.group ? groupPerPiece(props.group) : null))
const totalMinutes = computed(() => (props.group ? groupTotalMinutes(props.group) : null))
const noteLine = computed(() => (props.group ? groupNoteLine(props.group) : null))
const noteTooltip = computed(() => {
  if (!props.group || !isCombined.value) return undefined
  return props.group.steps
    .map((step) => `${stepMethodLabel(step)}: ${step.note ?? getEmptyPlaceholder()}`)
    .join('\n')
})

function onEditPlannedDate(): void {
  if (editTarget.value) ctx.openSetPlannedDate(editTarget.value)
}

function onMethodClick(event: MouseEvent): void {
  if (primary.value) ctx.onStepClick(props.lot, primary.value, event)
}
</script>

<template>
  <template v-if="kind === 'method'">
    <Button
      v-if="group && primary && ctx.isStepClickable(lot, primary)"
      :label="buttonLabel"
      size="small"
      :outlined="!ctx.isStepSelected(lot, primary)"
      :loading="ctx.isStepResolving(lot, primary)"
      v-tooltip.top="combinedTooltip"
      @click="onMethodClick"
    />
    <div v-else-if="group && primary" class="step-method-cell" v-tooltip.top="combinedTooltip">
      <span class="step-method-name">
        {{ methodLabel }}
        <Tag
          v-if="isCombined"
          :value="`${group.steps.length}`"
          severity="secondary"
          class="step-count-badge"
          v-tooltip.top="combinedTooltip"
        />
      </span>
      <span class="item-code">
        <template v-if="sourceOrderInfo">
          <ClickableOrderNumber
            v-if="sourceOrderInfo.orderId !== null && sourceOrderInfo.orderNumber"
            :order-id="sourceOrderInfo.orderId"
            :order-number="sourceOrderInfo.orderNumber"
          /><template
            v-if="sourceOrderInfo.orderId !== null && sourceOrderInfo.machineNames.length > 0"
            >, </template
          >{{ sourceOrderInfo.machineNames.join(', ') }}
        </template>
        <template v-else>{{ getEmptyPlaceholder() }}</template>
      </span>
    </div>
    <span v-else class="step-cell step-cell--empty">{{ getEmptyPlaceholder() }}</span>
  </template>

  <template v-else-if="kind === 'status'">
    <Tag
      v-if="primary"
      :value="
        t(
          `production.lots.positionStatus.${lotPositionStatusKey(primary.position_status, primary.position_kind)}`,
        )
      "
      :severity="lotPositionStatusSeverityFor(primary.position_status, primary.position_kind)"
      v-tooltip.top="statusTooltip"
    />
    <span v-else class="step-cell step-cell--empty">{{ getEmptyPlaceholder() }}</span>
    <InQuotationTag v-if="position" :requests="ctx.quoteRequestsOf(position.id)" />
  </template>

  <template v-else-if="kind === 'setup'">
    <span v-if="group && setupMinutes != null" class="step-cell">{{
      formatMinutesDuration(setupMinutes)
    }}</span>
    <span v-else-if="group" class="step-cell">{{ getEmptyPlaceholder() }}</span>
    <span v-else class="step-cell step-cell--empty">{{ getEmptyPlaceholder() }}</span>
  </template>

  <template v-else-if="kind === 'perPiece'">
    <div v-if="group && perPiece && !perPiece.estimated" class="step-cell-stack">
      <span class="step-cell">{{ formatMinutesDuration(perPiece.minutes) }}</span>
      <span
        v-if="totalMinutes !== null"
        class="step-cell-total"
        v-tooltip.top="
          t('production.lots.columns.stepTotalTimeTooltip', {
            quantity: primary!.position_quantity,
          })
        "
        >{{ formatMinutesDuration(totalMinutes) }}</span
      >
    </div>
    <div v-else-if="group && perPiece && perPiece.estimated" class="step-cell-stack">
      <span
        class="step-cell step-cell--estimated"
        v-tooltip.top="t('production.lots.columns.stepPerPieceEstimateTooltip')"
        >{{ formatMinutesDuration(perPiece.minutes) }}</span
      >
      <span
        v-if="totalMinutes !== null"
        class="step-cell-total"
        v-tooltip.top="
          t('production.lots.columns.stepTotalTimeTooltip', {
            quantity: primary!.position_quantity,
          })
        "
        >{{ formatMinutesDuration(totalMinutes) }}</span
      >
    </div>
    <span v-else-if="group" class="step-cell">{{ getEmptyPlaceholder() }}</span>
    <span v-else class="step-cell step-cell--empty">{{ getEmptyPlaceholder() }}</span>
  </template>

  <template v-else-if="kind === 'plannedStart'">
    <div v-if="plannedInfo" class="delivery-cell">
      <span class="delivery-date-row">
        <span v-if="plannedInfo.startDate">{{ toDateParam(plannedInfo.startDate) }}</span>
        <span v-else class="step-cell step-cell--empty">{{ getEmptyPlaceholder() }}</span>
        <Button
          v-if="editTarget"
          icon="mdi mdi-calendar-edit-outline"
          size="small"
          text
          rounded
          v-tooltip.top.focus="t('production.lots.plannedDate.edit')"
          :aria-label="t('production.lots.plannedDate.edit')"
          @click="onEditPlannedDate"
          style="margin-bottom: -0.5rem; margin-top: -0.5rem"
        />
      </span>
      <span
        v-if="plannedInfo.plannedByLabel"
        class="delivery-note"
        v-tooltip.top="attributionTooltip"
        >{{ plannedInfo.plannedByLabel }}</span
      >
    </div>
    <span v-else class="step-cell step-cell--empty">{{ getEmptyPlaceholder() }}</span>
  </template>

  <template v-else-if="kind === 'plannedDate'">
    <div v-if="plannedInfo" class="delivery-cell">
      <span class="delivery-date-row">
        <span
          v-if="plannedInfo.date"
          :class="{
            'delivery-date--overdue': plannedInfo.isOverdue,
            'delivery-date--conflicts': plannedInfo.conflicts.length > 0,
          }"
          v-tooltip.top="dateTooltip"
        >
          {{ toDateParam(plannedInfo.date) }}
        </span>
        <span v-else class="step-cell step-cell--empty">{{ getEmptyPlaceholder() }}</span>
        <Button
          v-if="editTarget"
          icon="mdi mdi-calendar-edit-outline"
          size="small"
          text
          rounded
          v-tooltip.top.focus="t('production.lots.plannedDate.edit')"
          :aria-label="t('production.lots.plannedDate.edit')"
          @click="onEditPlannedDate"
          style="margin-bottom: -0.5rem; margin-top: -0.5rem"
        />
      </span>
      <span
        v-if="plannedInfo.plannedByLabel"
        class="delivery-note"
        v-tooltip.top="attributionTooltip"
        >{{ plannedInfo.plannedByLabel }}</span
      >
      <span v-if="deliveryNoteLine(plannedInfo)" class="delivery-note">{{
        deliveryNoteLine(plannedInfo)
      }}</span>
      <span
        v-if="pickupLine(plannedInfo, toDateParam, t)"
        class="delivery-note delivery-note--pickup"
        >{{ pickupLine(plannedInfo, toDateParam, t) }}</span
      >
    </div>
    <span v-else class="step-cell step-cell--empty">{{ getEmptyPlaceholder() }}</span>
  </template>

  <template v-else-if="kind === 'deliveryDate'">
    <div v-if="confirmedInfo" class="delivery-cell">
      <!-- Only ever a confirmed date, so nothing here needs the muted
           "projected" styling the Planned Date column uses. -->
      <span v-if="confirmedInfo.date">{{ toDateParam(confirmedInfo.date) }}</span>
      <span v-else class="step-cell step-cell--empty">{{ getEmptyPlaceholder() }}</span>
      <span v-if="confirmedInfo.note" class="delivery-note">{{ confirmedInfo.note }}</span>
    </div>
    <span v-else class="step-cell step-cell--empty">{{ getEmptyPlaceholder() }}</span>
  </template>

  <template v-else-if="kind === 'note'">
    <span v-if="group" class="step-cell item-code" v-tooltip.top="noteTooltip">{{
      noteLine ?? getEmptyPlaceholder()
    }}</span>
    <span v-else class="step-cell step-cell--empty">{{ getEmptyPlaceholder() }}</span>
  </template>
</template>

<style scoped lang="scss">
.item-code {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.step-method-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  width: fit-content;
}

.step-method-name {
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
}

.step-count-badge {
  font-size: var(--font-size-xs);
  min-width: 1.25rem;
  justify-content: center;
}

.delivery-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.delivery-note {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.delivery-note--pickup {
  font-style: italic;
}

.delivery-date--conflicts {
  color: var(--p-orange-500);
}

/* A planned date whose target has passed unconfirmed. Declared after
   --conflicts so it wins on the shared `color` property: a stale plan is
   the more urgent of the two signals. */
.delivery-date--overdue {
  color: var(--p-red-500);
  font-weight: bold;
}

.step-cell--estimated {
  color: var(--p-text-muted-color);
  font-style: italic;
}

.step-cell-stack {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.step-cell-total {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.delivery-date-row {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}
</style>
