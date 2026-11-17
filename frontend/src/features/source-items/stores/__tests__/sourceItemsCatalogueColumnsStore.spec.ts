import { describe, it, expect } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'

import { i18n } from '@/core/i18n'
import {
  SOURCE_ITEMS_CATALOGUE_COLUMNS,
  createEmptySourceItemFilters,
  useSourceItemsCatalogueColumnsStore,
} from '../sourceItemsCatalogueColumnsStore'

// Adds the synthetic 'files' column (mesh + PDF icons, rendered by
// SourceItemFilesCell) alongside the existing synthetic 'image' column,
// mirrors MadeItemColumnField's 'image' | 'files' pair and its column-store
// wiring (MADE_ITEMS_CATALOGUE_COLUMNS / DEFAULT_VISIBLE_FIELDS).
describe('sourceItemsCatalogueColumnsStore files column', () => {
  it('declares a display-only files column with no backend filter, right after image', () => {
    const fields = SOURCE_ITEMS_CATALOGUE_COLUMNS.map((c) => c.field)
    const filesColumn = SOURCE_ITEMS_CATALOGUE_COLUMNS.find((c) => c.field === 'files')

    expect(filesColumn).toBeDefined()
    expect(filesColumn?.headerKey).toBe('sourceItems.catalogue.columns.files')
    expect(filesColumn?.filter).toBeUndefined()
    expect(fields.indexOf('files')).toBe(fields.indexOf('image') + 1)
  })

  it('creates no filter-meta entry for files - display-only, no backend query param', () => {
    const filters = createEmptySourceItemFilters()
    expect(filters.files).toBeUndefined()
  })

  // createCatalogueColumnsStore uses useI18n() internally, which needs a
  // real component instance (not just an active Pinia app) to resolve.
  it('is visible by default, alongside image', () => {
    let store!: ReturnType<typeof useSourceItemsCatalogueColumnsStore>
    mount(
      defineComponent({
        setup() {
          store = useSourceItemsCatalogueColumnsStore()
          return () => h('div')
        },
      }),
      { global: { plugins: [createPinia(), i18n] } },
    )

    const fields = store.visibleColumns.map((c) => c.field)
    expect(fields).toContain('files')
    expect(fields.indexOf('files')).toBe(fields.indexOf('image') + 1)
  })
})
