import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { computed, defineComponent, ref } from 'vue'
import { createMemoryHistory, createRouter, useRoute } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import type { CalculationResponse } from '../../types/calculation'
import type { ToolState } from '../useToolState'

const getCalculationByPublicId = vi.fn<(id: string) => Promise<CalculationResponse>>()
const createCalculation = vi.fn<(body: unknown) => Promise<CalculationResponse>>()
const updateCalculation = vi.fn<(id: number, body: unknown) => Promise<CalculationResponse>>()
const deleteCalculation = vi.fn<(id: number) => Promise<void>>()

vi.mock('../../api/getCalculationByPublicId', () => ({
  getCalculationByPublicId: (id: string) => getCalculationByPublicId(id),
}))
vi.mock('../../api/createCalculation', () => ({
  createCalculation: (body: unknown) => createCalculation(body),
}))
vi.mock('../../api/updateCalculation', () => ({
  updateCalculation: (id: number, body: unknown) => updateCalculation(id, body),
}))
vi.mock('../../api/deleteCalculation', () => ({ deleteCalculation: (id: number) => deleteCalculation(id) }))

import { useSavedCalculation } from '../useSavedCalculation'
import { readLocalDraft, writeLocalDraft } from '@/shared/documents/utils/localDraft'
import { controlledDocumentFields } from '@/test-utils/controlledDocument'

const PUBLIC_ID = '55555555-5555-4555-8555-555555555555'
const NEW_ID = '99999999-9999-4999-8999-999999999999'

function makeCalculation(overrides: Partial<CalculationResponse> = {}): CalculationResponse {
  return {
    ...controlledDocumentFields(),
    id: 5,
    public_id: PUBLIC_ID,
    created: '2026-10-08T10:00:00Z',
    changed: '2026-10-08T10:00:00Z',
    tool: 'fit_calculator',
    title: 'Bearing seat',
    note: null,
    inputs: { d: '25', hole: 'H7', shaft: 'g6' },
    results: { fit: { type: 'clearance' } },
    input_version: 1,
    engine_version: 1,
    project_id: 3,
    project_number: 'P-003',
    product_id: null,
    product_number: null,
    product_device_id: null,
    product_device_name: null,
    creator_id: 1,
    creator_full_name: 'Tester',
    released_at: null,
    released_by_id: null,
    released_by_full_name: null,
    changes: [],
    ...overrides,
  }
}

const state = ref<ToolState | null>(null)

const Harness = defineComponent({
  setup() {
    const route = useRoute()
    const tab = computed(() => String(route.params.tab ?? 'fit-calculator'))
    return { saved: useSavedCalculation(tab, state) }
  },
  template: '<div />',
})

async function mountAt(path: string, permissions: string[] = ['write:calculations']) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = { id: 1, permissions, is_systemuser: false } as never
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/tools/:tab?/:calc?', name: 'Tools', component: Harness }],
  })
  router.push(path)
  await router.isReady()
  const wrapper = mountWithApp(Harness, { pinia, global: { plugins: [router, ConfirmationService] } })
  await flushPromises()
  return { router, saved: wrapper.vm.saved }
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  state.value = null
})

