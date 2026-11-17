import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'

import DemandImportReviewTable from '../DemandImportReviewTable.vue'
import { createDemandImportDraftStore } from '../../stores/createDemandImportDraftStore'

import type {
  DemandImportAdapter,
  DemandImportFieldSpec,
  ImportRowValidation,
} from '../../types/demandImport'

// A self-contained, bought-items-shaped fixture adapter. This module must
// not import anything from @/features/* (see src/shared/demand-import's own
// doc comments), so rather than the real bought-items adapter this
// reproduces its review-column shape locally. Reuses the real
// 'boughtItems.demands.batchCreate' i18n prefix (owned by core, not the
// feature) purely so the assertions below can check real rendered English
// strings.
type TestField = 'project' | 'quantity' | 'partNumber' | 'articleName' | 'orderCode' | 'manufacturerName'

interface TestRow {
  row_index: number
  project_number: string | null
  quantity: number | null
  part_number: string | null
  article_name: string | null
  order_code: string | null
  manufacturer_name: string | null
}

interface TestItem {
  id: number
  part_number: string | null
  article_name: string
}

type TestResult = ImportRowValidation<TestItem, 'article_name' | 'part_number', 'part_number' | 'order_code_manufacturer'>

const TEST_FIELDS: DemandImportFieldSpec<TestField>[] = [
  { key: 'project', alwaysRequired: true, kind: 'text', payloadKey: 'project_number' },
  { key: 'quantity', alwaysRequired: true, kind: 'number', payloadKey: 'quantity' },
  { key: 'partNumber', kind: 'text', payloadKey: 'part_number' },
  { key: 'articleName', kind: 'text', payloadKey: 'article_name' },
  { key: 'orderCode', kind: 'text', payloadKey: 'order_code' },
  { key: 'manufacturerName', kind: 'text', payloadKey: 'manufacturer_name' },
]

const testAdapter: DemandImportAdapter<TestField, TestRow, TestItem, TestResult> = {
  id: 'test-demand-import',
  importType: 'bought_item_demand',
  i18nPrefix: 'boughtItems.demands.batchCreate',
  storageKey: 'glados.testDemandImport.draft.v1',
  fields: TEST_FIELDS,
  isMappingComplete: (mapping) =>
    !!mapping.project && !!mapping.quantity && (!!mapping.partNumber || !!mapping.orderCode),
  isRowComplete: (row) => !!row.project_number && row.quantity !== null,
  buildRow: (values) => ({
    row_index: 0,
    project_number: (values.project as string | null) ?? null,
    quantity: (values.quantity as number | null) ?? null,
    part_number: (values.partNumber as string | null) ?? null,
    article_name: (values.articleName as string | null) ?? null,
    order_code: (values.orderCode as string | null) ?? null,
    manufacturer_name: (values.manufacturerName as string | null) ?? null,
  }),
  validate: async () => ({ results: [], all_valid: true }),
  commit: async () => ({ created_demand_ids: [] }),
  reviewColumns: [
    {
      key: 'partNumber',
      headerKey: 'review.partNumber',
      primary: (row) => row.part_number,
      secondary: (_row, result) =>
        result?.match_source === 'order_code_manufacturer' ? (result.matched_item?.part_number ?? null) : null,
    },
    {
      key: 'item',
      headerKey: 'review.item',
      primary: (row) => row.article_name,
      secondary: (_row, result) =>
        result?.divergences.some((d) => d.field === 'article_name')
          ? (result.matched_item?.article_name ?? null)
          : null,
    },
    {
      key: 'manufacturer',
      headerKey: 'review.manufacturer',
      primary: (row) => row.manufacturer_name,
    },
  ],
  divergenceLabel: (field, t) => t(`boughtItems.demands.batchCreate.divergenceField.${field}`),
  blockedHintKey: (status) => {
    switch (status) {
      case 'not_found':
        return 'boughtItems.demands.batchCreate.errors.itemNotFound'
      case 'unresolved_reference':
        return 'boughtItems.demands.batchCreate.errors.projectNotFound'
      default:
        return null
    }
  },
}

const useTestStore = createDemandImportDraftStore(testAdapter)
type TestStore = ReturnType<typeof useTestStore>

function makeRowInput(overrides: Partial<TestRow> = {}): TestRow {
  return {
    row_index: 0,
    project_number: 'PRJ-001',
    quantity: 2,
    part_number: 'PN-1',
    article_name: 'File Article Name',
    order_code: 'OC-1',
    manufacturer_name: 'Acme',
    ...overrides,
  }
}

function makeResult(overrides: Partial<TestResult> = {}): TestResult {
  return {
    row_index: 0,
    row_status: 'matched',
    match_source: 'part_number',
    matched_item: null,
    divergences: [],
    resolved_project_id: 1,
    errors: [],
    ...overrides,
  }
}

