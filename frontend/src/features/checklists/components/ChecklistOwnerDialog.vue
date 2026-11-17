<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useProductsStore } from '@/features/products'
import ProjectSelect from '@/shared/components/project/ProjectSelect.vue'
import type { ProjectRef } from '@/core/types/projectRef'
import type { ChecklistOwner } from '../types/checklist'
import { typeLabelKey } from '../utils/definitions'
import { CHECKLIST_OWNER_KINDS, CHECKLIST_TYPES } from '../utils/types'
import type { ChecklistType } from '../utils/types'

/**
 * Starts a checklist (type and owner) or moves a single-revision draft to
 * another owner. The owner comes preset from where the dialog was opened:
 * a project page offers its project, a product page its product. Only the
 * kinds of owner the checklist type allows are offered; when a type allows
 * just one, the choice of kind is left out.
 */

const props = defineProps<{
  mode: 'create' | 'owner'
  initialOwner: ChecklistOwner
  /** The type of the checklist whose owner changes; in create mode the type is chosen here. */
  type?: ChecklistType
  busy?: boolean
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{ save: [type: ChecklistType, owner: ChecklistOwner] }>()

const { t } = useI18n()
const productsStore = useProductsStore()

type OwnerKind = ChecklistOwner['kind']

const form = reactive({
  type: 'hydraulics' as ChecklistType,
  kind: 'personal' as OwnerKind,
  project: null as ProjectRef | null,
  productId: null as number | null,
})
const submitted = ref(false)

const allowedKinds = computed<readonly OwnerKind[]>(() => CHECKLIST_OWNER_KINDS[form.type])

function allowedKind(kind: OwnerKind): OwnerKind {
  return allowedKinds.value.includes(kind) ? kind : (allowedKinds.value[0] ?? 'personal')
}

function reset(): void {
  const owner = props.initialOwner
  if (props.type) form.type = props.type
  form.kind = allowedKind(owner.kind)
  form.project =
    owner.kind === 'project'
      ? { id: owner.id, project_number: owner.label, customer: null, description: null }
      : null
  form.productId = owner.kind === 'product' ? owner.id : null
  submitted.value = false
}

watch(visible, (open) => {
  if (open) reset()
})

watch(
  () => form.type,
  () => {
    form.kind = allowedKind(form.kind)
  },
)

onMounted(() => {
  if (!productsStore.items.length) void productsStore.refresh()
})

const typeOptions = computed(() => CHECKLIST_TYPES.map((value) => ({ value, label: t(typeLabelKey(value)) })))

const ownerOptions = computed(() =>
  allowedKinds.value.map((value) => ({
    value,
    label: t(`checklists.owner.${value}`),
  })),
)

// Checklists cannot be attached to an archived product, so archived ones
// are left out, except one the checklist already has.
const productOptions = computed(() =>
  productsStore.items
    .filter((p) => !p.archived || p.id === form.productId)
    .map((p) => ({
      value: p.id,
      label: p.description ? `${p.product_number} - ${p.description}` : p.product_number,
      number: p.product_number,
    })),
)

const owner = computed<ChecklistOwner | null>(() => {
  if (form.kind === 'personal') return { kind: 'personal' }
  if (form.kind === 'project') {
    return form.project ? { kind: 'project', id: form.project.id, label: form.project.project_number } : null
  }
  if (form.productId === null) return null
  const label = productOptions.value.find((p) => p.value === form.productId)?.number ?? ''
  return { kind: 'product', id: form.productId, label }
})

function submit(): void {
  submitted.value = true
  if (!owner.value) return
  emit('save', form.type, owner.value)
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="mode === 'create' ? t('checklists.dialog.createTitle') : t('checklists.dialog.ownerTitle')"
    :style="{ width: 'var(--dialog-width-md)' }"
    :breakpoints="{ '640px': '95vw' }"
  >
    <form class="owner-form" @submit.prevent="submit">
      <div v-if="mode === 'create'" class="field">
        <span id="cl-new-type-label">{{ t('checklists.type') }}</span>
        <SelectButton
          v-model="form.type"
          :options="typeOptions"
          option-label="label"
          option-value="value"
          :allow-empty="false"
          aria-labelledby="cl-new-type-label"
          data-testid="cl-new-type"
        />
      </div>

      <div v-if="ownerOptions.length > 1" class="field">
        <span id="cl-owner-kind-label">{{ t('checklists.dialog.owner') }}</span>
        <SelectButton
          v-model="form.kind"
          :options="ownerOptions"
          option-label="label"
          option-value="value"
          :allow-empty="false"
          aria-labelledby="cl-owner-kind-label"
          data-testid="cl-owner-kind"
        />
        <small class="hint">{{ t(`checklists.dialog.ownerHint.${form.kind}`) }}</small>
      </div>

      <div v-if="form.kind === 'project'" class="field">
        <label id="cl-owner-project-label" for="cl-owner-project">{{ t('checklists.owner.project') }}</label>
        <ProjectSelect v-model="form.project" input-id="cl-owner-project" aria-labelledby="cl-owner-project-label" />
      </div>
      <div v-if="form.kind === 'product'" class="field">
        <label id="cl-owner-product-label" for="cl-owner-product">{{ t('checklists.owner.product') }}</label>
        <Select
          v-model="form.productId"
          input-id="cl-owner-product"
          aria-labelledby="cl-owner-product-label"
          :options="productOptions"
          option-label="label"
          option-value="value"
          :loading="productsStore.loading"
          filter
          fluid
        />
      </div>
      <small v-if="submitted && !owner" class="error">{{ t('checklists.dialog.ownerRequired') }}</small>
    </form>

    <template #footer>
      <Button :label="t('common.cancel')" severity="secondary" text @click="visible = false" />
      <Button
        :label="mode === 'create' ? t('checklists.dialog.create') : t('common.save')"
        :icon="mode === 'create' ? 'mdi mdi-plus' : 'mdi mdi-content-save-outline'"
        :loading="busy"
        data-testid="cl-owner-submit"
        @click="submit"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.owner-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.error {
  color: var(--p-red-500);
}
</style>
