import { describe, it, expect, vi } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'
import CatalogueItemFilesCard from '../CatalogueItemFilesCard.vue'
import type { CatalogueFileRow } from '../CatalogueItemFilesCard.vue'

function row(overrides: Partial<CatalogueFileRow> = {}): CatalogueFileRow {
  return {
    id: 1,
    file_name: 'part.step',
    category: 'step',
    mimeType: 'application/octet-stream',
    size: 1024,
    created: '2026-03-01T00:00:00Z',
    ...overrides,
  }
}

function categoryLabel(category: string): string {
  return `Category: ${category}`
}

function mountCard(overrides: Partial<InstanceType<typeof CatalogueItemFilesCard>['$props']> = {}) {
  return mountWithApp(CatalogueItemFilesCard, {
    props: {
      files: [],
      categoryLabel,
      canEdit: true,
      fetchBlob: vi.fn<(fileId: number) => Promise<Blob>>(),
      ...overrides,
    },
  })
}

describe('CatalogueItemFilesCard', () => {
  it('shows the empty state when there are no files', () => {
    const wrapper = mountCard({ files: [] })

    expect(wrapper.text()).toContain('No files for this item.')
  })

  it('renders one row per file with the category label and file name', () => {
    const wrapper = mountCard({
      files: [row({ id: 1, file_name: 'drawing.pdf', category: 'drawing' })],
    })

    const text = wrapper.text()
    expect(text).toContain('Category: drawing')
    expect(text).toContain('drawing.pdf')
  })

  it('renders rows in the order given, trusting the page to have sorted them', () => {
    const wrapper = mountCard({
      files: [
        row({ id: 1, file_name: 'b.pdf', category: 'pdf' }),
        row({ id: 2, file_name: 'a.dxf', category: 'dxf' }),
      ],
    })

    const names = wrapper.findAll('td').map((td) => td.text())
    const bIndex = names.findIndex((t) => t === 'b.pdf')
    const aIndex = names.findIndex((t) => t === 'a.dxf')
    expect(bIndex).toBeGreaterThanOrEqual(0)
    expect(aIndex).toBeGreaterThan(bIndex)
  })

  it('shows the size column, formatted, when rows carry a size', () => {
    const wrapper = mountCard({ files: [row({ size: 2048 })] })

    expect(wrapper.text()).toContain('2.0 KB')
  })

  it('hides the size column when no row carries a size', () => {
    const wrapper = mountCard({ files: [row({ size: null })] })

    expect(wrapper.text()).not.toContain('Size')
  })

  it('shows the uploaded column, formatted, when rows carry a created date', () => {
    const wrapper = mountCard({ files: [row({ created: '2026-03-15T00:00:00Z' })] })

    expect(wrapper.text()).toContain('2026-03-15')
  })

  it('hides the uploaded column when no row carries a created date', () => {
    const wrapper = mountCard({ files: [row({ created: null })] })

    expect(wrapper.text()).not.toContain('Uploaded')
  })

  it('shows delete when canEdit is true, and hides it when false', () => {
    const editable = mountCard({ files: [row()], canEdit: true })
    const readonly = mountCard({ files: [row()], canEdit: false })

    expect(editable.find('[data-testid="file-delete"]').exists()).toBe(true)
    expect(readonly.find('[data-testid="file-delete"]').exists()).toBe(false)
  })

  it('always shows download regardless of canEdit', () => {
    const wrapper = mountCard({ files: [row()], canEdit: false })

    expect(wrapper.find('[data-testid="file-download"]').exists()).toBe(true)
  })

  it('shows preview only for previewable files (pdf/image/mesh), not arbitrary ones', () => {
    const wrapper = mountCard({
      files: [
        row({ id: 1, file_name: 'drawing.pdf', mimeType: 'application/pdf' }),
        row({ id: 2, file_name: 'part.step', mimeType: 'application/octet-stream' }),
      ],
    })

    const previewButtons = wrapper.findAll('[data-testid="file-preview"]')
    expect(previewButtons).toHaveLength(1)
  })

  it('emits delete with the clicked row', async () => {
    const wrapper = mountCard({ files: [row({ id: 42 })], canEdit: true })

    await wrapper.find('[data-testid="file-delete"]').trigger('click')

    const emitted = wrapper.emitted('delete')
    expect(emitted).toBeTruthy()
    expect((emitted![0]![0] as CatalogueFileRow).id).toBe(42)
  })

  it('marks only the row currently deleting with a loading delete button', () => {
    const wrapper = mountCard({
      files: [row({ id: 1 }), row({ id: 2 })],
      canEdit: true,
      deleting: 2,
    })

    // OpenVue's Button swaps its icon for a spinner while `loading`, so the
    // delete buttons are counted by their testid, which stays put either way,
    // and the loading one by its `loading` prop.
    const deleteButtons = wrapper.findAll('[data-testid="file-delete"]')
    const loadingButtons = wrapper
      .findAllComponents({ name: 'Button' })
      .filter((button) => button.props('loading'))
    expect(deleteButtons).toHaveLength(2)
    expect(loadingButtons).toHaveLength(1)
  })

  it('opens the preview dialog with the clicked file', async () => {
    const fetchBlob = vi
      .fn<(fileId: number) => Promise<Blob>>()
      .mockResolvedValue(new Blob(['%PDF'], { type: 'application/pdf' }))
    const wrapper = mountCard({
      files: [row({ id: 7, file_name: 'drawing.pdf', mimeType: 'application/pdf' })],
      fetchBlob,
    })

    await wrapper.find('[data-testid="file-preview"]').trigger('click')

    const dialog = wrapper.findComponent({ name: 'FilePreviewDialog' })
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('filename')).toBe('drawing.pdf')
    expect(dialog.props('mimeType')).toBe('application/pdf')
  })
})
