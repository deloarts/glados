<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useEntityFormDialog } from '@/shared/composables/useEntityFormDialog'
import LocalizedTextInput from '@/shared/components/forms/LocalizedTextInput.vue'
import { cleanLocalizedText, type LocalizedText } from '@/shared/utils/localizedText'
import {
  createProductDeviceOption,
  updateProductDeviceOption,
} from '../api/productDeviceResourcesApi'
import { useProductDeviceResourcesStore } from '../stores/productDeviceResourcesStore'
import type { ProductDeviceOption, ProductDeviceOptionCategory } from '../types/productDevice'

/**
 * Creates or edits one entry of a plain device list. Only a driving medium
 * has a letter; it becomes part of device names.
 */
const props = defineProps<{
  category: ProductDeviceOptionCategory
  option?: ProductDeviceOption
}>()

const emit = defineEmits<{ saved: [option: ProductDeviceOption] }>()
const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const store = useProductDeviceResourcesStore()

interface FormState {
  label: LocalizedText
  letter: string
}

const isMedium = computed(() => props.category === 'driving_medium')

const { form, submitting, errorMessage, isEditMode, onSubmit, onCancel } = useEntityFormDialog<
  ProductDeviceOption,
  FormState
>({
  visible,
  entity: () => props.option,
  emptyForm: () => ({ label: {}, letter: '' }),
  formFromEntity: (option) => ({ label: { ...option.label }, letter: option.letter ?? '' }),
  validate: (form) => {
    if (Object.keys(cleanLocalizedText(form.label)).length === 0) {
      return t('productDevices.resources.errors.labelRequired')
    }
    if (isMedium.value && !/^[A-Z]{1,4}$/.test(form.letter.trim())) {
      return t('productDevices.resources.errors.letterFormat')
    }
    return null
  },
  save: async (form, isEdit, option) => {
    const label = cleanLocalizedText(form.label)
    const letter = isMedium.value ? form.letter.trim() : null
    const saved =
      isEdit && option
        ? await updateProductDeviceOption(option.id, { label, letter })
        : await createProductDeviceOption({ category: props.category, label, letter })
    store.upsertOption(saved)
    return saved
  },
  onSaved: (saved) => emit('saved', saved),
  unknownErrorMessage: t('productDevices.resources.errors.unknown'),
})
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="
      isEditMode
        ? t('productDevices.resources.editEntry')
        : t('productDevices.resources.createEntry')
    "
    :style="{ width: 'var(--dialog-width-sm)' }"
  >
    <form class="option-form" @submit.prevent="onSubmit">
      <LocalizedTextInput
        v-model="form.label"
        :label="t('productDevices.resources.fields.label')"
        :maxlength="200"
        required
      />
      <div v-if="isMedium" class="field">
        <label for="pdo-letter">{{ t('productDevices.resources.fields.letter') }} *</label>
        <InputText
          id="pdo-letter"
          v-model="form.letter"
          :maxlength="4"
          autocomplete="off"
          aria-required="true"
          @update:model-value="form.letter = ($event ?? '').toUpperCase()"
        />
        <small class="hint">{{ t('productDevices.resources.fields.letterHint') }}</small>
      </div>

      <Message v-if="errorMessage" severity="error">{{ errorMessage }}</Message>

      <div class="form-footer">
        <Button
          type="button"
          :label="t('common.cancel')"
          severity="secondary"
          :disabled="submitting"
          @click="onCancel"
        />
        <Button type="submit" :label="t('common.save')" :loading="submitting" />
      </div>
    </form>
  </Dialog>
</template>

<style scoped lang="scss">
.option-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.field {
  label {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}
</style>
