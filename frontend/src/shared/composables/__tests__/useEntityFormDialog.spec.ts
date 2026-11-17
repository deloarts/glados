import { describe, it, expect, vi } from 'vitest'
import { nextTick, ref } from 'vue'

import { useEntityFormDialog } from '../useEntityFormDialog'

interface Entity {
  id: number
  name: string
}

interface FormState {
  name: string
}

function emptyForm(): FormState {
  return { name: '' }
}

function formFromEntity(entity: Entity): FormState {
  return { name: entity.name }
}

describe('useEntityFormDialog', () => {
  it('starts with an empty form and edit mode false when there is no entity', () => {
    const visible = ref(false)
    const { form, isEditMode } = useEntityFormDialog<Entity, FormState>({
      visible,
      entity: () => undefined,
      emptyForm,
      formFromEntity,
      save: vi.fn<(form: FormState, isEditMode: boolean, entity: Entity | null | undefined) => Promise<Entity>>(),
      unknownErrorMessage: 'unknown',
    })

    expect(form.name).toBe('')
    expect(isEditMode.value).toBe(false)
  })

  it('reports edit mode true when an entity is present', () => {
    const visible = ref(false)
    const { isEditMode } = useEntityFormDialog<Entity, FormState>({
      visible,
      entity: () => ({ id: 1, name: 'Milling' }),
      emptyForm,
      formFromEntity,
      save: vi.fn<(form: FormState, isEditMode: boolean, entity: Entity | null | undefined) => Promise<Entity>>(),
      unknownErrorMessage: 'unknown',
    })

    expect(isEditMode.value).toBe(true)
  })

  it('resets the form from the entity on a false -> true visible transition', async () => {
    const visible = ref(false)
    let entity: Entity | undefined = { id: 1, name: 'Milling' }
    const { form } = useEntityFormDialog<Entity, FormState>({
      visible,
      entity: () => entity,
      emptyForm,
      formFromEntity,
      save: vi.fn<(form: FormState, isEditMode: boolean, entity: Entity | null | undefined) => Promise<Entity>>(),
      unknownErrorMessage: 'unknown',
    })

    expect(form.name).toBe('')

    visible.value = true
    await nextTick()

    expect(form.name).toBe('Milling')

    // Editing the form, then reopening with no entity resets to empty. This is the
    // same "close and reopen" behaviour every hand-written watch(visible) had.
    form.name = 'Something typed'
    visible.value = false
    await nextTick()
    entity = undefined
    visible.value = true
    await nextTick()

    expect(form.name).toBe('')
  })

  it('does not touch the form while closing (true -> false)', async () => {
    const visible = ref(true)
    const { form } = useEntityFormDialog<Entity, FormState>({
      visible,
      entity: () => undefined,
      emptyForm,
      formFromEntity,
      save: vi.fn<(form: FormState, isEditMode: boolean, entity: Entity | null | undefined) => Promise<Entity>>(),
      unknownErrorMessage: 'unknown',
    })

    form.name = 'Draft'
    visible.value = false
    await nextTick()

    expect(form.name).toBe('Draft')
  })

  it('validate blocks the submit and neither calls save nor closes the dialog', async () => {
    const visible = ref(true)
    const save = vi.fn<(form: FormState, isEditMode: boolean, entity: Entity | null | undefined) => Promise<Entity>>()
    const { onSubmit, errorMessage } = useEntityFormDialog<Entity, FormState>({
      visible,
      entity: () => undefined,
      emptyForm,
      formFromEntity,
      validate: (form) => (form.name.trim() ? null : 'name is required'),
      save,
      unknownErrorMessage: 'unknown',
    })

    await onSubmit()

    expect(errorMessage.value).toBe('name is required')
    expect(save).not.toHaveBeenCalled()
    expect(visible.value).toBe(true)
  })

  it('onSubmit saves, closes the dialog, and calls onSaved with the result', async () => {
    const visible = ref(true)
    const saved: Entity = { id: 7, name: 'Anodizing' }
    const save = vi.fn<(form: FormState, isEditMode: boolean, entity: Entity | null | undefined) => Promise<Entity>>().mockResolvedValue(saved)
    const onSaved = vi.fn<() => void>()
    const { form, onSubmit, submitting, errorMessage } = useEntityFormDialog<Entity, FormState>({
      visible,
      entity: () => undefined,
      emptyForm,
      formFromEntity,
      save,
      onSaved,
      unknownErrorMessage: 'unknown',
    })
    form.name = 'Anodizing'

    const submitPromise = onSubmit()
    expect(submitting.value).toBe(true)
    await submitPromise

    expect(save).toHaveBeenCalledWith(form, false, undefined)
    expect(visible.value).toBe(false)
    expect(onSaved).toHaveBeenCalledWith(saved)
    expect(submitting.value).toBe(false)
    expect(errorMessage.value).toBeNull()
  })

  it('passes isEditMode and the entity through to save', async () => {
    const visible = ref(false)
    const entity: Entity = { id: 3, name: 'Milling' }
    const save = vi.fn<(form: FormState, isEditMode: boolean, entity: Entity | null | undefined) => Promise<Entity>>().mockResolvedValue(entity)
    const { onSubmit } = useEntityFormDialog<Entity, FormState>({
      visible,
      entity: () => entity,
      emptyForm,
      formFromEntity,
      save,
      unknownErrorMessage: 'unknown',
    })
    // Mirrors how the dialog itself opens: the form only populates from a
    // false -> true `visible` transition, not from an initial mount.
    visible.value = true
    await nextTick()

    await onSubmit()

    expect(save).toHaveBeenCalledWith(expect.objectContaining({ name: 'Milling' }), true, entity)
  })

  it('a rejected axios-shaped error is read via extractApiError', async () => {
    const visible = ref(true)
    const axiosError = {
      isAxiosError: true,
      response: { data: { detail: 'name already exists' } },
    }
    const save = vi.fn<(form: FormState, isEditMode: boolean, entity: Entity | null | undefined) => Promise<Entity>>().mockRejectedValue(axiosError)
    const { onSubmit, errorMessage, submitting } = useEntityFormDialog<Entity, FormState>({
      visible,
      entity: () => undefined,
      emptyForm,
      formFromEntity,
      save,
      unknownErrorMessage: 'unknown',
    })

    await onSubmit()

    expect(errorMessage.value).toBe('name already exists')
    expect(submitting.value).toBe(false)
  })

  it('falls back to unknownErrorMessage for a non-axios rejection, and leaves the dialog open', async () => {
    const visible = ref(true)
    const save = vi.fn<(form: FormState, isEditMode: boolean, entity: Entity | null | undefined) => Promise<Entity>>().mockRejectedValue(new Error('boom'))
    const { onSubmit, errorMessage } = useEntityFormDialog<Entity, FormState>({
      visible,
      entity: () => undefined,
      emptyForm,
      formFromEntity,
      save,
      unknownErrorMessage: 'something went wrong',
    })

    await onSubmit()

    expect(errorMessage.value).toBe('something went wrong')
    expect(visible.value).toBe(true)
  })

  it('onCancel closes the dialog without touching the form', () => {
    const visible = ref(true)
    const { form, onCancel } = useEntityFormDialog<Entity, FormState>({
      visible,
      entity: () => undefined,
      emptyForm,
      formFromEntity,
      save: vi.fn<(form: FormState, isEditMode: boolean, entity: Entity | null | undefined) => Promise<Entity>>(),
      unknownErrorMessage: 'unknown',
    })
    form.name = 'Draft'

    onCancel()

    expect(visible.value).toBe(false)
    expect(form.name).toBe('Draft')
  })
})
