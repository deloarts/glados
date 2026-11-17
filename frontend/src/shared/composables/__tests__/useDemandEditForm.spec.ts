import { describe, it, expect, vi } from 'vitest'
import { nextTick, ref } from 'vue'

import { useDemandEditForm } from '../useDemandEditForm'

interface Demand {
  id: number
  quantity: number
}

interface FormState {
  quantity: number
}

function formFromDemand(demand: Demand): FormState {
  return { quantity: demand.quantity }
}

function emptyForm(): FormState {
  return { quantity: 0 }
}

describe('useDemandEditForm', () => {
  it('starts from the empty form before the dialog ever opens', () => {
    const visible = ref(false)
    const { form } = useDemandEditForm<Demand, FormState>({
      visible,
      demand: () => null,
      emptyForm,
      formFromDemand,
      save: vi.fn<(id: number, form: FormState) => Promise<Demand>>(),
      unknownErrorMessage: 'unknown',
    })

    expect(form.quantity).toBe(0)
  })

  it('populates the form when visible and a demand are both present', async () => {
    const visible = ref(false)
    // A `ref` here, not a plain variable, so reading `.value` inside the
    // `demand` getter is the same reactive-tracking shape `() => props.demand`
    // has in the real dialog (Vue props are reactive too).
    const demand = ref<Demand | null>({ id: 1, quantity: 5 })
    const { form } = useDemandEditForm<Demand, FormState>({
      visible,
      demand: () => demand.value,
      emptyForm,
      formFromDemand,
      save: vi.fn<(id: number, form: FormState) => Promise<Demand>>(),
      unknownErrorMessage: 'unknown',
    })

    expect(form.quantity).toBe(0)

    visible.value = true
    await nextTick()

    expect(form.quantity).toBe(5)

    // A demand swap while the dialog stays open also repopulates the form;
    // unlike useEntityFormDialog, this composable watches both visible and
    // the demand, because a caller may rebind the demand without closing.
    demand.value = { id: 2, quantity: 9 }
    await nextTick()

    expect(form.quantity).toBe(9)
  })

  it('does nothing while there is no demand, even if visible', async () => {
    const visible = ref(true)
    const { form } = useDemandEditForm<Demand, FormState>({
      visible,
      demand: () => null,
      emptyForm,
      formFromDemand,
      save: vi.fn<(id: number, form: FormState) => Promise<Demand>>(),
      unknownErrorMessage: 'unknown',
    })

    form.quantity = 3
    await nextTick()

    expect(form.quantity).toBe(3)
  })

  it('runs onOpen after the form is populated, with the demand and the form', async () => {
    const visible = ref(false)
    const demand: Demand = { id: 1, quantity: 5 }
    const onOpen = vi.fn<(demand: Demand, form: FormState) => void>()
    useDemandEditForm<Demand, FormState>({
      visible,
      demand: () => demand,
      emptyForm,
      formFromDemand,
      onOpen,
      save: vi.fn<(id: number, form: FormState) => Promise<Demand>>(),
      unknownErrorMessage: 'unknown',
    })

    visible.value = true
    await nextTick()

    expect(onOpen).toHaveBeenCalledWith(demand, expect.objectContaining({ quantity: 5 }))
  })

  it('onSave does nothing without a demand', async () => {
    const visible = ref(true)
    const save = vi.fn<(id: number, form: FormState) => Promise<Demand>>()
    const { onSave } = useDemandEditForm<Demand, FormState>({
      visible,
      demand: () => null,
      emptyForm,
      formFromDemand,
      save,
      unknownErrorMessage: 'unknown',
    })

    await onSave()

    expect(save).not.toHaveBeenCalled()
  })

  it('onSave saves the current form against the demand id and calls onSaved with the result', async () => {
    const visible = ref(true)
    const demand: Demand = { id: 7, quantity: 5 }
    const saved: Demand = { id: 7, quantity: 12 }
    const save = vi.fn<(id: number, form: FormState) => Promise<Demand>>().mockResolvedValue(saved)
    const onSaved = vi.fn<(saved: Demand) => void>()
    const { form, onSave, errorMessage } = useDemandEditForm<Demand, FormState>({
      visible,
      demand: () => demand,
      emptyForm,
      formFromDemand,
      save,
      onSaved,
      unknownErrorMessage: 'unknown',
    })

    form.quantity = 12
    const savePromise = onSave()
    await savePromise

    expect(save).toHaveBeenCalledWith(7, expect.objectContaining({ quantity: 12 }))
    expect(onSaved).toHaveBeenCalledWith(saved)
    expect(errorMessage.value).toBeNull()
  })

  it('tracks saving true only while the save is in flight', async () => {
    const visible = ref(true)
    const demand: Demand = { id: 1, quantity: 1 }
    let resolveSave!: (value: Demand) => void
    const save = vi.fn<(id: number, form: FormState) => Promise<Demand>>().mockReturnValue(
      new Promise((resolve) => {
        resolveSave = resolve
      }),
    )
    const { saving, onSave } = useDemandEditForm<Demand, FormState>({
      visible,
      demand: () => demand,
      emptyForm,
      formFromDemand,
      save,
      unknownErrorMessage: 'unknown',
    })

    const savePromise = onSave()
    expect(saving.value).toBe(true)
    resolveSave(demand)
    await savePromise
    expect(saving.value).toBe(false)
  })

  it('a rejected axios-shaped error is read via extractApiError', async () => {
    const visible = ref(true)
    const demand: Demand = { id: 1, quantity: 1 }
    const axiosError = {
      isAxiosError: true,
      response: { data: { detail: 'quantity too high' } },
    }
    const save = vi
      .fn<(id: number, form: FormState) => Promise<Demand>>()
      .mockRejectedValue(axiosError)
    const { onSave, errorMessage, saving } = useDemandEditForm<Demand, FormState>({
      visible,
      demand: () => demand,
      emptyForm,
      formFromDemand,
      save,
      unknownErrorMessage: 'unknown',
    })

    await onSave()

    expect(errorMessage.value).toBe('quantity too high')
    expect(saving.value).toBe(false)
  })

  it('falls back to unknownErrorMessage for a non-axios rejection', async () => {
    const visible = ref(true)
    const demand: Demand = { id: 1, quantity: 1 }
    const save = vi
      .fn<(id: number, form: FormState) => Promise<Demand>>()
      .mockRejectedValue(new Error('boom'))
    const { onSave, errorMessage } = useDemandEditForm<Demand, FormState>({
      visible,
      demand: () => demand,
      emptyForm,
      formFromDemand,
      save,
      unknownErrorMessage: 'something went wrong',
    })

    await onSave()

    expect(errorMessage.value).toBe('something went wrong')
  })
})
