import { reactive, ref, watch } from 'vue'
import type { Reactive, Ref } from 'vue'

import { extractApiError } from '@/core/utils/errors'

export interface UseDemandEditFormOptions<TDemand extends { id: number }, TForm extends object> {
  /**
   * The dialog's own `visible = defineModel<boolean>('visible')` ref.
   * `defineModel`/`defineEmits` are compiler macros and can only be called
   * directly inside `<script setup>`, so the dialog creates this (and its
   * `emit`) itself and hands them in rather than the composable owning it.
   */
  visible: Ref<boolean>
  /**
   * Getter for the demand being edited, e.g. `() => props.demand`. A
   * function rather than a plain value so a prop change is picked up
   * without the caller having to pass a `computed` in.
   */
  demand: () => TDemand | null
  emptyForm: () => TForm
  formFromDemand: (demand: TDemand) => TForm
  /**
   * Extra side effects to run once the form fields are in place for a
   * newly opened demand: fetching an allocation summary, resetting other
   * dialog-local message/quantity refs, loading a referenced item. Unlike
   * `useEntityFormDialog`, this fires on any `visible`/`demand` combination
   * that is open-with-a-demand, not only a `false -> true` transition,
   * because a caller may swap the bound demand while the dialog stays open.
   */
  onOpen?: (demand: TDemand, form: TForm) => void | Promise<void>
  save: (id: number, form: TForm) => Promise<TDemand>
  /**
   * Called after a successful save with the updated demand, typically
   * just `(saved) => emit('updated', saved)`.
   */
  onSaved?: (saved: TDemand) => void
  /**
   * Shown when `save` rejects with something `extractApiError` can't read.
   * Already localized by the caller, same as every dialog's own
   * `errors.unknown` string today.
   */
  unknownErrorMessage: string
}

export interface UseDemandEditFormResult<TForm> {
  form: Reactive<TForm>
  saving: Ref<boolean>
  errorMessage: Ref<string | null>
  onSave: () => Promise<void>
}

/**
 * The open/save half of a demand detail dialog's edit form, repeated across
 * the bought/made/source-item demand detail dialogs: a reactive form
 * rebuilt from the demand whenever the dialog is open on one, and a save
 * that reports API errors the same way. Each family's own allocation side
 * of the dialog (auto-allocate, stock fulfillment, lots, cancellation)
 * stays with the family; this only owns the editable-fields form, mirroring
 * `useEntityFormDialog`'s create/edit split but keyed on an always-present
 * demand rather than an optional entity.
 */
export function useDemandEditForm<TDemand extends { id: number }, TForm extends object>(
  options: UseDemandEditFormOptions<TDemand, TForm>,
): UseDemandEditFormResult<TForm> {
  const form = reactive<TForm>(options.emptyForm())
  // `reactive<TForm>()` returns `Reactive<TForm>`, not `TForm` itself. Fine
  // in practice (these forms are plain data) but not something TS can prove
  // for a generic `TForm`. Bridged once here, like useEntityFormDialog does.
  const formAsTForm = form as TForm

  const saving = ref(false)
  const errorMessage = ref<string | null>(null)

  watch(
    () => [options.visible.value, options.demand()] as const,
    ([isVisible, demand]) => {
      if (isVisible && demand) {
        Object.assign(form, options.formFromDemand(demand))
        errorMessage.value = null
        void options.onOpen?.(demand, formAsTForm)
      }
    },
  )

  async function onSave(): Promise<void> {
    const demand = options.demand()
    if (!demand) return

    saving.value = true
    errorMessage.value = null

    try {
      const saved = await options.save(demand.id, formAsTForm)
      options.onSaved?.(saved)
    } catch (e) {
      errorMessage.value = extractApiError(e) ?? options.unknownErrorMessage
    } finally {
      saving.value = false
    }
  }

  return { form, saving, errorMessage, onSave }
}
