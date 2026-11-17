import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import Tooltip from 'openvue/tooltip'


import FilesSection from '../FilesSection.vue'
import type { FilesStoreInstance } from '@/core/stores/createFilesStore'
import { mountWithApp } from '@/test-utils/mountWithApp'
import { answerConfirmations } from '@/test-utils/confirmations'

// The smoke-mount spec for the host component FilesSection.vue; its logic
// seams (useMeshPreview, useImagePreviewCache, FileActionButtons) each carry
// their own focused spec alongside this file.

interface TestFile {
  id: number
  file_name: string
  mime_type: string
  size_bytes: number
  category: string
  from_pdm?: boolean
}

function makeFilesStore(files: TestFile[]): FilesStoreInstance<TestFile, string> {
  return {
    getFiles: vi.fn<(itemId: number) => TestFile[]>(() => files),
    isLoading: vi.fn<(itemId: number) => boolean>(() => false),
    fetchFiles: vi.fn<(itemId: number) => Promise<void>>().mockResolvedValue(undefined),
    refetchFiles: vi.fn<(itemId: number) => Promise<void>>().mockResolvedValue(undefined),
    upload: vi.fn<(itemId: number, file: File, category: string) => Promise<TestFile>>(),
    remove: vi.fn<(itemId: number, fileId: number) => Promise<void>>(),
    invalidate: vi.fn<(itemId: number) => void>(),
  }
}

function mountSection(overrides: {
  itemId?: number | null
  filesStore?: FilesStoreInstance<TestFile, string>
  canEdit?: boolean
  missingHint?: string
} = {}) {
  const filesStore =
    overrides.filesStore ??
    makeFilesStore([
      { id: 1, file_name: 'drawing.pdf', mime_type: 'application/pdf', size_bytes: 2048, category: 'documents' },
    ])

  return mountWithApp(FilesSection, {
    props: {
      itemId: 'itemId' in overrides ? (overrides.itemId as number | null) : 1,
      filesStore,
      multi: [{ key: 'documents', labelKey: 'common.files.noDocuments', accent: 'blue', icon: 'mdi mdi-file' }],
      canEdit: overrides.canEdit ?? true,
      missingHint: overrides.missingHint,
      fetchBlob: vi.fn<(itemId: number, fileId: number) => Promise<Blob>>().mockResolvedValue(new Blob(['x'])),
    },
    global: {
      directives: { tooltip: Tooltip },
    },
  })
}

