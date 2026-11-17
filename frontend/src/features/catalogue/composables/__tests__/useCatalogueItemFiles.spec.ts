import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h, ref } from 'vue'

import { useHostStore } from '@/core/host/stores/hostStore'
import { mountWithApp } from '@/test-utils/mountWithApp'
import { answerConfirmations } from '@/test-utils/confirmations'

import { useCatalogueItemFiles } from '../useCatalogueItemFiles'
import type { CatalogueItemFile, CatalogueItemFilesStore } from '../useCatalogueItemFiles'

function makeFile(overrides: Partial<CatalogueItemFile> & { id: number }): CatalogueItemFile {
  return {
    file_name: `file-${overrides.id}`,
    category: 'pdf',
    mime_type: 'application/pdf',
    size_bytes: 10,
    created: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

function makeStore(files: CatalogueItemFile[]): CatalogueItemFilesStore<CatalogueItemFile> {
  return {
    getFiles: vi.fn<(itemId: number) => CatalogueItemFile[]>(() => files),
    isLoading: vi.fn<(itemId: number) => boolean>(() => false),
    fetchFiles: vi.fn<(itemId: number) => Promise<void>>(() => Promise.resolve()),
    refetchFiles: vi.fn<(itemId: number) => Promise<void>>(() => Promise.resolve()),
    remove: vi.fn<(itemId: number, fileId: number) => Promise<void>>(() => Promise.resolve()),
  }
}

function setup(
  files: CatalogueItemFile[],
  { storageEnabled = true, categories = ['dxf', 'pdf'] } = {},
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useHostStore().storageEnabled = storageEnabled
  const store = makeStore(files)
  const fetchBlob = vi.fn<(itemId: number, fileId: number) => Promise<Blob>>(() =>
    Promise.resolve(new Blob(['x'])),
  )
  const item = ref<{ id: number } | null>({ id: 7 })
  const holder: { result?: ReturnType<typeof useCatalogueItemFiles<CatalogueItemFile>> } = {}
  mountWithApp(
    defineComponent({
      setup() {
        holder.result = useCatalogueItemFiles({
          itemId: ref(7),
          item,
          filesStore: store,
          fetchBlob,
          filesCardCategories: categories,
          categoryLabelPrefix: 'boughtItems.catalogue.files.categories',
        })
        return () => h('div')
      },
    }),
    { pinia },
  )
  return { store, fetchBlob, item, result: holder.result! }
}

describe('useCatalogueItemFiles', () => {
  it('fetches the files of the item only while storage is enabled', () => {
    const enabled = setup([])
    const disabled = setup([], { storageEnabled: false })

    expect(enabled.store.fetchFiles).toHaveBeenCalledWith(7)
    expect(disabled.store.fetchFiles).not.toHaveBeenCalled()
  })

  it('finds the mesh', () => {
    const { result } = setup([
      makeFile({ id: 1, category: 'pdf' }),
      makeFile({ id: 3, category: 'mesh' }),
    ])

    expect(result.meshFile.value?.id).toBe(3)
  })

  it('lists only the card categories, in category order and then by name', () => {
    const { result } = setup([
      makeFile({ id: 1, category: 'pdf', file_name: 'b.pdf' }),
      makeFile({ id: 2, category: 'image', file_name: 'a.png' }),
      makeFile({ id: 3, category: 'pdf', file_name: 'a.pdf' }),
      makeFile({ id: 4, category: 'dxf', file_name: 'z.dxf' }),
    ])

    expect(result.filesCardRows.value.map((row) => row.id)).toEqual([4, 3, 1])
    expect(result.filesCardRows.value[0]).toMatchObject({
      file_name: 'z.dxf',
      category: 'dxf',
      mimeType: 'application/pdf',
      size: 10,
    })
  })

  it('fetches a blob for the loaded item and rejects without one', async () => {
    const { result, fetchBlob, item } = setup([])

    await result.fetchItemFileBlob(5)
    expect(fetchBlob).toHaveBeenCalledWith(7, 5)

    item.value = null
    await expect(result.fetchItemFileBlob(5)).rejects.toThrow('No item loaded.')
  })

  it('removes a file once confirmed, refetches the list and clears the deleting id', async () => {
    const confirmations = answerConfirmations('accept')
    const { result, store } = setup([])
    let finishRemove: () => void = () => {}
    vi.mocked(store.remove).mockImplementationOnce(
      () => new Promise<void>((resolve) => (finishRemove = resolve)),
    )

    const pending = result.onDeleteFile({ id: 9, file_name: 'a.pdf', category: 'pdf' })
    await flushPromises()
    expect(confirmations.asked[0]?.message).toContain('a.pdf')
    expect(result.deletingFileId.value).toBe(9)
    finishRemove()
    await pending
    await flushPromises()
    confirmations.stop()

    expect(store.remove).toHaveBeenCalledWith(7, 9)
    expect(store.refetchFiles).toHaveBeenCalledWith(7)
    expect(result.deletingFileId.value).toBeNull()
  })

  it('deletes nothing when the user cancels the confirmation', async () => {
    const confirmations = answerConfirmations('reject')
    const { result, store } = setup([])

    await result.onDeleteFile({ id: 9, file_name: 'a.pdf', category: 'pdf' })
    confirmations.stop()

    expect(store.remove).not.toHaveBeenCalled()
    expect(result.deletingFileId.value).toBeNull()
  })
})
