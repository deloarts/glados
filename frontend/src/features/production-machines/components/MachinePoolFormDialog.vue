<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { API_MAX_PAGE_SIZE } from '@/core/constants/table'

import { getProductionMachines } from '../api/getProductionMachines'
import { useMachinePoolsStore } from '../stores/machinePoolsStore'
import { useEntityFormDialog } from '@/shared/composables/useEntityFormDialog'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'

import type { ProductionMachineResponse } from '../types/productionMachinesResponse'
import type { MachinePoolResponse } from '../types/machinePoolsResponse'

interface Props {
  pool?: MachinePoolResponse | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  saved: [pool: MachinePoolResponse]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const store = useMachinePoolsStore()

const machines = ref<ProductionMachineResponse[]>([])
const machinesLoaded = ref(false)
const loadingMachines = ref(false)

// Referencing an already-archived machine is allowed. The options include
// archived rows, sorted after live ones, each tagged (see
// useArchivableOptions.ts).
const { sortedOptions: machineOptions, isArchived } = useArchivableOptions(machines)

interface FormState {
  name: string
  machine_ids: number[]
  note: string
}

function createEmptyForm(): FormState {
  return {
    name: '',
    machine_ids: [],
    note: '',
  }
}

function formFromPool(pool: MachinePoolResponse): FormState {
  return {
    name: pool.name,
    machine_ids: [...pool.machine_ids],
    note: pool.note ?? '',
  }
}

onMounted(async () => {
  if (machinesLoaded.value) return
  loadingMachines.value = true
  try {
    const result = await getProductionMachines({ limit: API_MAX_PAGE_SIZE, include_archived: true })
    machines.value = result.items
    machinesLoaded.value = true
  } finally {
    loadingMachines.value = false
  }
})

const { form, submitting, errorMessage, isEditMode, onSubmit, onCancel } = useEntityFormDialog<
  MachinePoolResponse,
  FormState
>({
  visible,
  entity: () => props.pool,
  emptyForm: createEmptyForm,
  formFromEntity: formFromPool,
  validate: (form) =>
    form.name.trim() ? null : t('productionMachinePools.create.errors.required'),
  save: (form, isEditMode, pool) => {
    const payload = {
      name: form.name.trim(),
      machine_ids: form.machine_ids,
      note: form.note.trim() || null,
    }
    return isEditMode && pool ? store.update(pool.id, payload) : store.create(payload)
  },
  onSaved: (saved) => emit('saved', saved),
  unknownErrorMessage: t('productionMachinePools.create.errors.unknown'),
})

const selectedMachines = computed<ProductionMachineResponse[]>(() =>
  machineOptions.value.filter((m) => form.machine_ids.includes(m.id)),
)
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="
      isEditMode
        ? t('productionMachinePools.create.editTitle')
        : t('productionMachinePools.create.createTitle')
    "
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <form class="pool-form" @submit.prevent="onSubmit">
      <div class="form-fields">
        <div class="field field-wide">
          <label for="mp-name">{{ t('productionMachinePools.create.fields.name') }} *</label>
          <InputText id="mp-name" v-model="form.name" fluid autocomplete="off" />
        </div>

        <div class="field field-wide">
          <label id="mp-machines-label" for="mp-machines">{{ t('productionMachinePools.create.fields.machines') }}</label>
          <MultiSelect
            id="mp-machines"
            aria-labelledby="mp-machines-label"
            v-model="form.machine_ids"
            :options="machineOptions"
            option-label="internal_name"
            option-value="id"
            :loading="loadingMachines"
            :placeholder="t('productionMachinePools.create.fields.machinesPlaceholder')"
            display="chip"
            filter
            fluid
          >
            <template #option="{ option }">
              <span>{{ option.internal_name }}</span>
              <ArchivedOptionTag v-if="option.archived" />
            </template>
          </MultiSelect>
          <ArchivedSelectionWarning v-if="isArchived(selectedMachines)" />
        </div>

        <div class="field field-wide">
          <label for="mp-note">{{ t('productionMachinePools.create.fields.note') }}</label>
          <Textarea id="mp-note" v-model="form.note" rows="3" fluid auto-resize />
        </div>
      </div>

      <Message v-if="errorMessage" severity="error" class="mt-2">{{ errorMessage }}</Message>

      <div class="form-footer">
        <Button
          type="button"
          :label="t('common.cancel')"
          severity="secondary"
          @click="onCancel"
          :disabled="submitting"
        />
        <Button type="submit" :label="t('common.save')" :loading="submitting" />
      </div>
    </form>
  </Dialog>
</template>

<style scoped lang="scss">
.pool-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.form-fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3) var(--space-4);
}

.field {
  label {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}

.field-wide {
  grid-column: 1 / -1;
}
</style>