describe('useSavedCalculation', () => {
  it('loads the calculation named by its public id and hands its inputs to the tool', async () => {
    getCalculationByPublicId.mockResolvedValue(makeCalculation())
    const { router, saved } = await mountAt(`/tools/fit-calculator/${PUBLIC_ID}`)

    expect(getCalculationByPublicId).toHaveBeenCalledWith(PUBLIC_ID)
    expect(saved.calculation.value?.title).toBe('Bearing seat')
    expect(saved.initialInputs.value).toEqual({ d: '25', hole: 'H7', shaft: 'g6' })
    expect(saved.mountKey.value).toBe(1)
    expect(saved.resolving.value).toBe(false)
    expect(router.currentRoute.value.query).toEqual({})
  })

  it('moves to the tool the calculation belongs to', async () => {
    getCalculationByPublicId.mockResolvedValue(
      makeCalculation({ tool: 'drive_sizing', inputs: { m: '140' } }),
    )
    const { router } = await mountAt(`/tools/fit-calculator/${PUBLIC_ID}`)

    expect(router.currentRoute.value.fullPath).toBe(`/tools/drive-sizing/${PUBLIC_ID}`)
  })

  it('reports unsaved edits and changed results separately', async () => {
    getCalculationByPublicId.mockResolvedValue(makeCalculation())
    const { saved } = await mountAt(`/tools/fit-calculator/${PUBLIC_ID}`)

    state.value = { inputs: { d: '25', hole: 'H7', shaft: 'g6' }, results: { fit: { type: 'clearance' } }, title: '' }
    expect(saved.dirty.value).toBe(false)
    expect(saved.drift.value).toBe(false)
    expect(saved.canPrint.value).toBe(true)

    state.value = { inputs: { d: '25', hole: 'H7', shaft: 'g6' }, results: { fit: { type: 'transition' } }, title: '' }
    expect(saved.drift.value).toBe(true)
    expect(saved.differences.value).toEqual([{ path: 'fit.type', saved: 'clearance', current: 'transition' }])
    expect(saved.canPrint.value).toBe(false)

    state.value = { inputs: { d: '30', hole: 'H7', shaft: 'g6' }, results: {}, title: '' }
    expect(saved.dirty.value).toBe(true)
    expect(saved.drift.value).toBe(false)
  })

  it('saves a new calculation and names it in the URL', async () => {
    createCalculation.mockResolvedValue(
      makeCalculation({ id: 9, public_id: NEW_ID, project_id: null, project_number: null }),
    )
    const { router, saved } = await mountAt('/tools/fit-calculator')
    state.value = { inputs: { d: '25', hole: 'H7', shaft: 'g6' }, results: { fit: null }, title: 'x' }

    await saved.saveNew({ owner: { kind: 'personal' }, title: 'Seat', note: null, deviceId: null })
    await flushPromises()

    expect(createCalculation).toHaveBeenCalledWith({
      tool: 'fit_calculator',
      title: 'Seat',
      note: null,
      project_id: null,
      product_id: null,
      product_device_id: null,
      inputs: { d: '25', hole: 'H7', shaft: 'g6' },
      results: { fit: null },
      input_version: 1,
      engine_version: 1,
    })
    expect(router.currentRoute.value.fullPath).toBe(`/tools/fit-calculator/${NEW_ID}`)
    expect(saved.mountKey.value).toBe(0)
  })

  it('allows editing only own drafts, and releasing only with the permission', async () => {
    getCalculationByPublicId.mockResolvedValue(makeCalculation({ creator_id: 2 }))
    const { saved } = await mountAt(`/tools/fit-calculator/${PUBLIC_ID}`)
    state.value = { inputs: { d: '25', hole: 'H7', shaft: 'g6' }, results: { fit: { type: 'clearance' } }, title: '' }

    expect(saved.canUpdate.value).toBe(false)
    expect(saved.canDelete.value).toBe(false)
    expect(saved.canRelease.value).toBe(false)
  })

  it('deleting leaves the tool on an unsaved copy', async () => {
    getCalculationByPublicId.mockResolvedValue(makeCalculation())
    deleteCalculation.mockResolvedValue()
    const { router, saved } = await mountAt(`/tools/fit-calculator/${PUBLIC_ID}`)

    await saved.remove()
    await flushPromises()

    expect(deleteCalculation).toHaveBeenCalledWith(5)
    expect(router.currentRoute.value.fullPath).toBe('/tools/fit-calculator')
    expect(saved.calculation.value).toBeNull()
  })

  it('keeps the inputs of a tool without a calculation and starts on them again', async () => {
    vi.useFakeTimers()
    try {
      const first = await mountAt('/tools/drive-sizing')
      expect(first.saved.initialInputs.value).toBeNull()
      state.value = { inputs: { st: '1200' }, results: {}, title: '' }
      await vi.advanceTimersByTimeAsync(500)
      expect(readLocalDraft(1, 'calculation.new.drive_sizing')?.value).toEqual({ st: '1200' })

      state.value = null
      const second = await mountAt('/tools/drive-sizing')
      expect(second.saved.initialInputs.value).toEqual({ st: '1200' })
    } finally {
      vi.useRealTimers()
    }
  })

  it('offers the kept changes of a calculation and remounts the tool on them', async () => {
    writeLocalDraft(1, 'calculation.5', { inputs: { d: '30', hole: 'H7', shaft: 'g6' } }, '2026-10-08T10:00:00Z')
    getCalculationByPublicId.mockResolvedValue(makeCalculation())
    const { saved } = await mountAt(`/tools/fit-calculator/${PUBLIC_ID}`)

    expect(saved.draft.offer.value).toMatchObject({ stale: false })
    const mounted = saved.mountKey.value
    saved.restoreDraft()

    expect(saved.draft.offer.value).toBeNull()
    expect(saved.mountKey.value).toBe(mounted + 1)
    expect(saved.initialInputs.value).toEqual({ d: '30', hole: 'H7', shaft: 'g6' })
  })

  it('does not take the inputs of the tool being replaced for changes of the next calculation', async () => {
    getCalculationByPublicId.mockResolvedValue(makeCalculation())
    state.value = { inputs: { d: '99', hole: 'H7', shaft: 'g6' }, results: {}, title: '' }
    const { saved } = await mountAt(`/tools/fit-calculator/${PUBLIC_ID}`)

    // The tool that showed before the calculation loaded has not been replaced yet.
    expect(saved.dirty.value).toBe(false)
    state.value = { inputs: { d: '99', hole: 'H7', shaft: 'g6' }, results: {}, title: '' }
    expect(saved.dirty.value).toBe(true)
  })

})
