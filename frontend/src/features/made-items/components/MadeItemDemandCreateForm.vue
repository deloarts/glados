<script setup lang="ts">
import { toLocalDayStart } from '@/core/utils/dates'
import { ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useMadeItemsDemandsStore } from '../stores/madeItemsDemandsStore'
import { useMadeItemsStore } from '../stores/madeItemsStore'
import { getMadeItems } from '../api/getMadeItems'
import MadeItemSelect from './MadeItemSelect.vue'
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

import type { MadeItemDemandResponse } from '../types/madeItemsDemandsResponse'
import type { MadeItemResponse } from '../types/madeItemsResponse'
import type { ProjectRef } from '@/core/types/projectRef'
import { BOUGHT_ITEM_UNIT_CODES, DEFAULT_UNIT } from '@/shared/utils/units'

const props = defineProps<{
  presetItem?: MadeItemResponse | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  created: [item: MadeItemDemandResponse]
}>()

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()

const demandsStore = useMadeItemsDemandsStore()
const madeItemsStore = useMadeItemsStore()

interface FormState extends DemandCommonCreateFields {
  item: MadeItemResponse | null
  project: ProjectRef | null
  is_alteration: boolean
  alteration_of_item: MadeItemResponse | null
}

function createEmptyForm(): FormState {
  return {
    item: props.presetItem ?? null,
    project: null,
    is_alteration: false,
    alteration_of_item: null,
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
  MadeItemDemandResponse,
  FormState
>({
  visible,
  entity: () => null,
  emptyForm: createEmptyForm,
  formFromEntity: createEmptyForm,
  validate: (f) =>
    f.item !== null &&
    f.project !== null &&
    isDemandCommonCreateFieldsValid(f) &&
    (!f.is_alteration || f.alteration_of_item !== null)
      ? null
      : t('madeItems.demands.create.errors.required'),
  save: (f) =>
    demandsStore.create({
      made_item_id: f.item!.id,
      project_id: f.project!.id,
      ...demandCommonFieldsToPayload(f),
      is_alteration: f.is_alteration,
      alteration_of_made_item_id: f.is_alteration ? (f.alteration_of_item?.id ?? null) : null,
    }),
  onSaved: (created) => emit('created', created),
  unknownErrorMessage: t('madeItems.demands.create.errors.unknown'),
})

watch(
  () => form.project,
  (project) => {
    if (userTouchedDate.value) return
    form.desired_delivery_date = project?.required_delivery_date_made
      ? toLocalDayStart(project.required_delivery_date_made)
      : null
  },
)

watch(
  () => form.is_alteration,
  (isAlteration) => {
    if (!isAlteration) {
      form.alteration_of_item = null
    }
  },
)

async function onUseReplacement(): Promise<void> {
  const successorId = form.item?.successor_item_id
  if (!successorId) return

  const cached = madeItemsStore.getById(successorId)
  if (cached) {
    form.item = cached
    return
  }

  replacementLoading.value = true
  try {
    const result = await getMadeItems({ id: successorId, limit: 1 })
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
    :header="t('madeItems.demands.create.title')"
    :style="{ width: 'var(--dialog-width-lg)' }"
  >
    <form class="create-form" @submit.prevent="onSubmit">
      <Message v-if="form.item?.status == 'replaced'" severity="warn" :closable="false">
        <div class="replace-warning">
          <span>{{ t('madeItems.demands.create.replaceWarning') }}</span>
          <Button
            :label="t('madeItems.demands.create.useReplacement')"
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
          <span>{{ t('madeItems.demands.create.inactiveWarning') }}</span>
        </div>
      </Message>
      <div class="form-grid">
        <div class="field field-wide">
          <label :id="`${uid}-item-label`" :for="`${uid}-item`">
            {{ t('madeItems.demands.create.fields.item') }} *
          </label>
          <MadeItemSelect v-model="form.item" :input-id="`${uid}-item`" :aria-labelledby="`${uid}-item-label`" fluid />
        </div>

        <div class="field field-wide">
          <label :id="`${uid}-project-label`" :for="`${uid}-project`">{{ t('madeItems.demands.create.fields.project') }} *</label>
          <ProjectSelect
            v-model="form.project"
            :input-id="`${uid}-project`"
            :aria-labelledby="`${uid}-project-label`"
            :placeholder="t('madeItems.demands.create.fields.projectPlaceholder')"
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
          i18n-prefix="madeItems.demands.create"
          id-prefix="made-demand"
          @date-touched="userTouchedDate = true"
        >
          <template #extra-fields>
            <div class="field checkbox-field field-wide">
              <Checkbox
                v-model="form.is_alteration"
                input-id="made-demand-is-alteration"
                :binary="true"
              />
              <label for="made-demand-is-alteration">{{
                t('madeItems.demands.create.fields.isAlteration')
              }}</label>
            </div>

            <div v-if="form.is_alteration" class="field field-wide">
              <label :id="`${uid}-alteration-of-item-label`" :for="`${uid}-alteration-of-item`">
                {{ t('madeItems.demands.create.fields.alterationOfItem') }} *
              </label>
              <MadeItemSelect
                v-model="form.alteration_of_item"
                :input-id="`${uid}-alteration-of-item`"
                :aria-labelledby="`${uid}-alteration-of-item-label`"
                :exclude-id="form.item?.id"
                fluid
              />
            </div>
          </template>
        </DemandCreateFieldsBlock>
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

.checkbox-field {
  flex-direction: row;
  align-items: center;
  gap: var(--space-2);
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
