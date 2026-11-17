<script setup lang="ts">
import { extractApiError } from '@/core/utils/errors'
import { computed, reactive, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useProductionLotsStore } from '../../stores/productionLotsStore'
import { MadeItemSelect } from '@/features/made-items'
import ProjectSelect from '@/shared/components/project/ProjectSelect.vue'
import { LOT_PRIORITIES } from '../../utils/lotStatus'
import { dateToParam, toLocalDayStart } from '@/core/utils/dates'

import type { LotCreateRequest } from '../../types/productionLotsRequest'
import type { LotPriority, LotResponse } from '../../types/productionLotsResponse'
import type { MadeItemResponse } from '@/features/made-items'
import type { MadeItemDemandResponse } from '@/features/made-items'
import type { ProjectRef } from '@/core/types/projectRef'

const props = defineProps<{
  presetItem?: MadeItemResponse | null
  presetDemand?: MadeItemDemandResponse | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  created: [lot: LotResponse]
}>()

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()

const lotsStore = useProductionLotsStore()

interface FormState {
  item: MadeItemResponse | null
  project: ProjectRef | null
  quantity: number | null
  priority: LotPriority | null
  note: string
  requiredDeliveryDate: Date | null
}

function presetProject(): ProjectRef | null {
  if (!props.presetDemand) return null
  return {
    id: props.presetDemand.project_id,
    project_number: props.presetDemand.project_number,
    customer: { name: props.presetDemand.project_customer },
    description: null,
  }
}

function createEmptyForm(): FormState {
  return {
    item: props.presetItem ?? null,
    project: presetProject(),
    quantity: props.presetDemand ? props.presetDemand.quantity : null,
    priority: props.presetDemand?.high_priority ? 'high' : null,
    note: '',
    requiredDeliveryDate: props.presetDemand?.desired_delivery_date
      ? toLocalDayStart(props.presetDemand.desired_delivery_date)
      : null,
  }
}

const form = reactive(createEmptyForm())
const submitting = ref(false)
const errorMessage = ref<string | null>(null)

// Without a material source the lot's first in-house step waits until a
// source is selected and approved, which is intended but easy to miss.
const itemHasNoSource = computed(
  () => !!form.item && form.item.bought_item_id === null && form.item.source_item_id === null,
)

const priorityOptions = LOT_PRIORITIES.map((p) => ({ value: p, label: p }))

watch(visible, (isVisible) => {
  if (!isVisible) return
  Object.assign(form, createEmptyForm())
  errorMessage.value = null
})

// A lot builds the made item of the demand it covers, so a preset demand
// fixes the item: the backend refuses to link a demand of another item.
function madeItemId(): number | null {
  return props.presetDemand ? props.presetDemand.made_item_id : (form.item?.id ?? null)
}

function isFormValid(): boolean {
  return (
    madeItemId() !== null && form.project !== null && form.quantity !== null && form.quantity > 0
  )
}

async function onSubmit(): Promise<void> {
  if (!isFormValid()) {
    errorMessage.value = t('production.lots.create.errors.required')
    return
  }

  submitting.value = true
  errorMessage.value = null

  const payload: LotCreateRequest = {
    made_item_id: madeItemId()!,
    project_id: form.project!.id,
    quantity: form.quantity!,
    note: form.note.trim() || null,
    priority: form.priority,
    required_delivery_date: dateToParam(form.requiredDeliveryDate),
    demand_allocations: props.presetDemand
      ? [{ demand_item_id: props.presetDemand.id, quantity: form.quantity! }]
      : [],
  }

  try {
    const created = await lotsStore.create(payload)
    visible.value = false
    emit('created', created)
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t('production.lots.create.errors.unknown')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('production.lots.create.title')"
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <form class="create-form" @submit.prevent="onSubmit">
      <div class="field">
        <label :id="`${uid}-item-label`" :for="`${uid}-item`">{{ t('production.lots.create.fields.item') }} *</label>
        <MadeItemSelect
          v-model="form.item"
          :input-id="`${uid}-item`"
          :aria-labelledby="`${uid}-item-label`"
          :disabled="!!presetItem || !!presetDemand"
          fluid
        />
      </div>

      <div class="field">
        <label :id="`${uid}-project-label`" :for="`${uid}-project`">{{ t('production.lots.create.fields.project') }} *</label>
        <ProjectSelect v-model="form.project" :input-id="`${uid}-project`" :aria-labelledby="`${uid}-project-label`" :disabled="!!presetDemand" fluid />
      </div>

      <div class="form-grid">
        <div class="field">
          <label :for="`${uid}-quantity`">{{ t('production.lots.create.fields.quantity') }} *</label>
          <InputNumber v-model="form.quantity" :input-id="`${uid}-quantity`" :min="1" :max-fraction-digits="0" fluid />
        </div>

        <div class="field">
          <label :id="`${uid}-priority-label`" :for="`${uid}-priority`">
            {{ t('production.lots.create.fields.priority') }}
          </label>
          <Select
            v-model="form.priority"
            :input-id="`${uid}-priority`"
            :aria-labelledby="`${uid}-priority-label`"
            :options="priorityOptions"
            option-label="label"
            option-value="value"
            :placeholder="t('production.lots.create.fields.priorityPlaceholder')"
            show-clear
            fluid
          />
        </div>
      </div>

      <div class="field">
        <label :for="`${uid}-required-delivery-date`">
          {{ t('production.lots.create.fields.requiredDeliveryDate') }}
        </label>
        <DatePicker
          v-model="form.requiredDeliveryDate"
          :input-id="`${uid}-required-delivery-date`"
          show-button-bar
          show-clear
          fluid
        />
        <small class="field-hint">{{
          t('production.lots.create.fields.requiredDeliveryDateHint')
        }}</small>
      </div>

      <div class="field">
        <label :for="`${uid}-note`">{{ t('production.lots.create.fields.note') }}</label>
        <Textarea v-model="form.note" :id="`${uid}-note`" rows="3" auto-resize fluid />
      </div>

      <Message v-if="itemHasNoSource" severity="info" :closable="false">
        {{ t('production.lots.create.noSourceHint') }}
      </Message>

      <Message v-if="presetDemand" severity="info" :closable="false">
        {{ t('production.lots.create.fromDemand', { id: presetDemand.id }) }}
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
        @click="visible = false"
      />
      <Button :label="t('common.save')" :loading="submitting" @click="onSubmit" />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.create-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
</style>