describe('FilesSection', () => {
  it('mounts and renders the multi-category file list', () => {
    const wrapper = mountSection()

    expect(wrapper.find('.multi-name').text()).toBe('drawing.pdf')
    expect(wrapper.find('.multi-size').exists()).toBe(true)
  })

  it('refetches files for the item on mount', () => {
    const filesStore = makeFilesStore([])
    mountSection({ filesStore })

    expect(filesStore.refetchFiles).toHaveBeenCalledWith(1)
  })

  it('does not refetch when there is no item id yet', () => {
    const filesStore = makeFilesStore([])
    mountSection({ itemId: null, filesStore })

    expect(filesStore.refetchFiles).not.toHaveBeenCalled()
  })

  it('hides delete/upload affordances when canEdit is false', () => {
    const wrapper = mountSection({ canEdit: false })

    expect(wrapper.find('.multi-upload-trigger').exists()).toBe(false)
  })

  it('shows the upload and delete controls disabled with the missing permission as tooltip', () => {
    const hint = 'This needs the permission Write Orders.'
    const wrapper = mountSection({ canEdit: false, missingHint: hint })

    const triggers = wrapper.get('[data-testid="file-multi-triggers"]')
    expect((triggers.element as HTMLElement & { $_ptooltipValue?: string }).$_ptooltipValue).toBe(hint)
    expect(wrapper.get('.multi-upload-trigger').attributes('disabled')).toBeDefined()
    const actions = wrapper.findComponent({ name: 'FileActionButtons' })
    expect(actions.props('canEdit')).toBe(false)
    expect(actions.props('missingHint')).toBe(hint)
    expect(wrapper.find('.multi-empty').exists()).toBe(false)
  })

  it('shows an empty-category hint when there are no files and editing is disallowed', () => {
    const filesStore = makeFilesStore([])
    const wrapper = mountSection({ filesStore, canEdit: false })

    expect(wrapper.find('.multi-empty').exists()).toBe(true)
  })

  // ── from_pdm (made/bought item files ingested by the PDM sync) ──────────
  // FilesSection is entity-agnostic. `from_pdm` is optional on SectionFile
  // precisely so this behaviour is exercised once here rather than per
  // feature, even though only made/bought items ever set it true.

  it('tags a from_pdm multi-category file "PDM" and locks its FileActionButtons, unlike its plain sibling', () => {
    const filesStore = makeFilesStore([
      { id: 1, file_name: 'drawing.pdf', mime_type: 'application/pdf', size_bytes: 2048, category: 'documents', from_pdm: true },
      { id: 2, file_name: 'note.pdf', mime_type: 'application/pdf', size_bytes: 1024, category: 'documents' },
    ])
    const wrapper = mountSection({ filesStore })

    // Exactly one file is from_pdm, so exactly one "PDM" Tag renders.
    const tags = wrapper.findAllComponents({ name: 'Tag' })
    expect(tags).toHaveLength(1)
    expect(tags[0]!.props('value')).toBe('PDM')

    // Row order follows the store's file order: pdm file first, then plain.
    const actionButtons = wrapper.findAllComponents({ name: 'FileActionButtons' })
    expect(actionButtons).toHaveLength(2)
    expect(actionButtons[0]!.props('locked')).toBe(true)
    expect(actionButtons[1]!.props('locked')).toBe(false)
  })

  it('tags a from_pdm singleton-category file "PDM" and disables its replace and delete', () => {
    const filesStore = makeFilesStore([
      { id: 1, file_name: 'part.step', mime_type: 'model/step', size_bytes: 4096, category: 'step', from_pdm: true },
    ])
    const wrapper = mountWithApp(FilesSection, {
      props: {
        itemId: 1,
        filesStore,
        singletons: [
          { key: 'step', labelKey: 'common.files.upload', accent: 'teal', accept: '.step,.stp', render: 'file' },
        ],
        canEdit: true,
        fetchBlob: vi.fn<(itemId: number, fileId: number) => Promise<Blob>>().mockResolvedValue(new Blob(['x'])),
      },
      global: {
        directives: { tooltip: Tooltip },
      },
    })

    expect(wrapper.findComponent({ name: 'Tag' }).props('value')).toBe('PDM')
    // Locking replace/delete (while leaving preview/download alone) is
    // FileActionButtons' own job, already covered by its spec. This only
    // checks FilesSection passes `locked` through for a from_pdm singleton.
    expect(wrapper.findComponent({ name: 'FileActionButtons' }).props('locked')).toBe(true)
  })

  it('shows no PDM tag for a plain, non-PDM file', () => {
    const wrapper = mountSection()

    expect(wrapper.findComponent({ name: 'Tag' }).exists()).toBe(false)
  })

  // ── Upload status live region ────────────────────────────────────────
  // The spinner shown while a category uploads carried no text an assistive
  // tech user could pick up on; role="status"/aria-live="polite" plus a
  // visually-hidden label fixes that for both category shapes.

  it('marks the multi-category upload spinner as a polite live region while an upload is in flight', async () => {
    let resolveUpload!: (f: TestFile) => void
    const uploadPromise = new Promise<TestFile>((res) => {
      resolveUpload = res
    })
    const filesStore = makeFilesStore([])
    filesStore.upload = vi.fn<(itemId: number, file: File, category: string) => Promise<TestFile>>(
      () => uploadPromise,
    )
    const wrapper = mountSection({ filesStore })

    const vm = wrapper.vm as unknown as { onMultiInput: (e: Event, cat: string) => void }
    const input = document.createElement('input')
    Object.defineProperty(input, 'files', { value: [new File(['x'], 'drawing.pdf')] })
    vm.onMultiInput({ target: input } as unknown as Event, 'documents')
    await nextTick()

    const status = wrapper.find('.upload-status')
    expect(status.attributes('role')).toBe('status')
    expect(status.attributes('aria-live')).toBe('polite')
    expect(status.text()).toBe('Uploading…')

    resolveUpload({
      id: 1,
      file_name: 'drawing.pdf',
      mime_type: 'application/pdf',
      size_bytes: 1,
      category: 'documents',
    })
    await flushPromises()
  })

  it('marks the singleton upload spinner as a polite live region while an upload is in flight', async () => {
    let resolveUpload!: (f: TestFile) => void
    const uploadPromise = new Promise<TestFile>((res) => {
      resolveUpload = res
    })
    const filesStore = makeFilesStore([])
    filesStore.upload = vi.fn<(itemId: number, file: File, category: string) => Promise<TestFile>>(
      () => uploadPromise,
    )
    const wrapper = mountWithApp(FilesSection, {
      props: {
        itemId: 1,
        filesStore,
        singletons: [
          { key: 'step', labelKey: 'common.files.upload', accent: 'teal', accept: '.step,.stp', render: 'file' },
        ],
        canEdit: true,
        fetchBlob: vi.fn<(itemId: number, fileId: number) => Promise<Blob>>().mockResolvedValue(new Blob(['x'])),
      },
      global: {
        directives: { tooltip: Tooltip },
      },
    })

    const vm = wrapper.vm as unknown as { onSingletonInput: (e: Event, cat: string) => void }
    const input = document.createElement('input')
    Object.defineProperty(input, 'files', { value: [new File(['x'], 'part.step')] })
    vm.onSingletonInput({ target: input } as unknown as Event, 'step')
    await nextTick()

    const status = wrapper.find('.upload-status')
    expect(status.attributes('role')).toBe('status')
    expect(status.attributes('aria-live')).toBe('polite')

    resolveUpload({ id: 1, file_name: 'part.step', mime_type: 'model/step', size_bytes: 1, category: 'step' })
    await flushPromises()
  })

  it('deletes a file only after the user confirms', async () => {
    const confirmations = answerConfirmations('accept')
    const filesStore = makeFilesStore([
      { id: 1, file_name: 'drawing.pdf', mime_type: 'application/pdf', size_bytes: 2048, category: 'documents' },
    ])
    vi.mocked(filesStore.remove).mockResolvedValue(undefined)
    const wrapper = mountSection({ filesStore })

    await wrapper.find('button[aria-label="Delete"]').trigger('click')
    await flushPromises()
    confirmations.stop()

    expect(confirmations.asked[0]?.message).toContain('drawing.pdf')
    expect(filesStore.remove).toHaveBeenCalledWith(1, 1)
  })

  it('keeps the file when the user cancels', async () => {
    const confirmations = answerConfirmations('reject')
    const filesStore = makeFilesStore([
      { id: 1, file_name: 'drawing.pdf', mime_type: 'application/pdf', size_bytes: 2048, category: 'documents' },
    ])
    const wrapper = mountSection({ filesStore })

    await wrapper.find('button[aria-label="Delete"]').trigger('click')
    await flushPromises()
    confirmations.stop()

    expect(filesStore.remove).not.toHaveBeenCalled()
  })
})
