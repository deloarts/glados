<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { dateToParam as toDateParam, toLocalDayStart } from '@/core/utils/dates'
import { extractApiError } from '@/core/utils/errors'

import { getLot } from '../../api/getLot'
import { updateLot } from '../../api/updateLot'
import { updateProductionOrder } from '../../api/updateProductionOrder'
import { useProductionLotsStore } from '../../stores/productionLotsStore'
import { useProductionLotsEditStore } from '../stores/productionLotsEditStore'
import { LOT_PRIORITIES } from '../../utils/lotStatus'

import type { LotPriority, LotResponse, LotSummaryResponse } from '../../types/productionLotsResponse'
import { sortedBySequence } from '../../utils/sequence'

const { t } = useI18n()

const lotsStore = useProductionLotsStore()
const editStore = useProductionLotsEditStore()

interface LotEditFormState {
  priority: LotPriority | null
  required_delivery_date: Date | null
}

type EditFieldKey = keyof LotEditFormState

function createEmptyForm(): LotEditFormState {
  return {
    priority: null,
    required_delivery_date: null,
  }
}

const form = reactive(createEmptyForm())

// Fields with differing values across the selection that the user has not
// edited yet.
const mixedFields = reactive(new Set<EditFieldKey>())

// Only edited fields overwrite the selected lots.
const dirtyFields = reactive(new Set<EditFieldKey>())

// The step schedule is not prefilled, since each lot's step belongs to a
// different order. Blank leaves it alone.
const stepPosition = ref<number | null>(null)
const plannedStart = ref<Date | null>(null)
const plannedEnd = ref<Date | null>(null)

const submitting = ref(false)
const errorMessage = ref<string | null>(null)
const resultMessage = ref<string | null>(null)

const selectedItems = computed(() => editStore.selectedItems)

const maxStepCount = computed(() =>
  selectedItems.value.reduce((max, lot) => Math.max(max, lot.steps?.length ?? 0), 0),
)

const stepPositionOptions = computed(() =>
  Array.from({ length: maxStepCount.value }, (_, i) => ({
    label: t('production.lots.columns.step', { n: i + 1 }),
    value: i + 1,
  })),
)

function applyFieldFromSelection<K extends EditFieldKey>(
  field: K,
  items: LotSummaryResponse[],
  getter: (item: LotSummaryResponse) => LotEditFormState[K],
  emptyValue: LotEditFormState[K],
): void {
  const first = getter(items[0]!)
  const allSame = items.every((item) => {
    const value = getter(item)
    if (value instanceof Date && first instanceof Date) {
      return value.getTime() === first.getTime()
    }
    return value === first
  })

  if (allSame) {
    form[field] = first
  } else {
    form[field] = emptyValue
    mixedFields.add(field)
  }
}

function resetFormFromSelection(items: LotSummaryResponse[]): void {
  dirtyFields.clear()
  mixedFields.clear()
  errorMessage.value = null
  resultMessage.value = null

  Object.assign(form, createEmptyForm())
  plannedStart.value = null
  plannedEnd.value = null

  if (items.length === 0) return

  applyFieldFromSelection('priority', items, (item) => item.priority, null)
  applyFieldFromSelection(
    'required_delivery_date',
    items,
    (item) =>
      item.required_delivery_date ? toLocalDayStart(item.required_delivery_date) : null,
    null,
  )
}

watch(selectedItems, (items) => resetFormFromSelection(items), { immediate: true })

// An invalid step position would skip every lot on submit.
watch(maxStepCount, (max) => {
  if (stepPosition.value !== null && stepPosition.value > max) stepPosition.value = null
})

function markDirty(field: EditFieldKey): void {
  dirtyFields.add(field)
  mixedFields.delete(field)
}

function placeholderFor(field: EditFieldKey, fallback?: string): string | undefined {
  if (mixedFields.has(field) && !dirtyFields.has(field)) {
    return t('production.lots.edit.multipleValues')
  }
  return fallback
}

const hasLotFieldChanges = computed(() => dirtyFields.size > 0)
const hasStepScheduleChanges = computed(
  () => stepPosition.value !== null && plannedStart.value !== null,
)
const canSubmit = computed(
  () =>
    selectedItems.value.length > 0 && (hasLotFieldChanges.value || hasStepScheduleChanges.value),
)

// Only an internal position with exactly one queued or paused order is
// eligible for a direct schedule edit. The order comes with the edit version
// it was read at, which the edit sends.
function eligibleOrder(
  detail: LotResponse,
  position: number,
): { id: number; editVersion: number } | null {
  const step = sortedBySequence(detail.steps)[position - 1]
  if (!step) return null

  const positionEntry = (detail.positions ?? []).find((p) => p.id === step.position_id)
  if (!positionEntry || positionEntry.kind !== 'internal') return null

  const active = (positionEntry.production_orders ?? []).filter((po) => po.status !== 'canceled')
  if (active.length !== 1) return null

  const order = active[0]!
  if (order.status !== 'queued' && order.status !== 'paused') return null
  return { id: order.id, editVersion: order.edit_version }
}

async function applyStepSchedule(items: LotSummaryResponse[]): Promise<number> {
  const position = stepPosition.value
  if (position === null || plannedStart.value === null) return 0

  const details = await Promise.all(items.map((lot) => getLot(lot.id)))
  const targets = details
    .map((detail) => eligibleOrder(detail, position))
    .filter((order) => order !== null)

  await Promise.all(
    targets.map((order) =>
      updateProductionOrder(order.id, {
        expected_edit_version: order.editVersion,
        planned_start: toDateParam(plannedStart.value),
        // planned_start needs planned_end; without one the backend recomputes the
        // end from the order's duration.
        ...(plannedEnd.value !== null
          ? { planned_end: toDateParam(plannedEnd.value) }
          : { recompute_planned_end: true }),
      }),
    ),
  )

  return targets.length
}

