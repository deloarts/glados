import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import Tooltip from 'openvue/tooltip'


let filesById: Record<number, unknown[]>

vi.mock('../../stores/sourceItemFilesStore', () => ({
  useSourceItemFilesStore: () => ({
    getFiles: (id: number) => filesById[id] ?? [],
    fetchFiles: vi.fn<(itemId: number) => Promise<void>>(),
  }),
}))

import SourceItemFilesCell from '../SourceItemFilesCell.vue'
import type { SourceItemFile } from '../../types/sourceItemsResponse'
import { mountWithApp } from '@/test-utils/mountWithApp'

function makeFile(overrides: Partial<SourceItemFile> = {}): SourceItemFile {
  return {
    id: 1,
    public_id: 'cccccccc-0000-0000-0000-000000000001',
    source_item_id: 1,
    file_name: 'stand-in.3mf',
    stored_name: 'stored-stand-in.3mf',
    mime_type: 'model/3mf',
    size_bytes: 2048,
    storage_path: '/files/1',
    sha256: 'abc',
    category: 'mesh',
    created: '2026-01-01T00:00:00Z',
    uploaded_by_user_id: 1,
    url: null,
    ...overrides,
  }
}

function mountCell(itemId: number) {
  return mountWithApp(SourceItemFilesCell, {
    props: { itemId },
    global: {
      directives: { tooltip: Tooltip },
    },
  })
}

describe('SourceItemFilesCell', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    filesById = {}
  })

  it('renders no icon for an item with zero files', () => {
    const wrapper = mountCell(1)

    expect(wrapper.find('i.mdi').exists()).toBe(false)
  })

  it('renders a mesh icon for a mesh file', () => {
    filesById[2] = [makeFile({ id: 10, source_item_id: 2, category: 'mesh' })]
    const wrapper = mountCell(2)

    const icon = wrapper.find('.icon-mesh')
    expect(icon.exists()).toBe(true)
    expect(icon.classes()).toContain('mdi-cube-outline')
  })

  it('renders a pdf icon per pdf file and emits preview on click', async () => {
    filesById[3] = [
      makeFile({ id: 11, source_item_id: 3, category: 'pdf', file_name: 'cert-a.pdf' }),
      makeFile({ id: 12, source_item_id: 3, category: 'pdf', file_name: 'cert-b.pdf' }),
    ]
    const wrapper = mountCell(3)

    const icons = wrapper.findAll('.icon-pdf')
    expect(icons).toHaveLength(2)

    await icons[0]!.trigger('click')
    expect(wrapper.emitted('preview')?.[0]?.[0]).toMatchObject({ id: 11, file_name: 'cert-a.pdf' })
  })

})
