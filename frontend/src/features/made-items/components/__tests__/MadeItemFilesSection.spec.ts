import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'

import type { MadeItemFile } from '../../types/madeItemsResponse'

// MadeItemFilesSection is a thin wrapper declaring the made-item category
// set over the shared FilesSection (see FilesSection.spec.ts for the
// from_pdm badge/lock behaviour itself, exercised there generically). This
// only pins that a real from_pdm file, ingested into one of THIS entity's
// own categories, actually renders it end to end.

const hasPermissionMock = vi.fn<(permission: string) => boolean>().mockReturnValue(true)
vi.mock('@/core/composables/usePermissions', () => ({
  usePermissions: () => ({ hasPermission: (p: string) => hasPermissionMock(p) }),
}))

const getMadeItemFilesMock = vi.fn<(itemId: number) => Promise<MadeItemFile[]>>()
vi.mock('../../api/madeItemFilesApi', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../api/madeItemFilesApi')>()),
  getMadeItemFiles: (itemId: number) => getMadeItemFilesMock(itemId),
  getMadeItemFilesForItems: vi.fn<(itemIds: number[]) => Promise<MadeItemFile[]>>().mockResolvedValue([]),
}))

import MadeItemFilesSection from '../MadeItemFilesSection.vue'

function makeFile(overrides: Partial<MadeItemFile> = {}): MadeItemFile {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    made_item_id: 1,
    file_name: 'bracket-A.pdf',
    stored_name: 'stored.pdf',
    mime_type: 'application/pdf',
    size_bytes: 2048,
    storage_path: '/files/stored.pdf',
    sha256: 'abc',
    category: 'drawing',
    created: '2026-09-01T10:00:00Z',
    uploaded_by_user_id: 1,
    url: null,
    from_pdm: false,
    ...overrides,
  }
}

describe('MadeItemFilesSection', () => {
  beforeEach(() => {
    getMadeItemFilesMock.mockReset()
    hasPermissionMock.mockReturnValue(true)
  })

  it('tags a PDM-ingested drawing "PDM" and disables its replace/delete actions', async () => {
    getMadeItemFilesMock.mockResolvedValue([makeFile({ category: 'drawing', from_pdm: true })])
    const wrapper = mountWithApp(MadeItemFilesSection, { props: { itemId: 1 }, global: { directives: { tooltip: Tooltip } } })
    await flushPromises()

    expect(wrapper.findComponent({ name: 'Tag' }).props('value')).toBe('PDM')
    // Locking replace/delete is FileActionButtons' own job (see its spec);
    // this only checks the made-item wiring passes `locked` through for a
    // real from_pdm file in one of its own categories ("drawing").
    expect(wrapper.findComponent({ name: 'FileActionButtons' }).props('locked')).toBe(true)

    wrapper.unmount()
  })

  it('leaves a web-uploaded drawing untagged, with FileActionButtons unlocked', async () => {
    getMadeItemFilesMock.mockResolvedValue([makeFile({ category: 'drawing', from_pdm: false })])
    const wrapper = mountWithApp(MadeItemFilesSection, { props: { itemId: 1 }, global: { directives: { tooltip: Tooltip } } })
    await flushPromises()

    expect(wrapper.findComponent({ name: 'Tag' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'FileActionButtons' }).props('locked')).toBe(false)

    wrapper.unmount()
  })
})
