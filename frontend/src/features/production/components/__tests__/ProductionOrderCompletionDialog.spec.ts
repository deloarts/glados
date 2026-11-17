import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeProductionOrderResponse, userWithPermissions } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'

// files array returned for GET /production-orders/{id}/files. Swapped per
// test via filesGetResponse, defaults to "no evidence uploaded yet".
let filesGetResponse: unknown[] = []

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<(url: string) => Promise<unknown>>((url: string) => {
      if (url.endsWith('/files')) return Promise.resolve({ data: filesGetResponse })
      return Promise.resolve({ data: [] })
    }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    put: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    patch: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import ProductionOrderCompletionDialog from '../ProductionOrderCompletionDialog.vue'
import type { ProductionOrderResponse } from '../../types/productionOrdersResponse'
import type { LotStepResponse } from '../../types/productionLotsResponse'

function makeOrder(): ProductionOrderResponse {
  return makeProductionOrderResponse({ status: 'in_progress', quantity_completed: 4 })
}

const INSPECTION_STEP_BASE = {
  id: 2,
  public_id: '22222222-2222-2222-2222-222222222222',
  created: '2026-07-01',
  note: null,
  estimated_setup_minutes: null,
  estimated_minutes_per_piece: null,
  time_budget_per_piece: null,
  sequence: 2,
  creator_id: 1,
  fabrication_method_id: null,
  role: 'inspection' as const,
  fabrication_method_name: { enGB: '' },
  fabrication_method_requires_machine: false,
  fabrication_method_required_external: false,
  fabrication_method_default_supplier_id: null,
  lot_id: 1,
  position_id: 1,
  source_process_id: null,
}

function makeInspectionStep(requiresEvidence: boolean): LotStepResponse {
  return {
    ...INSPECTION_STEP_BASE,
    inspection_method_id: 5,
    inspection_method_name: requiresEvidence ? { enGB: 'Measurement' } : { enGB: 'Visual Inspection' },
    inspection_method_requires_evidence: requiresEvidence,
  } as LotStepResponse
}

// Mounts closed and opens it via setProps. The reset-on-open watcher only
// fires on a false -> true transition (mirrors the existing test above),
// so mounting pre-opened would skip populating the default accepted/
// rejected/quantity values every other test here depends on.
async function mountDialog(
  order: ProductionOrderResponse,
  steps: LotStepResponse[] = [],
  permissions: string[] = ['write:inspections'],
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)

  const wrapper = mountWithApp(ProductionOrderCompletionDialog, {
    pinia,
    attachTo: document.body,
    props: { visible: false, order, steps },
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  await flushPromises()
  return wrapper
}

describe('ProductionOrderCompletionDialog', () => {
  it('books once when Record is double-clicked', async () => {
    const api = (await import('@/core/api')).default
    const post = vi.mocked(api.post)
    post.mockClear()
    // Held open, so the second click lands while the first is still saving.
    post.mockImplementationOnce(() => new Promise(() => {}))
    const wrapper = await mountDialog(makeOrder(), [], ['write:production_orders'])

    const record = [...document.body.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Record')!
    record.click()
    await flushPromises()
    record.click()
    await flushPromises()

    expect(record.disabled).toBe(true)
    expect(post.mock.calls.filter(([url]) => String(url).endsWith('/completions'))).toHaveLength(1)

    wrapper.unmount()
  })

  it('renders without errors when opened and defaults quantity to the remainder', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountWithApp(ProductionOrderCompletionDialog, {
      attachTo: document.body,
      props: { visible: false, order: makeOrder() },
      // The handbook drawer reads the route, and this mount has no router.
      global: { stubs: { HelpDrawer: true } },
    })

    // The reset-on-open watcher only fires on a false -> true transition
    // (mirrors LotCreateDialog's convention), so open the dialog the same
    // way a real caller would rather than mounting pre-opened.
    await wrapper.setProps({ visible: true })
    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(wrapper.exists()).toBe(true)
    expect(logs).toEqual([])

    const vm = wrapper.vm as unknown as { quantity: number | null }
    expect(vm.quantity).toBe(6)

    wrapper.unmount()
  })

  it('defaults quantity to what the order has not processed, rejected pieces included', async () => {
    // 4 of 10 accepted and 2 scrapped: the order takes 4 more, not 6.
    const wrapper = mountWithApp(ProductionOrderCompletionDialog, {
      attachTo: document.body,
      props: {
        visible: false,
        order: makeProductionOrderResponse({
          status: 'in_progress',
          quantity: 10,
          quantity_completed: 4,
          quantity_processed: 6,
        }),
      },
    })
    await wrapper.setProps({ visible: true })
    await flushPromises()

    const vm = wrapper.vm as unknown as { quantity: number | null }
    expect(vm.quantity).toBe(4)

    wrapper.unmount()
  })

  it('is invalid without a positive quantity or a completion date', async () => {
    const wrapper = mountWithApp(ProductionOrderCompletionDialog, {
      attachTo: document.body,
      props: { visible: true, order: makeOrder() },
    })

    await flushPromises()

    const vm = wrapper.vm as unknown as { quantity: number | null; isValid: boolean }
    vm.quantity = 0
    await flushPromises()
    expect(vm.isValid).toBe(false)

    vm.quantity = 5
    await flushPromises()
    expect(vm.isValid).toBe(true)

    wrapper.unmount()
  })

  it('defaults accepted to the remainder and rejected to 0 for an inspection order', async () => {
    filesGetResponse = []
    const wrapper = await mountDialog(makeOrder(), [makeInspectionStep(false)])

    const vm = wrapper.vm as unknown as {
      isInspectionOrder: boolean
      acceptedQty: number | null
      rejectedQty: number | null
    }
    expect(vm.isInspectionOrder).toBe(true)
    expect(vm.acceptedQty).toBe(6)
    expect(vm.rejectedQty).toBe(0)

    wrapper.unmount()
  })

  it('requires accepted + rejected to be positive for an inspection order', async () => {
    filesGetResponse = []
    const wrapper = await mountDialog(makeOrder(), [makeInspectionStep(false)])

    const vm = wrapper.vm as unknown as {
      acceptedQty: number | null
      rejectedQty: number | null
      rejectReason: string | null
      isValid: boolean
    }
    vm.acceptedQty = 0
    vm.rejectedQty = 0
    await flushPromises()
    expect(vm.isValid).toBe(false)

    vm.acceptedQty = 4
    vm.rejectedQty = 2
    await flushPromises()
    // Rejected pieces need the reason they failed.
    expect(vm.isValid).toBe(false)
    vm.rejectReason = 'out_of_tolerance'
    await flushPromises()
    expect(vm.isValid).toBe(true)

    wrapper.unmount()
  })

  it('builds one per-unit disposition row per rejected piece, defaulting every row to rework', async () => {
    filesGetResponse = []
    const wrapper = await mountDialog(makeOrder(), [makeInspectionStep(false)])

    const vm = wrapper.vm as unknown as {
      rejectedQty: number | null
      perUnit: string[]
      reworkTotal: number
      scrapTotal: number
    }
    vm.rejectedQty = 3
    await flushPromises()

    expect(vm.perUnit).toEqual(['rework', 'rework', 'rework'])
    expect(vm.reworkTotal).toBe(3)
    expect(vm.scrapTotal).toBe(0)

    vm.perUnit[1] = 'replacement'
    await flushPromises()
    expect(vm.reworkTotal).toBe(2)
    expect(vm.scrapTotal).toBe(1)

    wrapper.unmount()
  })

  it('a fractional rejected quantity falls back to two fields that must sum to it', async () => {
    filesGetResponse = []
    const wrapper = await mountDialog(makeOrder(), [makeInspectionStep(false)])

    const vm = wrapper.vm as unknown as {
      rejectedQty: number | null
      reworkQty: number | null
      scrapQty: number | null
      dispositionValid: boolean
      isValid: boolean
      acceptedQty: number | null
      rejectReason: string | null
    }
    vm.rejectReason = 'material_defect'
    vm.acceptedQty = 3.5
    vm.rejectedQty = 2.5
    vm.reworkQty = 1
    vm.scrapQty = 1
    await flushPromises()
    expect(vm.dispositionValid).toBe(false)
    expect(vm.isValid).toBe(false)

    vm.scrapQty = 1.5
    await flushPromises()
    expect(vm.dispositionValid).toBe(true)
    expect(vm.isValid).toBe(true)

    wrapper.unmount()
  })

  it('an inspection order using a requires-evidence method is invalid until at least one evidence file exists', async () => {
    filesGetResponse = []
    const wrapper = await mountDialog(makeOrder(), [makeInspectionStep(true)])

    const vm = wrapper.vm as unknown as {
      acceptedQty: number | null
      rejectedQty: number | null
      hasMeasurementFile: boolean
      isValid: boolean
    }
    vm.acceptedQty = 6
    vm.rejectedQty = 0
    await flushPromises()
    expect(vm.hasMeasurementFile).toBe(false)
    expect(vm.isValid).toBe(false)

    wrapper.unmount()
  })

  it('an inspection order using a requires-evidence method becomes valid once an evidence file is on record', async () => {
    filesGetResponse = [
      {
        id: 9,
        production_order_id: 1,
        file_name: 'report.pdf',
        stored_name: 'report.pdf',
        mime_type: 'application/pdf',
        size_bytes: 1000,
        storage_path: '',
        sha256: '',
        category: 'measurement_report',
        created: '2026-08-14',
        uploaded_by_user_id: 1,
        url: 'https://example.com/report.pdf',
      },
    ]
    const wrapper = await mountDialog(makeOrder(), [makeInspectionStep(true)])

    const vm = wrapper.vm as unknown as {
      acceptedQty: number | null
      rejectedQty: number | null
      hasMeasurementFile: boolean
      isValid: boolean
    }
    vm.acceptedQty = 6
    vm.rejectedQty = 0
    await flushPromises()
    expect(vm.hasMeasurementFile).toBe(true)
    expect(vm.isValid).toBe(true)

    wrapper.unmount()
  })

  it('an inspection order using a no-evidence method needs no evidence file to be valid', async () => {
    filesGetResponse = []
    const wrapper = await mountDialog(makeOrder(), [makeInspectionStep(false)])

    const vm = wrapper.vm as unknown as {
      acceptedQty: number | null
      rejectedQty: number | null
      isValid: boolean
    }
    vm.acceptedQty = 6
    vm.rejectedQty = 0
    await flushPromises()
    expect(vm.isValid).toBe(true)

    wrapper.unmount()
  })

  it('a user without write:inspections can never record an inspection completion', async () => {
    filesGetResponse = []
    const wrapper = await mountDialog(makeOrder(), [makeInspectionStep(false)], [])

    const vm = wrapper.vm as unknown as {
      permissionBlocked: boolean
      acceptedQty: number | null
      rejectedQty: number | null
      isValid: boolean
    }
    expect(vm.permissionBlocked).toBe(true)

    vm.acceptedQty = 6
    vm.rejectedQty = 0
    await flushPromises()
    expect(vm.isValid).toBe(false)

    wrapper.unmount()
  })

  it('a non-inspection order is unaffected by having no write:inspections permission', async () => {
    filesGetResponse = []
    const wrapper = await mountDialog(makeOrder(), [], [])

    const vm = wrapper.vm as unknown as {
      isInspectionOrder: boolean
      permissionBlocked: boolean
      quantity: number | null
      isValid: boolean
    }
    expect(vm.isInspectionOrder).toBe(false)
    expect(vm.permissionBlocked).toBe(false)
    expect(vm.quantity).toBe(6)
    expect(vm.isValid).toBe(true)

    wrapper.unmount()
  })
})
