<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useHostStore } from '@/core/host/stores/hostStore'
import { useProductsStore } from '@/features/products'
import { getProductDevices } from '@/features/product-devices'
import type { ProductDevice } from '@/features/product-devices'
import ProjectSelect from '@/shared/components/project/ProjectSelect.vue'
import type { ProjectRef } from '@/core/types/projectRef'
import type { CalculationMeta } from '../composables/useSavedCalculation'
import type { CalculationOwner } from '../types/calculation'

type OwnerKind = CalculationOwner['kind']

const props = defineProps<{
  /** 'create' saves a new calculation, 'edit' changes the open one. */
  mode: 'create' | 'edit'
  initial: CalculationMeta
  busy?: boolean
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{ save: [meta: CalculationMeta] }>()

const { t } = useI18n()
const productsStore = useProductsStore()

const TITLE_MAX = 200
const NOTE_MAX = 2000

const form = reactive({
  kind: 'personal' as OwnerKind,
  project: null as ProjectRef | null,
  productId: null as number | null,
  title: '',
  note: '',
  deviceId: null as number | null,
})
const submitted = ref(false)
// True while reset() sets the calculation's own owner, so its device stays.
let keepDevice = false

function reset(): void {
  const { owner, title, note } = props.initial
  form.kind = owner.kind
  form.project =
    owner.kind === 'project'
      ? { id: owner.id, project_number: owner.label, customer: null, description: null }
      : null
  form.productId = owner.kind === 'product' ? owner.id : null
  form.title = title
  form.note = note ?? ''
  form.deviceId = props.initial.deviceId
  submitted.value = false
  keepDevice = true
  void nextTick(() => {
    keepDevice = false
  })
}

watch(visible, (open) => {
  if (open) reset()
})

onMounted(() => {
  if (!productsStore.items.length) void productsStore.refresh()
})

const ownerOptions = computed(() =>
  (['personal', 'project', 'product'] as const).map((value) => ({
    value,
    label: t(`tools.calculations.owner.${value}`),
  })),
)

// New calculations cannot be attached to an archived product, so archived
// ones are left out, except the one an existing calculation already has.
const productOptions = computed(() =>
  productsStore.items
    .filter((p) => !p.archived || p.id === form.productId)
    .map((p) => ({
      value: p.id,
      label: p.description ? `${p.product_number} - ${p.description}` : p.product_number,
    })),
)

const owner = computed<CalculationOwner | null>(() => {
  if (form.kind === 'personal') return { kind: 'personal' }
  if (form.kind === 'project') {
    return form.project
      ? { kind: 'project', id: form.project.id, label: form.project.project_number }
      : null
  }
  if (form.productId === null) return null
  const label = productOptions.value.find((p) => p.value === form.productId)?.label ?? ''
  return { kind: 'product', id: form.productId, label }
})

// The product whose devices can be referenced: the owning product, or the
// product of the owning project when the project carries one. None while
// devices are switched off, which hides the device field.
const hostStore = useHostStore()
const deviceProductId = computed<number | null>(() => {
  if (!hostStore.devicesEnabled) return null
  if (form.kind === 'product') return form.productId
  if (form.kind === 'project') return form.project?.product_id ?? null
  return null
})

const devices = ref<ProductDevice[]>([])
const devicesLoading = ref(false)

watch(
  deviceProductId,
  async (productId, previous) => {
    // A product the user switched to makes the chosen device no longer fit.
    if (!keepDevice && productId !== previous) form.deviceId = null
    devices.value = []
    if (productId === null) return
    devicesLoading.value = true
    try {
      const loaded = await getProductDevices(productId, true)
      if (deviceProductId.value === productId) devices.value = loaded
    } finally {
      devicesLoading.value = false
    }
  },
)

const deviceOptions = computed(() =>
  devices.value
    .filter((d) => !d.archived || d.id === form.deviceId)
    .map((d) => ({ value: d.id, label: d.name_utf8 })),
)

const titleError = computed(() => form.title.trim() === '')
const ownerError = computed(() => owner.value === null)

function submit(): void {
  submitted.value = true
  if (titleError.value || !owner.value) return
  emit('save', {
    owner: owner.value,
    title: form.title.trim().slice(0, TITLE_MAX),
    note: form.note.trim() === '' ? null : form.note.trim().slice(0, NOTE_MAX),
    deviceId: deviceProductId.value === null ? null : form.deviceId,
  })
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="mode === 'create' ? t('tools.calculations.dialog.createTitle') : t('tools.calculations.dialog.editTitle')"
    :style="{ width: 'var(--dialog-width-md)' }"
    :breakpoints="{ '640px': '95vw' }"
  >
    <form class="save-form" @submit.prevent="submit">
      <div class="field">
        <label for="calc-owner-kind">{{ t('tools.calculations.dialog.owner') }}</label>
        <SelectButton
          id="calc-owner-kind"
          v-model="form.kind"
          :options="ownerOptions"
          option-label="label"
          option-value="value"
          :allow-empty="false"
          data-testid="calc-owner-kind"
        />
        <small class="hint">{{ t(`tools.calculations.dialog.ownerHint.${form.kind}`) }}</small>
      </div>

      <div v-if="form.kind === 'project'" class="field">
        <label id="calc-project-label" for="calc-project">{{ t('tools.calculations.owner.project') }}</label>
        <ProjectSelect v-model="form.project" input-id="calc-project" aria-labelledby="calc-project-label" />
      </div>
      <div v-if="form.kind === 'product'" class="field">
        <label id="calc-product-label" for="calc-product">{{ t('tools.calculations.owner.product') }}</label>
        <Select
          v-model="form.productId"
          input-id="calc-product"
          aria-labelledby="calc-product-label"
          :options="productOptions"
          option-label="label"
          option-value="value"
          :loading="productsStore.loading"
          filter
          fluid
        />
      </div>
      <small v-if="submitted && ownerError" class="error">
        {{ t('tools.calculations.dialog.ownerRequired') }}
      </small>

      <div v-if="deviceProductId !== null" class="field">
        <label id="calc-device-label" for="calc-device">{{ t('tools.calculations.dialog.device') }}</label>
        <Select
          v-model="form.deviceId"
          input-id="calc-device"
          aria-labelledby="calc-device-label"
          :options="deviceOptions"
          option-label="label"
          option-value="value"
          :loading="devicesLoading"
          :placeholder="t('tools.calculations.dialog.devicePlaceholder')"
          show-clear
          filter
          fluid
          data-testid="calc-device"
        />
      </div>

      <div class="field">
        <label for="calc-title">{{ t('tools.calculations.dialog.title') }}</label>
        <InputText
          id="calc-title"
          v-model="form.title"
          :maxlength="TITLE_MAX"
          :invalid="submitted && titleError"
          fluid
          data-testid="calc-title"
        />
        <small v-if="submitted && titleError" class="error">
          {{ t('tools.calculations.dialog.titleRequired') }}
        </small>
      </div>

      <div class="field">
        <label for="calc-note">{{ t('tools.calculations.dialog.note') }}</label>
        <Textarea id="calc-note" v-model="form.note" :maxlength="NOTE_MAX" rows="3" auto-resize fluid />
      </div>
    </form>

    <template #footer>
      <Button :label="t('common.cancel')" severity="secondary" text @click="visible = false" />
      <Button
        :label="t('common.save')"
        icon="mdi mdi-content-save-outline"
        :loading="busy"
        data-testid="calc-save-submit"
        @click="submit"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.save-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.error {
  color: var(--p-red-500);
}
</style>
