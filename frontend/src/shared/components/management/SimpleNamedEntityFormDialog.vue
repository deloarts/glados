<script setup lang="ts" generic="T extends SimpleNamedEntity">
// The create/edit dialog shared by every "simple named entity" resource, one
// with a name, a description and a label colour pair and nothing else. A resource with one more field of its
// own does not fit this component and should keep its own FormDialog. With
// `localized` the name and description are kept in every UI language at once
// and the name needs a text in the instance's default language.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useHostStore } from '@/core/host/stores/hostStore'
import LocalizedTextInput from '@/shared/components/forms/LocalizedTextInput.vue'
import { useLocalizedText } from '@/shared/composables/useLocalizedText'

import { useEntityFormDialog } from '@/shared/composables/useEntityFormDialog'
import LabelColorPairField from '@/shared/components/forms/LabelColorPairField.vue'
import type {
  AnyNamedEntityFormStore,
  SimpleNamedEntity,
  SimpleNamedEntityFormStore,
} from '@/shared/types/simpleNamedEntity'
import { DEFAULT_LABEL_COLOR, DEFAULT_LABEL_FONT_COLOR } from '@/shared/utils/labelColors'
import { cleanLocalizedText, type LocalizedText } from '@/shared/utils/localizedText'

interface Props {
  entity?: T
  /**
   * Lightweight prefill for the name field when creating from elsewhere
   * (e.g. a batch import row), ignored when editing an existing entity.
   */
  prefillName?: string
  /**
   * Prefixes this dialog's field ids, so they stay unique from any other
   * instance of this generic dialog on the same page.
   */
  idPrefix: string
  /**
   * i18n path prefix carrying this resource's fields/errors strings, e.g.
   * 'settings.articleGroups'. Every key below this prefix must follow the
   * same layout: fields.name, fields.description, fields.labelColor,
   * fields.labelFontColor, fields.preview, fields.previewPlaceholder,
   * errors.required, errors.unknown, and contrast.warning/contrast.fix when
   * showContrastWarning is set.
   */
  i18nPrefix: string
  /**
   * Already-translated dialog titles. The create/edit wording is not
   * uniform across resources (e.g. "Create Article Group" vs "Create Source
   * Item Type"), so it stays caller-supplied rather than derived.
   */
  createTitle: string
  editTitle: string
  /**
   * Opt in to the label/font-colour contrast warning. Only article groups
   * show it today.
   */
  showContrastWarning?: boolean
  /** Name and description are language maps (article groups, source item types). */
  localized?: boolean
  store: AnyNamedEntityFormStore<T>
}

const props = withDefaults(defineProps<Props>(), {
  showContrastWarning: false,
  localized: false,
})

const emit = defineEmits<{
  saved: [entity: T]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const host = useHostStore()
const { localize } = useLocalizedText()

// The plain fields serve the single-string resources, the maps the localized ones.
interface FormState {
  name: string
  description: string
  names: LocalizedText
  descriptions: LocalizedText
  label_color: string
  label_font_color: string
}

function asMap(text: LocalizedText | string | null | undefined): LocalizedText {
  return typeof text === 'string' ? {} : { ...text }
}

function createEmptyForm(): FormState {
  const prefill = props.prefillName ?? ''
  return {
    name: prefill,
    description: '',
    names: prefill ? { [host.defaultLanguage]: prefill } : {},
    descriptions: {},
    label_color: DEFAULT_LABEL_COLOR,
    label_font_color: DEFAULT_LABEL_FONT_COLOR,
  }
}

function formFromEntity(entity: T): FormState {
  return {
    name: typeof entity.name === 'string' ? entity.name : '',
    description: typeof entity.description === 'string' ? entity.description : '',
    names: asMap(entity.name),
    descriptions: asMap(entity.description),
    label_color: entity.label_color ?? DEFAULT_LABEL_COLOR,
    label_font_color: entity.label_font_color ?? DEFAULT_LABEL_FONT_COLOR,
  }
}

function hasName(form: FormState): boolean {
  return props.localized
    ? Boolean(form.names[host.defaultLanguage]?.trim())
    : Boolean(form.name.trim())
}

const { form, submitting, errorMessage, isEditMode, onSubmit, onCancel } = useEntityFormDialog<
  T,
  FormState
>({
  visible,
  entity: () => props.entity,
  emptyForm: createEmptyForm,
  formFromEntity,
  validate: (form) => (hasName(form) ? null : t(`${props.i18nPrefix}.errors.required`)),
  save: (form, isEditMode, entity) => {
    const colors = { label_color: form.label_color, label_font_color: form.label_font_color }
    if (props.localized) {
      const store = props.store as SimpleNamedEntityFormStore<T, LocalizedText>
      const payload = {
        ...colors,
        name: cleanLocalizedText(form.names),
        description: cleanLocalizedText(form.descriptions),
      }
      return isEditMode && entity ? store.update(entity.id, payload) : store.create(payload)
    }
    const store = props.store as SimpleNamedEntityFormStore<T, string>
    const payload = {
      ...colors,
      name: form.name.trim(),
      description: form.description.trim() || null,
    }
    return isEditMode && entity
      ? store.update(entity.id, payload)
      : store.create({ ...payload, description: payload.description ?? undefined })
  },
  onSaved: (saved) => emit('saved', saved),
  unknownErrorMessage: t(`${props.i18nPrefix}.errors.unknown`),
})

const previewText = computed(
  () =>
    (props.localized ? localize(form.names) : form.name) ||
    t(`${props.i18nPrefix}.fields.previewPlaceholder`),
)
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="isEditMode ? editTitle : createTitle"
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <form class="entity-form" @submit.prevent="onSubmit">
      <div class="form-fields">
        <template v-if="localized">
          <div class="field field-wide">
            <LocalizedTextInput
              v-model="form.names"
              :label="`${t(`${i18nPrefix}.fields.name`)} *`"
              :maxlength="200"
              required
            />
          </div>
          <div class="field field-wide">
            <LocalizedTextInput
              v-model="form.descriptions"
              :label="t(`${i18nPrefix}.fields.description`)"
              :maxlength="4000"
              multiline
            />
          </div>
        </template>
        <template v-else>
          <div class="field field-wide">
            <label :for="`${idPrefix}-name`">{{ t(`${i18nPrefix}.fields.name`) }} *</label>
            <InputText :id="`${idPrefix}-name`" v-model="form.name" fluid autocomplete="off" />
          </div>

          <div class="field field-wide">
            <label :for="`${idPrefix}-description`">{{
              t(`${i18nPrefix}.fields.description`)
            }}</label>
            <Textarea
              :id="`${idPrefix}-description`"
              v-model="form.description"
              rows="3"
              fluid
              auto-resize
            />
          </div>
        </template>

        <LabelColorPairField
          v-model:color="form.label_color"
          v-model:font-color="form.label_font_color"
          :color-id="`${idPrefix}-label-color`"
          :font-color-id="`${idPrefix}-font-color`"
          :color-label="t(`${i18nPrefix}.fields.labelColor`)"
          :font-color-label="t(`${i18nPrefix}.fields.labelFontColor`)"
          :preview-label="t(`${i18nPrefix}.fields.preview`)"
          :preview-text="previewText"
          :show-contrast-warning="showContrastWarning"
          :contrast-warning-text="showContrastWarning ? t(`${i18nPrefix}.contrast.warning`) : ''"
          :contrast-fix-label="showContrastWarning ? t(`${i18nPrefix}.contrast.fix`) : ''"
        />
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
.entity-form {
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
