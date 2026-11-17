import { describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { computed, ref } from 'vue'
import type { Ref } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { controlledDocumentFields } from '@/test-utils/controlledDocument'
import type { DocumentAction } from '@/shared/documents'
import type { SavedCalculation } from '../../composables/useSavedCalculation'
import type { CalculationResponse } from '../../types/calculation'

vi.mock('@/core/api/projects/searchProjects', () => ({
  searchProjects: vi.fn<() => Promise<{ items: never[]; total: number; limit: number; skip: number }>>(
    async () => ({ items: [], total: 0, limit: 50, skip: 0 }),
  ),
}))
vi.mock('../../api/getCalculations', () => ({
  getCalculations: vi.fn<() => Promise<{ items: never[]; total: number; limit: number; skip: number }>>(
    async () => ({ items: [], total: 0, limit: 500, skip: 0 }),
  ),
}))

import ToolCalculationControls from '../ToolCalculationControls.vue'

interface FakeOverrides {
  unsaved?: boolean
  canCreate?: boolean
  calculation?: CalculationResponse
  offered?: Partial<Record<DocumentAction, boolean>>
  missing?: Partial<Record<DocumentAction, string>>
}

function fakeSaved(overrides: FakeOverrides = {}) {
  const startNew = vi.fn<() => Promise<void>>(async () => {})
  const saved = {
    calculation: computed(() => overrides.calculation ?? null),
    offered: ref({ edit: false, release: false, revise: false, invalidate: false, delete: false, ...overrides.offered }),
    missing: ref({ edit: null, release: null, revise: null, invalidate: null, delete: null, ...overrides.missing }),
    hasUnsavedChanges: ref(overrides.unsaved ?? false),
    dirty: ref(false),
    drift: ref(false),
    differences: ref([]),
    released: ref(false),
    loadFailed: ref(false),
    resolving: ref(false),
    toolReady: ref(true),
    busy: ref(false),
    canCreate: ref(overrides.canCreate ?? true),
    canUpdate: ref(false),
    canEdit: ref(false),
    canTakeOver: ref(false),
    takeOverBlocked: ref(''),
    canRevise: ref(false),
    editing: ref(false),
    latestRevision: ref(null),
    lostBy: ref([]),
    idleEnded: ref(0),
    lock: { busy: ref(false), lockedByOther: ref(null) },
    canRelease: ref(false),
    canMarkInvalid: ref(false),
    canDelete: ref(false),
    canPrint: ref(true),
    startNew,
  } as unknown as SavedCalculation
  return { saved, startNew }
}

async function mountControls(saved: SavedCalculation, extraProps: Record<string, unknown> = {}) {
  setActivePinia(createPinia())
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
  })
  const wrapper = mountWithApp(ToolCalculationControls, {
    props: {
      saved,
      toolKey: 'drive_sizing',
      tab: 'drive-sizing',
      defaultTitle: 'Vertical axis',
      defaultOwner: { kind: 'personal' },
      ...extraProps,
    },
    attachTo: document.body,
    global: { plugins: [router, ConfirmationService], directives: { tooltip: Tooltip } },
  })
  await flushPromises()
  return wrapper
}

function labels(wrapper: Awaited<ReturnType<typeof mountControls>>): string[] {
  return wrapper.findAll('button').map((b) => b.text()).filter(Boolean)
}

/** The tooltip of a button, kept by OpenVue's Tooltip directive on the span around it. */
function tooltipOf(button: { element: Element }): string | undefined {
  return (button.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null)?.$_ptooltipValue
}

function makeCalculation(overrides: Partial<CalculationResponse> = {}): CalculationResponse {
  return {
    ...controlledDocumentFields(),
    id: 5,
    public_id: '55555555-5555-4555-8555-555555555555',
    created: '2026-10-08T10:00:00Z',
    changed: '2026-10-08T10:00:00Z',
    tool: 'drive_sizing',
    title: 'Vertical axis',
    note: null,
    inputs: {},
    results: {},
    input_version: 1,
    engine_version: 1,
    project_id: null,
    project_number: null,
    product_id: null,
    product_number: null,
    product_device_id: null,
    product_device_name: null,
    creator_id: 2,
    creator_full_name: 'Other',
    released_at: null,
    released_by_id: null,
    released_by_full_name: null,
    changes: [],
    ...overrides,
  }
}

