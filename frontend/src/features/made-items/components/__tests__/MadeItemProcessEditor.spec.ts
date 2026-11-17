import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { makeMadeItemResponse, userWithPermissions } from '@/test-utils/factories'

import type { MadeItemResponse } from '../../types/madeItemsResponse'

const postMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>()

const INSPECTION_METHOD = {
  id: 5,
  public_id: '55555555-5555-5555-5555-555555555555',
  created: '2026-01-01',
  changed: null,
  deleted: false,
  name: 'Visual Inspection',
  description: '',
  label_color: '#999999',
  label_font_color: '#000000',
  requires_evidence: false,
  archived: false,
  creator_id: 1,
  creator: null,
}

const ARCHIVED_INSPECTION_METHOD = { ...INSPECTION_METHOD, id: 6, name: 'Old Inspection', archived: true }

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => {
      if (url === '/inspection-methods/') {
        return Promise.resolve({
          data: {
            items: [ARCHIVED_INSPECTION_METHOD, INSPECTION_METHOD],
            total: 2,
            limit: 1000,
            skip: 0,
          },
        })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 1000, skip: 0 } })
    },
    post: (url: string, payload: unknown) => {
      postMock(url, payload)
      return Promise.resolve({
        data: {
          id: 99,
          public_id: '99999999-9999-9999-9999-999999999999',
          created: '2026-08-14',
          note: null,
          estimated_setup_minutes: null,
          estimated_minutes_per_piece: null,
          creator_id: 1,
          role: 'inspection',
          fabrication_method_id: null,
          inspection_method_id: INSPECTION_METHOD.id,
          inspection_method_name: INSPECTION_METHOD.name,
          fabrication_method_name: '',
          made_item_id: 1,
          position: 0,
          group_index: 0,
        },
      })
    },
  },
}))

import MadeItemProcessEditor from '../MadeItemProcessEditor.vue'

function makeItem(overrides: Partial<MadeItemResponse> = {}): MadeItemResponse {
  return makeMadeItemResponse({
    public_id: '33333333-3333-3333-3333-333333333333',
    mass: 100,
    ...overrides,
  })
}

function mountEditor(item: MadeItemResponse) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(['write:made_items'])

  return mountWithApp(MadeItemProcessEditor, {
    pinia,
    attachTo: document.body,
    props: { item },
  })
}

describe('MadeItemProcessEditor', () => {
  it('the "Add Inspection" split-button item creates an inspection process using the first active method', async () => {
    postMock.mockClear()
    const wrapper = mountEditor(makeItem())

    await flushPromises()
    await flushPromises()

    const splitButton = wrapper.findComponent({ name: 'SplitButton' })
    const items = splitButton.props('model') as { label: string; command: () => void }[]
    const addInspectionItem = items.find((i) => i.label === 'Add Inspection')
    expect(addInspectionItem).toBeDefined()

    addInspectionItem!.command()
    await flushPromises()

    expect(postMock).toHaveBeenCalledWith(
      '/made-items/1/processes',
      expect.objectContaining({ role: 'inspection', inspection_method_id: INSPECTION_METHOD.id }),
    )
    expect(wrapper.emitted('updated')).toBeTruthy()

    wrapper.unmount()
  })

  it('renders a method Select (not a kind Select) for an inspection process row', async () => {
    const wrapper = mountEditor(
      makeItem({
        processes: [
          {
            id: 2,
            public_id: '22222222-2222-2222-2222-222222222222',
            created: '2026-08-01',
            note: null,
            estimated_setup_minutes: null,
            estimated_minutes_per_piece: null,
            creator_id: 1,
            role: 'inspection',
            fabrication_method_id: null,
            inspection_method_id: INSPECTION_METHOD.id,
            inspection_method_name: { enGB: INSPECTION_METHOD.name },
            fabrication_method_name: { enGB: '' },
            made_item_id: 1,
            position: 0,
            group_index: 0,
          },
        ],
      }),
    )

    await flushPromises()
    await flushPromises()

    const selects = wrapper.findAllComponents({ name: 'Select' })
    const methodSelect = selects.find((s) =>
      (s.props('options') as { id: number }[] | undefined)?.some(
        (o) => o.id === INSPECTION_METHOD.id,
      ),
    )
    expect(methodSelect).toBeDefined()
    expect(methodSelect!.props('modelValue')).toBe(INSPECTION_METHOD.id)

    wrapper.unmount()
  })

  // Referencing an already-archived method is allowed: it stays in the
  // options list (sorted after live ones), just visibly tagged.
  it('keeps an archived inspection method selectable, sorted after live ones', async () => {
    const wrapper = mountEditor(
      makeItem({
        processes: [
          {
            id: 2,
            public_id: '22222222-2222-2222-2222-222222222222',
            created: '2026-08-01',
            note: null,
            estimated_setup_minutes: null,
            estimated_minutes_per_piece: null,
            creator_id: 1,
            role: 'inspection',
            fabrication_method_id: null,
            inspection_method_id: INSPECTION_METHOD.id,
            inspection_method_name: { enGB: INSPECTION_METHOD.name },
            fabrication_method_name: { enGB: '' },
            made_item_id: 1,
            position: 0,
            group_index: 0,
          },
        ],
      }),
    )

    await flushPromises()
    await flushPromises()

    const selects = wrapper.findAllComponents({ name: 'Select' })
    const methodSelect = selects.find((s) =>
      (s.props('options') as { id: number }[] | undefined)?.some(
        (o) => o.id === INSPECTION_METHOD.id,
      ),
    )
    const options = methodSelect!.props('options') as { id: number; archived: boolean }[]

    expect(options.map((o) => o.id)).toEqual([INSPECTION_METHOD.id, ARCHIVED_INSPECTION_METHOD.id])

    wrapper.unmount()
  })
})