function seedRow(
  store: TestStore,
  rowOverrides: Partial<TestRow> = {},
  resultOverrides: Partial<TestResult> | null = {},
): string {
  store.addRow(makeRowInput(rowOverrides))
  const clientId = store.rows[store.rows.length - 1]!.clientId
  if (resultOverrides !== null) {
    store.validationResults[clientId] = makeResult(resultOverrides)
    store.validationStale = false
  }
  return clientId
}

function mountTable(pinia: ReturnType<typeof createPinia>, store: TestStore) {
  return mountWithApp(DemandImportReviewTable, { pinia, props: { adapter: testAdapter, store } })
}

describe('DemandImportReviewTable', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('renders no create-item / resolve-divergence / create-reference affordances for a not_found row', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useTestStore()
    seedRow(store, {}, { row_status: 'not_found', errors: ['No matching catalogue item'] })

    const wrapper = mountTable(pinia, store)
    const html = wrapper.html()

    expect(html).not.toContain('mdi-plus-box-outline')
    expect(html).not.toContain('mdi-swap-horizontal')
    expect(html).not.toContain('mdi-folder-plus-outline')
    // Only the Remove Row action remains in the actions column.
    expect(wrapper.find('[aria-label="Remove Row"]').exists()).toBe(true)
  })

  it('renders a warn icon and the file/catalogue values in Details for a matched row with a divergence', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useTestStore()
    seedRow(
      store,
      { article_name: 'File Name' },
      {
        row_status: 'matched',
        matched_item: { id: 1, part_number: 'PN-1', article_name: 'DB Name' },
        divergences: [{ field: 'article_name', db_value: 'DB Name', file_value: 'File Name' }],
      },
    )

    const wrapper = mountTable(pinia, store)

    expect(wrapper.find('.status-warn-icon').exists()).toBe(true)
    expect(wrapper.text()).toContain('File "File Name"')
    expect(wrapper.text()).toContain('Catalogue "DB Name"')
  })

  it('renders only the catalogue side for a divergence without a file value (e.g. a status warning)', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useTestStore()
    seedRow(
      store,
      { article_name: 'File Name' },
      {
        row_status: 'matched',
        matched_item: { id: 1, part_number: 'PN-1', article_name: 'File Name' },
        divergences: [{ field: 'article_name', db_value: 'replaced', file_value: null }],
      },
    )

    const wrapper = mountTable(pinia, store)

    expect(wrapper.find('.status-warn-icon').exists()).toBe(true)
    expect(wrapper.text()).toContain('Catalogue "replaced"')
    expect(wrapper.text()).not.toContain('File ""')
  })

  it('renders a danger tag and the itemNotFound hint for a not_found row', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useTestStore()
    seedRow(store, {}, { row_status: 'not_found', errors: ['No matching catalogue item'] })

    const wrapper = mountTable(pinia, store)

    const tag = wrapper.findComponent({ name: 'Tag' })
    expect(tag.props('severity')).toBe('danger')
    expect(tag.props('value')).toBe('Not found')
    expect(wrapper.text()).toContain(
      'No matching catalogue item. Create the item in the catalogue first.',
    )
  })

  it('renders the projectNotFound hint for an unresolved_reference row', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useTestStore()
    seedRow(store, {}, { row_status: 'unresolved_reference', errors: ['Project not found'] })

    const wrapper = mountTable(pinia, store)

    expect(wrapper.text()).toContain('Project not found. Create it on the Projects page first.')
  })

  it('calls store.removeRow when the Remove Row action is clicked', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useTestStore()
    const clientId = seedRow(store, {}, { row_status: 'matched' })

    const wrapper = mountTable(pinia, store)
    await wrapper.find('[aria-label="Remove Row"]').trigger('click')

    expect(store.rows.find((r) => r.clientId === clientId)).toBeUndefined()
  })

  it('renders the unvalidated status for a row with stale/no validation result', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useTestStore()
    // No result is seeded, so the store's own validationStale stays true, same
    // as right after addRow()/updateRow().
    seedRow(store, {}, null)

    const wrapper = mountTable(pinia, store)

    const tag = wrapper.findComponent({ name: 'Tag' })
    expect(tag.props('value')).toBe('Not Validated')
    expect(tag.props('severity')).toBe('secondary')
  })

  it("shows the catalogue part number when matched via order code + manufacturer, and the row's own quantity/project", () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useTestStore()
    seedRow(
      store,
      { part_number: null, project_number: 'PRJ-042', quantity: 7 },
      {
        row_status: 'matched',
        match_source: 'order_code_manufacturer',
        matched_item: { id: 1, part_number: 'PN-CATALOGUE', article_name: 'x' },
      },
    )

    const wrapper = mountTable(pinia, store)

    expect(wrapper.text()).toContain('PN-CATALOGUE')
    expect(wrapper.text()).toContain('PRJ-042')
    expect(wrapper.text()).toContain('7')
  })
})
