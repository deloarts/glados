import { computed, reactive, ref, watch } from 'vue'
import type { ComputedRef, Reactive, Ref } from 'vue'

import { extractApiError } from '@/core/utils/errors'

export interface UseEntityFormDialogOptions<TResponse, TForm extends object> {
  /** The dialog's own `defineModel` ref; macros only work in the dialog. */
  visible: Ref<boolean>
  /** Getter for the edited entity, so prop changes are picked up. */
  entity: () => TResponse | null | undefined
  emptyForm: () => TForm
  formFromEntity: (entity: TResponse) => TForm
  /** Returns an error message that aborts the submit, or null. */
  validate?: (form: TForm, isEditMode: boolean, entity: TResponse | null | undefined) => string | null
  save: (form: TForm, isEditMode: boolean, entity: TResponse | null | undefined) => Promise<TResponse>
  /** Called after a successful save, once the dialog is closed. */
  onSaved?: (saved: TResponse) => void
  /** Localized fallback for errors `extractApiError` cannot read. */
  unknownErrorMessage: string
}

export interface UseEntityFormDialogResult<TForm extends object> {
  form: Reactive<TForm>
  visible: Ref<boolean>
  submitting: Ref<boolean>
  errorMessage: Ref<string | null>
  isEditMode: ComputedRef<boolean>
  onSubmit: () => Promise<void>
  onCancel: () => void
}

/**
 * The create/edit `FormDialog` skeleton shared by the app's entity form
 * dialogs: a reactive form seeded from
 * `emptyForm()`/`formFromEntity()` depending on whether an entity prop is
 * set, reset on every `visible` false -> true transition, an `onSubmit`
 * that validates, calls `save`, closes the dialog and emits `saved`, and an
 * `onCancel` that just closes it. Each `*FormDialog` keeps owning its own
 * `<template>` (field types and counts genuinely diverge: checkbox vs
 * InputNumber vs Select) and its own `defineProps`/`defineEmits`/
 * `defineModel`; this only absorbs the logic behind them.
 *
 * Side effects that aren't part of resetting the form itself (e.g.
 * `FabricationMethodFormDialog` lazily loading its suppliers list the first
 * time it opens, or `ProductFormDialog` loading users on mount) stay in the
 * dialog as their own `watch`/`onMounted`; this composable only owns the
 * form lifecycle, not everything a dialog happens to do while open.
 */
export function useEntityFormDialog<TResponse, TForm extends object>(
  options: UseEntityFormDialogOptions<TResponse, TForm>,
): UseEntityFormDialogResult<TForm> {
  const { visible } = options

  const isEditMode = computed(() => options.entity() != null)

  const form = reactive<TForm>(options.emptyForm())
  const submitting = ref(false)
  const errorMessage = ref<string | null>(null)

  // `reactive<TForm>()` returns `Reactive<TForm>`, not `TForm` itself. Fine
  // in practice (these forms are plain data, no nested refs to unwrap) but
  // not something TS can prove for a generic `TForm`. This is the one place
  // that gap is bridged, so every caller-supplied callback below still sees
  // the plain `TForm` its signature promises.
  const formAsTForm = form as TForm

  watch(visible, (isVisible) => {
    if (!isVisible) return
    errorMessage.value = null
    const current = options.entity()
    Object.assign(form, current ? options.formFromEntity(current) : options.emptyForm())
  })

  async function onSubmit(): Promise<void> {
    const current = options.entity()
    const validationError = options.validate?.(formAsTForm, isEditMode.value, current) ?? null
    if (validationError) {
      errorMessage.value = validationError
      return
    }

    submitting.value = true
    errorMessage.value = null

    try {
      const saved = await options.save(formAsTForm, isEditMode.value, current)
      visible.value = false
      options.onSaved?.(saved)
    } catch (e) {
      errorMessage.value = extractApiError(e) ?? options.unknownErrorMessage
    } finally {
      submitting.value = false
    }
  }

  function onCancel(): void {
    visible.value = false
  }

  return { form, visible, submitting, errorMessage, isEditMode, onSubmit, onCancel }
}
