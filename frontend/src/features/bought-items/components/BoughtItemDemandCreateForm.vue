<script setup lang="ts">
import { toLocalDayStart } from '@/core/utils/dates'
import { ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useBoughtItemsDemandsStore } from '../stores/boughtItemsDemandsStore'
import { useBoughtItemsStore } from '../stores/boughtItemsStore'
import { getBoughtItems } from '../api/getBoughtItems'
import BoughtItemSelect from './BoughtItemSelect.vue'
import ProjectSelect from '@/shared/components/project/ProjectSelect.vue'
import { useEntityFormDialog } from '@/shared/composables/useEntityFormDialog'
import { useDemandUnitOptions } from '@/shared/composables/useDemandUnitOptions'
import {
  createDemandCommonCreateFields,
  demandCommonFieldsToPayload,
  isDemandCommonCreateFieldsValid,
  type DemandCommonCreateFields,
} from '@/shared/utils/demandCommonFields'
import DemandCreateFieldsBlock from '@/shared/components/demands/DemandCreateFieldsBlock.vue'

import type { BoughtItemDemandResponse } from '../types/boughtItemsDemandsResponse'
import type { BoughtItemResponse } from '../types/boughtItemsResponse'
import type { ProjectRef } from '@/core/types/projectRef'
import { BOUGHT_ITEM_UNIT_CODES, DEFAULT_UNIT } from '@/shared/utils/units'

const props = defineProps<{
  presetItem?: BoughtItemResponse | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  created: [item: BoughtItemDemandResponse]
}>()

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()

const demandsStore = useBoughtItemsDemandsStore()
const boughtItemsStore = useBoughtItemsStore()

interface FormState extends DemandCommonCreateFields {
  item: BoughtItemResponse | null
  project: ProjectRef | null
}

function createEmptyForm(): FormState {
  return {
    item: props.presetItem ?? null,
    project: null,
    ...createDemandCommonCreateFields(DEFAULT_UNIT),
  }
}

const replacementLoading = ref(false)
// Tracks whether the user has manually edited/cleared the delivery date, so
// switching projects only overwrites a still-derived value, never one the
// user chose on purpose.
const userTouchedDate = ref(false)

const unitOptions = useDemandUnitOptions(BOUGHT_ITEM_UNIT_CODES, (code) =>
  t(`boughtItems.units.${code}`),
)

watch(visible, (isVisible) => {
  if (isVisible) userTouchedDate.value = false
})

const { form, submitting, errorMessage, onSubmit, onCancel } = useEntityFormDialog<
  BoughtItemDemandResponse,
  FormState
>({
  visible,
  entity: () => null,
  emptyForm: createEmptyForm,
  formFromEntity: createEmptyForm,
  validate: (f) =>
    f.item !== null && f.project !== null && isDemandCommonCreateFieldsValid(f)
      ? null
      : t('boughtItems.demands.create.errors.required'),
  save: (f) =>
    demandsStore.create({
      item_id: f.item!.id,
      project_id: f.project!.id,
      ...demandCommonFieldsToPayload(f),
    }),
  onSaved: (created) => emit('created', created),
  unknownErrorMessage: t('boughtItems.demands.create.errors.unknown'),
})

watch(
  () => form.project,
  (project) => {
    if (userTouchedDate.value) return
    form.desired_delivery_date = project?.required_delivery_date_bought
      ? toLocalDayStart(project.required_delivery_date_bought)
      : null
  },
)

async function onUseReplacement(): Promise<void> {
  const successorId = form.item?.successor_item_id
  if (!successorId) return

  const cached = boughtItemsStore.getById(successorId)
  if (cached) {
    form.item = cached
    return
  }

  replacementLoading.value = true
  try {
    const result = await getBoughtItems({ id: successorId, limit: 1 })
    if (result.items[0]) {
      form.item = result.items[0]
    }
  } finally {
    replacementLoading.value = false
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('boughtItems.demands.create.title')"
    :style="{ width: 'var(--dialog-width-lg)' }"
  >
    <form class="create-form" @submit.prevent="onSubmit">
      <Message v-if="form.item?.status == 'replaced'" severity="warn" :closable="false">
        <div class="replace-warning">
          <span>{{ t('boughtItems.demands.create.replaceWarning') }}</span>
          <Button
            :label="t('boughtItems.demands.create.useReplacement')"
            severity="warn"
            size="small"
            icon="mdi mdi-swap-horizontal"
            :loading="replacementLoading"
            style="width: 12rem"
            @click="onUseReplacement"
          />
        </div>
      </Message>
      <Message v-if="form.item?.status == 'inactive'" severity="error" :closable="false">
        <div class="inactive-warning">
          <span>{{ t('boughtItems.demands.create.inactiveWarning') }}</span>
        </div>
      </Message>
      <div class="form-grid">
        <div class="field field-wide">
          <label :id="`${uid}-item-label`" :for="`${uid}-item`">
            {{ t('boughtItems.demands.create.fields.item') }} *
          </label>
          <BoughtItemSelect
            v-model="form.item"
            :input-id="`${uid}-item`"
            :aria-labelledby="`${uid}-item-label`"
            :placeholder="t('boughtItems.demands.create.fields.itemPlaceholder')"
            fluid
          />
        </div>

        <div class="field field-wide">
          <label :id="`${uid}-project-label`" :for="`${uid}-project`">{{ t('boughtItems.demands.create.fields.project') }} *</label>
          <ProjectSelect
            v-model="form.project"
            :input-id="`${uid}-project`"
            :aria-labelledby="`${uid}-project-label`"
            :placeholder="t('boughtItems.demands.create.fields.projectPlaceholder')"
            fluid
          />
        </div>

        <DemandCreateFieldsBlock
          v-model:quantity="form.quantity"
          v-model:unit="form.unit"
          v-model:items-per-unit="form.items_per_unit"
          v-model:high-priority="form.high_priority"
          v-model:notify-on-delivery="form.notify_on_delivery"
          v-model:desired-delivery-date="form.desired_delivery_date"
          v-model:note="form.note"
          :unit-options="unitOptions"
          i18n-prefix="boughtItems.demands.create"
          id-prefix="demand"
          @date-touched="userTouchedDate = true"
        />
      </div>

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
      <Button :label="t('common.save')" :loading="submitting" @click="onSubmit" />
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

.replace-warning {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  flex: 1 1 auto;
  width: 100%;
}
</style>
