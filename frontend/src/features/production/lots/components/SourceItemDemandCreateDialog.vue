<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useSourceItemDemandsStore } from '@/features/source-items'
import FormField from '@/shared/components/forms/FormField.vue'
import LotSelect from './LotSelect.vue'
import { isSourceApprovalPending, isSourceApprovalRejected } from '../utils/lotSourceEligibility'
import { useEntityFormDialog } from '@/shared/composables/useEntityFormDialog'
import { useDemandUnitOptions } from '@/shared/composables/useDemandUnitOptions'
import {
  createDemandCommonCreateFields,
  demandCommonFieldsToPayload,
  isDemandCommonCreateFieldsValid,
  type DemandCommonCreateFields,
} from '@/shared/utils/demandCommonFields'

import type { SourceItemDemandResponse } from '@/features/source-items'
import type { LotSummaryResponse } from '../../types/productionLotsResponse'
import { BOUGHT_ITEM_UNIT_CODES, DEFAULT_UNIT } from '@/shared/utils/units'

const props = withDefaults(
  defineProps<{
    // Without lotId the dialog renders its own lot select.
    lotId?: number | null
    lotQuantity?: number
  }>(),
  { lotId: null, lotQuantity: 0 },
)

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  created: [demand: SourceItemDemandResponse]
}>()

const { t } = useI18n()

const demandsStore = useSourceItemDemandsStore()

const selectedLot = ref<LotSummaryResponse | null>(null)
// Latched on open, since the bound lot id can go null during a refetch and
// would flip the dialog into picker mode.
const pickerMode = ref(false)

const effectiveLotId = computed(() => props.lotId ?? selectedLot.value?.id ?? null)

const unitOptions = useDemandUnitOptions(BOUGHT_ITEM_UNIT_CODES, (code) =>
  t(`boughtItems.units.${code}`),
)

watch(visible, (isVisible) => {
  if (!isVisible) return
  pickerMode.value = props.lotId == null
  selectedLot.value = null
})

// Picker mode only. A defensive guard behind LotSelect's own filter, so a
// pending or rejected approval explains itself instead of returning a 409.
const sourceApprovalBlocked = computed(
  () =>
    pickerMode.value &&
    selectedLot.value !== null &&
    (isSourceApprovalPending(selectedLot.value) || isSourceApprovalRejected(selectedLot.value)),
)

const { form, submitting, errorMessage, onSubmit, onCancel } = useEntityFormDialog<
  SourceItemDemandResponse,
  DemandCommonCreateFields
>({
  visible,
  entity: () => null,
  emptyForm: () =>
    createDemandCommonCreateFields(DEFAULT_UNIT, props.lotId == null ? null : props.lotQuantity),
  formFromEntity: () => createDemandCommonCreateFields(DEFAULT_UNIT),
  validate: (f) =>
    effectiveLotId.value !== null && !sourceApprovalBlocked.value && isDemandCommonCreateFieldsValid(f)
      ? null
      : t('sourceItems.demands.create.errors.required'),
  save: (f) =>
    demandsStore.create({
      lot_id: effectiveLotId.value!,
      ...demandCommonFieldsToPayload(f),
    }),
  onSaved: (created) => emit('created', created),
  unknownErrorMessage: t('sourceItems.demands.create.errors.unknown'),
})

// Picking a lot overwrites the quantity with the lot's.
watch(selectedLot, (lot) => {
  form.quantity = lot ? lot.quantity : null
})
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('sourceItems.demands.create.title')"
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <form class="create-form" @submit.prevent="onSubmit">
      <div class="form-grid">
        <div v-if="pickerMode" class="field field-wide">
          <FormField
            :label="t('sourceItems.demands.create.fields.lot')"
            required
            v-slot="{ inputId, labelId, ariaRequired }"
          >
            <LotSelect
              v-model="selectedLot"
              :input-id="inputId"
              :aria-labelledby="labelId"
              demandable-only
              fluid
              :pt="{ label: { 'aria-required': ariaRequired } }"
            />
          </FormField>
        </div>

        <div class="field">
          <FormField
            :label="t('sourceItems.demands.create.fields.quantity')"
            required
            v-slot="{ inputId, ariaRequired }"
          >
            <InputNumber
              v-model="form.quantity"
              :input-id="inputId"
              :min="0.001"
              :max-fraction-digits="3"
              fluid
              :pt="{ pcInputText: { root: { 'aria-required': ariaRequired } } }"
            />
          </FormField>
        </div>

        <div class="field">
          <FormField
            :label="t('sourceItems.demands.create.fields.unit')"
            required
            v-slot="{ inputId, labelId, ariaRequired }"
          >
            <Select
              v-model="form.unit"
              :input-id="inputId"
              :aria-labelledby="labelId"
              :options="unitOptions"
              option-label="label"
              option-value="value"
              fluid
              :pt="{ label: { 'aria-required': ariaRequired } }"
            />
          </FormField>
        </div>

        <div class="field">
          <FormField
            :label="t('sourceItems.demands.create.fields.itemsPerUnit')"
            v-slot="{ inputId }"
          >
            <InputNumber
              v-model="form.items_per_unit"
              :input-id="inputId"
              :min="0.001"
              :max-fraction-digits="3"
              fluid
            />
          </FormField>
        </div>

        <div class="field">
          <FormField
            :label="t('sourceItems.demands.create.fields.desiredDeliveryDate')"
            v-slot="{ inputId }"
          >
            <DatePicker
              v-model="form.desired_delivery_date"
              :input-id="inputId"
              show-button-bar
              show-clear
              fluid
            />
          </FormField>
        </div>

        <div class="field checkbox-field">
          <Checkbox v-model="form.high_priority" input-id="bid-high-priority" :binary="true" />
          <label for="bid-high-priority">{{
            t('sourceItems.demands.create.fields.highPriority')
          }}</label>
        </div>

        <div class="field checkbox-field">
          <Checkbox v-model="form.notify_on_delivery" input-id="bid-notify" :binary="true" />
          <label for="bid-notify">{{
            t('sourceItems.demands.create.fields.notifyOnDelivery')
          }}</label>
        </div>

        <div class="field field-wide">
          <FormField :label="t('sourceItems.demands.create.fields.note')" v-slot="{ id }">
            <Textarea :id="id" v-model="form.note" rows="3" auto-resize fluid />
          </FormField>
        </div>
      </div>

      <Message v-if="sourceApprovalBlocked" severity="warn" :closable="false">
        {{ t('production.lots.detail.record.sourceApproval.noDemandUntilApproved') }}
      </Message>

      <Message v-if="errorMessage" severity="error" :closable="false">
        {{ errorMessage }}
      </Message>
    </form>

    <template #footer>
      <Button
        :label="t('common.cancel')"
        severity="secondary"
        outlined
        :disabled="submitting"
        @click="onCancel"
      />
      <Button
        :label="t('common.save')"
        :loading="submitting"
        :disabled="sourceApprovalBlocked"
        @click="onSubmit"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.create-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding-top: var(--space-1);
}

.field-wide {
  grid-column: 1 / -1;
}

.checkbox-field {
  flex-direction: row;
  align-items: center;
  gap: var(--space-2);
}
</style>