async function onSubmit(): Promise<void> {
  const items = selectedItems.value
  if (items.length === 0 || !canSubmit.value) return

  submitting.value = true
  errorMessage.value = null
  resultMessage.value = null

  try {
    if (hasLotFieldChanges.value) {
      await Promise.all(
        items.map((lot) =>
          updateLot(lot.id, {
            expected_edit_version: lot.edit_version,
            ...(dirtyFields.has('priority') && form.priority ? { priority: form.priority } : {}),
            ...(dirtyFields.has('required_delivery_date')
              ? { required_delivery_date: toDateParam(form.required_delivery_date) }
              : {}),
          }),
        ),
      )
    }

    let scheduled: number | null = null
    if (hasStepScheduleChanges.value) {
      scheduled = await applyStepSchedule(items)
    }

    if (scheduled !== null) {
      resultMessage.value = t('production.lots.edit.stepScheduleSummary', {
        updated: scheduled,
        total: items.length,
        skipped: items.length - scheduled,
      })
    }

    lotsStore.triggerRefresh()
    dirtyFields.clear()
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t('production.lots.edit.errors.unknown')
  } finally {
    submitting.value = false
  }
}

function onCancel(): void {
  resetFormFromSelection(selectedItems.value)
  stepPosition.value = null
}

function onClear(): void {
  editStore.setSelectedItems([])
}
</script>

<template>
  <Panel class="edit-panel fill-panel fit-fields">
    <template #header>
      <div class="panel-header-row">
        <span class="panel-title">{{ t('production.lots.edit.title') }}</span>
        <Tag
          v-if="selectedItems.length > 0"
          :value="t('production.lots.edit.selectionSummary', { count: selectedItems.length })"
          severity="secondary"
        />
      </div>
    </template>

    <Message v-if="selectedItems.length === 0" severity="info" :closable="false">
      {{ t('production.lots.edit.noSelection') }}
    </Message>

    <form v-else class="edit-form" @submit.prevent="onSubmit">
      <div class="form-actions">
        <Button
          type="submit"
          :label="t('common.save')"
          :loading="submitting"
          :disabled="!canSubmit"
        />
        <Button
          type="button"
          :label="t('common.cancel')"
          severity="secondary"
          outlined
          :disabled="submitting"
          @click="onCancel"
        />
        <Button
          type="button"
          :label="t('common.clearSelection')"
          severity="secondary"
          outlined
          :disabled="submitting"
          @click="onClear"
        />
      </div>

      <Message v-if="errorMessage" severity="error" :closable="false">
        {{ errorMessage }}
      </Message>
      <Message v-if="resultMessage" severity="info" :closable="false">
        {{ resultMessage }}
      </Message>

      <div class="form-fields">
        <div class="field">
          <label id="lep-priority-label" for="lep-priority">{{ t('production.lots.edit.fields.priority') }}</label>
          <Select
            id="lep-priority"
            aria-labelledby="lep-priority-label"
            v-model="form.priority"
            :options="LOT_PRIORITIES"
            :option-label="(p) => t(`production.lots.priority.${p}`)"
            :placeholder="placeholderFor('priority')"
            fluid
            @update:model-value="markDirty('priority')"
          />
        </div>

        <div class="field">
          <label for="lep-required-delivery">{{
            t('production.lots.edit.fields.requiredDeliveryDate')
          }}</label>
          <DatePicker
            id="lep-required-delivery"
            v-model="form.required_delivery_date"
            show-icon
            show-button-bar
            :placeholder="placeholderFor('required_delivery_date')"
            fluid
            @update:model-value="markDirty('required_delivery_date')"
          />
        </div>

        <Divider />

        <div class="field">
          <label id="lep-step-position-label" for="lep-step-position">{{ t('production.lots.edit.fields.stepPosition') }}</label>
          <Select
            id="lep-step-position"
            aria-labelledby="lep-step-position-label"
            v-model="stepPosition"
            :options="stepPositionOptions"
            option-label="label"
            option-value="value"
            :placeholder="t('production.lots.edit.fields.stepPositionPlaceholder')"
            show-clear
            fluid
          />
          <small class="field-hint">{{ t('production.lots.edit.fields.stepPositionHint') }}</small>
        </div>

        <div class="field">
          <label for="lep-planned-start">{{ t('production.lots.edit.fields.plannedStart') }}</label>
          <DatePicker
            id="lep-planned-start"
            v-model="plannedStart"
            show-icon
            show-button-bar
            :disabled="stepPosition === null"
            fluid
          />
        </div>

        <div class="field">
          <label for="lep-planned-end">{{ t('production.lots.edit.fields.plannedEnd') }}</label>
          <DatePicker
            id="lep-planned-end"
            v-model="plannedEnd"
            show-icon
            show-button-bar
            :disabled="stepPosition === null || plannedStart === null"
            fluid
          />
          <small class="field-hint">{{ t('production.lots.edit.fields.plannedEndHint') }}</small>
        </div>
      </div>
    </form>
  </Panel>
</template>

<style scoped lang="scss">
.edit-panel {
  flex: 0 0 auto;
  min-width: 24rem;
}

.panel-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: var(--space-2);
}

.edit-form {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-width: 0;
}

.form-fields {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-width: 0;
  overflow-y: auto;
  overflow-x: hidden;
}

.field {
  flex-shrink: 0;
  min-width: 0;
  overflow: hidden;
}

.field label {
  color: var(--p-text-color);
}

.form-actions {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-start;
  gap: var(--space-2);
}
</style>