function acceptButton(label: string): HTMLButtonElement | undefined {
  return [...document.querySelectorAll<HTMLButtonElement>('button')].find(
    (b) => b.textContent?.trim() === label && b.closest('[role="alertdialog"], [role="dialog"]'),
  )
}

describe('ToolCalculationControls', () => {
  it('proposes the device the tool was opened from for a new calculation', async () => {
    const { saved } = fakeSaved()
    const wrapper = await mountControls(saved, {
      defaultOwner: { kind: 'product', id: 3, label: 'M26001' },
      defaultDeviceId: 9,
    })
    const initial = wrapper.findComponent({ name: 'SaveCalculationDialog' }).props('initial') as { deviceId: number | null }
    expect(initial.deviceId).toBe(9)
    wrapper.unmount()
  })

  it('lays out Save and Print, then the tool actions New and Load', async () => {
    const wrapper = await mountControls(fakeSaved().saved)

    expect(labels(wrapper)).toEqual(['Save', 'Print', 'New', 'Load'])
    wrapper.unmount()
  })

  it('keeps Save visible but disabled without the write permission', async () => {
    const wrapper = await mountControls(fakeSaved({ canCreate: false }).saved)

    const save = wrapper.get('[data-testid="calc-save"]')
    expect(save.attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })

  it('shows the actions on a calculation without the rights for them disabled, naming the missing permission', async () => {
    const { saved } = fakeSaved({
      calculation: makeCalculation(),
      offered: { edit: true, release: true, delete: true },
      missing: {
        edit: 'manage:calculations',
        release: 'release:calculations',
        delete: 'manage:calculations',
      },
    })
    const wrapper = await mountControls(saved)

    const edit = wrapper.get('[data-testid="calc-edit"]')
    expect(edit.attributes('disabled')).toBeDefined()
    expect(tooltipOf(edit)).toBe('This needs the permission Manage Calculations.')
    const release = wrapper.get('[data-testid="calc-release"]')
    expect(release.attributes('disabled')).toBeDefined()
    expect(tooltipOf(release)).toBe('This needs the permission Release Calculations.')
    const remove = wrapper.get('[data-testid="calc-delete"]')
    expect(remove.attributes('disabled')).toBeDefined()
    expect(tooltipOf(remove)).toBe('This needs the permission Manage Calculations.')
    expect(wrapper.find('[data-testid="calc-revise"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('keeps Save as New visible but disabled without the write permission', async () => {
    const { saved } = fakeSaved({ calculation: makeCalculation(), canCreate: false })
    const wrapper = await mountControls(saved)

    const saveAsNew = wrapper.get('[data-testid="calc-save-as-new"]')
    expect(saveAsNew.attributes('disabled')).toBeDefined()
    expect(tooltipOf(saveAsNew)).toContain('Write Calculations')
    wrapper.unmount()
  })

  it('releases from editing after saving first, and reads Done until something changes', async () => {
    const { saved } = fakeSaved({ calculation: makeCalculation(), offered: { release: true } })
    const release = vi.fn<() => Promise<void>>(async () => {})
    Object.assign(saved, { release, releaseSavesFirst: ref(true), canRelease: ref(true), editing: ref(true) })
    const wrapper = await mountControls(saved)

    expect(wrapper.get('[data-testid="calc-finish"]').text()).toBe('Done')
    ;(saved.dirty as unknown as Ref<boolean>).value = true
    await flushPromises()
    expect(wrapper.get('[data-testid="calc-finish"]').text()).toBe('Discard')

    await wrapper.get('[data-testid="calc-release"]').trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('Your unsaved changes are saved first.')
    acceptButton('Release')?.click()
    await flushPromises()
    expect(release).toHaveBeenCalledOnce()
    wrapper.unmount()
  })

  it('clears the tool for a new calculation only after confirming', async () => {
    const { saved, startNew } = fakeSaved()
    const wrapper = await mountControls(saved)

    await wrapper.get('[data-testid="calc-new-tool"]').trigger('click')
    await flushPromises()
    expect(startNew).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('Start a new calculation')

    acceptButton('Start new')?.click()
    await flushPromises()
    expect(startNew).toHaveBeenCalledOnce()
    wrapper.unmount()
  })
})
