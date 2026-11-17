import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'


const getMock = vi.fn<(url: string) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => getMock(url),
  },
}))

import MadeItemProcessStagedEditor from '../MadeItemProcessStagedEditor.vue'
import type { MadeItemProcessCreateRequest } from '../../types/madeItemsRequest'
import { mountWithApp } from '@/test-utils/mountWithApp'

function makeCreateRequest(groupIndex: number | null): MadeItemProcessCreateRequest {
  return {
    fabrication_method_id: 1,
    note: null,
    estimated_setup_minutes: null,
    estimated_minutes_per_piece: null,
    group_index: groupIndex,
  }
}

function mountComponent(processes: MadeItemProcessCreateRequest[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mountWithApp(MadeItemProcessStagedEditor, {
    pinia,
    attachTo: document.body,
    props: { modelValue: processes },
  })
}

describe('MadeItemProcessStagedEditor', () => {
  beforeEach(() => {
    getMock.mockReset()
    getMock.mockImplementation((url: string) => {
      if (url === '/fabrication-methods/') {
        return Promise.resolve({
          data: {
            items: [
              {
                id: 1,
                public_id: '00000000-0000-0000-0000-000000000001',
                created: '2026-01-01',
                changed: null,
                changes: [],
                deleted: false,
                name: 'Milling',
                label_color: '#999999',
                label_font_color: '#000000',
                description: '',
                creator_id: 1,
              },
            ],
            total: 1,
            limit: 1000,
            skip: 0,
          },
        })
      }
      if (url === '/inspection-methods/') {
        return Promise.resolve({
          data: {
            items: [
              {
                id: 5,
                public_id: '00000000-0000-0000-0000-000000000005',
                created: '2026-01-01',
                changed: null,
                changes: [],
                deleted: false,
                name: 'Visual Inspection',
                label_color: '#999999',
                label_font_color: '#000000',
                description: '',
                requires_evidence: false,
                archived: false,
                creator_id: 1,
              },
            ],
            total: 1,
            limit: 1000,
            skip: 0,
          },
        })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 1000, skip: 0 } })
    })
  })

  it('appends a new process with group_index null (its own group)', async () => {
    const wrapper = mountComponent([])
    await flushPromises()

    const addButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === 'Add Step')!
    await addButton.trigger('click')
    await flushPromises()

    const emitted = wrapper.emitted('update:modelValue')!
    const last = emitted[emitted.length - 1]![0] as MadeItemProcessCreateRequest[]
    expect(last).toHaveLength(1)
    expect(last[0]!.group_index).toBeNull()

    wrapper.unmount()
  })

  it('removing a process renormalizes the remaining group_index runs', async () => {
    // group 0: [0, 1], group 1: [2].
    const processes = [makeCreateRequest(0), makeCreateRequest(0), makeCreateRequest(1)]
    const wrapper = mountComponent(processes)
    await flushPromises()

    const deleteButtons = wrapper
      .findAllComponents({ name: 'Button' })
      .filter((b) => b.props('icon') === 'mdi mdi-delete-outline')
    expect(deleteButtons).toHaveLength(3)

    // Remove the first member of group 0.
    await deleteButtons[0]!.trigger('click')
    await flushPromises()

    const emitted = wrapper.emitted('update:modelValue')!
    const last = emitted[emitted.length - 1]![0] as MadeItemProcessCreateRequest[]
    // Remaining two rows had distinct original group_index (0 and 1),
    // renormalized to two separate groups, 0 and 1.
    expect(last.map((p) => p.group_index)).toEqual([0, 1])

    wrapper.unmount()
  })

  it('the "Add Inspection" split-button item stages an inspection row using the first active method, not a fabrication one', async () => {
    const wrapper = mountComponent([])
    await flushPromises()

    const splitButton = wrapper.findComponent({ name: 'SplitButton' })
    const items = splitButton.props('model') as { label: string; command: () => void }[]
    const addInspectionItem = items.find((i) => i.label === 'Add Inspection')
    expect(addInspectionItem).toBeDefined()

    addInspectionItem!.command()
    await flushPromises()

    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted).toBeTruthy()
    const staged = emitted![emitted!.length - 1]![0] as MadeItemProcessCreateRequest[]
    expect(staged).toHaveLength(1)
    expect(staged[0]).toMatchObject({
      role: 'inspection',
      inspection_method_id: 5,
      fabrication_method_id: null,
    })

    wrapper.unmount()
  })

  it('renders a method Select (not a kind Select) for a staged inspection row', async () => {
    const wrapper = mountComponent([
      {
        role: 'inspection',
        fabrication_method_id: null,
        inspection_method_id: 5,
        note: null,
        estimated_setup_minutes: null,
        estimated_minutes_per_piece: null,
        group_index: null,
      },
    ])
    await flushPromises()

    const selects = wrapper.findAllComponents({ name: 'Select' })
    const methodSelect = selects.find((s) =>
      (s.props('options') as { id: number }[] | undefined)?.some((o) => o.id === 5),
    )
    expect(methodSelect).toBeDefined()
    expect(methodSelect!.props('modelValue')).toBe(5)

    wrapper.unmount()
  })
})
