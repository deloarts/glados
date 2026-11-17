import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'

import type { BoughtItemFile } from '../../types/boughtItemsResponse'

// BoughtItemFilesSection is a thin wrapper declaring the bought-item
// category set over the shared FilesSection (see FilesSection.spec.ts for
// the from_pdm badge/lock behaviour itself, exercised there generically);
// this only pins that a real from_pdm file, ingested into one of THIS
// entity's own categories, actually renders it end to end.
//
// BoughtItemFileCategory (generated types) shares MadeItemFileCategory's
// full 7-value set, including "drawing"/"dxf": a purchased assembly can
// carry its own exported drawing/DXF, and a "documents"-kind watched folder
// can route either extension onto a bought item via document_categories.
// Without a slot for them, such a PDM-ingested file would exist on the
// backend but never render here; the "renders a from_pdm drawing" case
// below covers exactly that.

const hasPermissionMock = vi.fn<(permission: string) => boolean>().mockReturnValue(true)
vi.mock('@/core/composables/usePermissions', () => ({
  usePermissions: () => ({ hasPermission: (p: string) => hasPermissionMock(p) }),
}))

const getBoughtItemFilesMock = vi.fn<(itemId: number) => Promise<BoughtItemFile[]>>()
vi.mock('../../api/boughtItemFilesApi', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../api/boughtItemFilesApi')>()),
  getBoughtItemFiles: (itemId: number) => getBoughtItemFilesMock(itemId),
  getBoughtItemFilesForItems: vi
    .fn<(itemIds: number[]) => Promise<BoughtItemFile[]>>()
    .mockResolvedValue([]),
}))

import BoughtItemFilesSection from '../BoughtItemFilesSection.vue'

function makeFile(overrides: Partial<BoughtItemFile> = {}): BoughtItemFile {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    bought_item_id: 1,
    file_name: 'screw.step',
    stored_name: 'stored.step',
    mime_type: 'model/step',
    size_bytes: 4096,
    storage_path: '/files/stored.step',
    sha256: 'abc',
    category: 'step',
    created: '2026-09-01T10:00:00Z',
    uploaded_by_user_id: 1,
    url: null,
    from_pdm: false,
    ...overrides,
  }
}

describe('BoughtItemFilesSection', () => {
  beforeEach(() => {
    getBoughtItemFilesMock.mockReset()
    hasPermissionMock.mockReturnValue(true)
  })

  it('tags a PDM-ingested STEP file "PDM" and disables its replace/delete actions', async () => {
    getBoughtItemFilesMock.mockResolvedValue([makeFile({ category: 'step', from_pdm: true })])
    const wrapper = mountWithApp(BoughtItemFilesSection, {
      props: { itemId: 1 },
      global: { directives: { tooltip: Tooltip } },
    })
    await flushPromises()

    expect(wrapper.findComponent({ name: 'Tag' }).props('value')).toBe('PDM')
    // Locking replace/delete is FileActionButtons' own job (see its spec);
    // this only checks the bought-item wiring passes `locked` through for a
    // real from_pdm file in one of its own categories ("step").
    expect(wrapper.findComponent({ name: 'FileActionButtons' }).props('locked')).toBe(true)

    wrapper.unmount()
  })

  it('leaves a web-uploaded STEP file untagged, with FileActionButtons unlocked', async () => {
    getBoughtItemFilesMock.mockResolvedValue([makeFile({ category: 'step', from_pdm: false })])
    const wrapper = mountWithApp(BoughtItemFilesSection, {
      props: { itemId: 1 },
      global: { directives: { tooltip: Tooltip } },
    })
    await flushPromises()

    expect(wrapper.findComponent({ name: 'Tag' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'FileActionButtons' }).props('locked')).toBe(false)

    wrapper.unmount()
  })

  // A bought item can carry a "drawing" file (a purchased assembly's own
  // exported drawing, or one a "documents"-kind watched folder routed here
  // via document_categories); without the drawing/dxf slots, this category
  // would have nowhere to render, so the file would exist on the backend but
  // be invisible and undownloadable here.
  it('renders a from_pdm drawing file - visible, downloadable, tagged and locked', async () => {
    getBoughtItemFilesMock.mockResolvedValue([
      makeFile({
        id: 2,
        file_name: 'bracket-A.pdf',
        stored_name: 'stored.pdf',
        mime_type: 'application/pdf',
        category: 'drawing',
        from_pdm: true,
      }),
    ])
    const wrapper = mountWithApp(BoughtItemFilesSection, {
      props: { itemId: 1 },
      global: { directives: { tooltip: Tooltip } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('bracket-A.pdf')

    const actions = wrapper.findComponent({ name: 'FileActionButtons' })
    expect(actions.exists()).toBe(true)
    expect(actions.props('previewable')).toBe(true)
    expect(actions.props('locked')).toBe(true)
    expect(wrapper.findComponent({ name: 'Tag' }).props('value')).toBe('PDM')

    wrapper.unmount()
  })

  it('renders a web-uploaded dxf file - visible, downloadable, untagged and unlocked', async () => {
    getBoughtItemFilesMock.mockResolvedValue([
      makeFile({
        id: 3,
        file_name: 'plate.dxf',
        stored_name: 'stored.dxf',
        mime_type: 'application/dxf',
        category: 'dxf',
        from_pdm: false,
      }),
    ])
    const wrapper = mountWithApp(BoughtItemFilesSection, {
      props: { itemId: 1 },
      global: { directives: { tooltip: Tooltip } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('plate.dxf')
    expect(wrapper.findComponent({ name: 'Tag' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'FileActionButtons' }).props('locked')).toBe(false)

    wrapper.unmount()
  })
})
