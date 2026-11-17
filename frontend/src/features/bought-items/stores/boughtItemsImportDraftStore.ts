// The draft of the bought-item batch create (Import from file). It survives
// a page reload in localStorage, like the demand imports, and is cleared on
// logout through BOUGHT_ITEM_IMPORT_DRAFT_STORAGE_KEY. A commit removes the
// rows it created and keeps the others for the next run.
import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'

import { cancelDraftWrite, scheduleDraftWrite } from '@/core/stores/draftWrites'
import { BOUGHT_ITEM_IMPORT_DRAFT_STORAGE_KEY } from '@/core/stores/resetOnLogout'
import { safeStorage } from '@/core/utils/safeStorage'
import { buildRowsFromMapping, readSpreadsheet } from '@/shared/spreadsheet-import'
import { commitBoughtItemImport, validateBoughtItemImport } from '../api/boughtItemsImportApi'
import {
  BOUGHT_ITEM_IMPORT_FIELDS,
  buildBoughtItemImportRow,
  importFieldsFor,
  isImportMappingComplete,
} from '../utils/boughtItemsImportFields'

import type { ColumnMapping } from '@/shared/spreadsheet-import'
import type { BoughtItemImportField } from '../utils/boughtItemsImportFields'
import type {
  BoughtItemImportResult,
  BoughtItemImportRow,
} from '../types/boughtItemsImportTypes'

export type BoughtItemImportStep = 'upload' | 'mapColumns' | 'review'

export interface BoughtItemImportDraftRow {
  clientId: string
  data: BoughtItemImportRow
}

interface PersistedState {
  step: BoughtItemImportStep
  lookup: boolean
  headers: string[]
  rawRows: Record<string, unknown>[]
  mapping: ColumnMapping<BoughtItemImportField>
  rows: BoughtItemImportDraftRow[]
  results: Record<string, BoughtItemImportResult>
}

const STEPS: BoughtItemImportStep[] = ['upload', 'mapColumns', 'review']

function emptyState(): PersistedState {
  return {
    step: 'upload',
    lookup: false,
    headers: [],
    rawRows: [],
    mapping: {},
    rows: [],
    results: {},
  }
}

function loadPersisted(): PersistedState {
  const raw = safeStorage.get(BOUGHT_ITEM_IMPORT_DRAFT_STORAGE_KEY)
  if (!raw) return emptyState()
  try {
    const parsed = JSON.parse(raw) as Partial<PersistedState> | null
    if (!parsed || typeof parsed !== 'object') return emptyState()
    if (parsed.step !== undefined && !STEPS.includes(parsed.step)) return emptyState()
    if (parsed.rows !== undefined && !Array.isArray(parsed.rows)) return emptyState()
    return { ...emptyState(), ...parsed }
  } catch {
    return emptyState()
  }
}

export const useBoughtItemsImportDraftStore = defineStore('boughtItemsImportDraft', () => {
  const initial = loadPersisted()

  const step = ref<BoughtItemImportStep>(initial.step)
  // Looks every row up in the EPLAN Data Portal; chosen before the upload.
  const lookup = ref(initial.lookup)
  const headers = ref<string[]>(initial.headers)
  const rawRows = ref<Record<string, unknown>[]>(initial.rawRows)
  const mapping = ref<ColumnMapping<BoughtItemImportField>>(initial.mapping)
  const rows = ref<BoughtItemImportDraftRow[]>(initial.rows)
  const results = ref<Record<string, BoughtItemImportResult>>(initial.results)
  // A reloaded or edited draft is re-validated before anything is created.
  const stale = ref(true)
  const isValidating = ref(false)
  const isCommitting = ref(false)

  const hasDraft = computed(() => rows.value.length > 0 || step.value !== 'upload')
  const readyCount = computed(() =>
    stale.value
      ? 0
      : rows.value.filter((r) => results.value[r.clientId]?.row_status === 'ready').length,
  )

  function snapshot(): PersistedState {
    return {
      step: step.value,
      lookup: lookup.value,
      headers: headers.value,
      rawRows: rawRows.value,
      mapping: mapping.value,
      rows: rows.value,
      results: results.value,
    }
  }

  watch(
    [step, lookup, headers, rawRows, mapping, rows, results],
    () => scheduleDraftWrite(BOUGHT_ITEM_IMPORT_DRAFT_STORAGE_KEY, snapshot),
    { deep: true },
  )

  function applyMapping(next: ColumnMapping<BoughtItemImportField>): void {
    mapping.value = next
    rows.value = buildRowsFromMapping(rawRows.value, next, {
      fields: BOUGHT_ITEM_IMPORT_FIELDS,
      buildRow: buildBoughtItemImportRow,
    }).map((data) => ({ clientId: crypto.randomUUID(), data }))
    results.value = {}
    stale.value = true
  }

  /** Throws SpreadsheetImportError for a sheet the import cannot use. */
  async function loadFile(file: File): Promise<void> {
    const table = await readSpreadsheet(file, 'bought_item_create', importFieldsFor(lookup.value))
    headers.value = table.headers
    rawRows.value = table.rows
    if (isImportMappingComplete(table.mapping, lookup.value)) {
      applyMapping(table.mapping)
      step.value = 'review'
    } else {
      mapping.value = table.mapping
      step.value = 'mapColumns'
    }
  }

  function confirmMapping(next: ColumnMapping<BoughtItemImportField>): void {
    applyMapping(next)
    step.value = 'review'
  }

  function updateRow(clientId: string, data: BoughtItemImportRow): void {
    const row = rows.value.find((r) => r.clientId === clientId)
    if (!row) return
    row.data = { ...data }
    stale.value = true
  }

  /** Pins the portal part the user picked for an ambiguous row. */
  function pinPart(clientId: string, partId: number): void {
    const row = rows.value.find((r) => r.clientId === clientId)
    if (row) updateRow(clientId, { ...row.data, edp_part_id: partId, skip_lookup: false })
  }

  /** Creates a row from the file alone although the lookup is on. */
  function skipLookup(clientId: string): void {
    const row = rows.value.find((r) => r.clientId === clientId)
    if (row) updateRow(clientId, { ...row.data, skip_lookup: true, edp_part_id: null })
  }

  function removeRow(clientId: string): void {
    rows.value = rows.value.filter((r) => r.clientId !== clientId)
    delete results.value[clientId]
    stale.value = true
  }

  function payload(): BoughtItemImportRow[] {
    return rows.value.map((r, index) => ({ ...r.data, row_index: index }))
  }

  async function validate(): Promise<void> {
    isValidating.value = true
    try {
      const response = await validateBoughtItemImport(payload(), lookup.value)
      const next: Record<string, BoughtItemImportResult> = {}
      rows.value.forEach((r, index) => {
        const result = response.results[index]
        if (result) next[r.clientId] = result
      })
      results.value = next
      stale.value = false
    } finally {
      isValidating.value = false
    }
  }

  /**
   * Creates the ready rows (and links existing items with the lookup) and
   * drops every handled row from the draft; returns how many were created.
   */
  async function commit(): Promise<number> {
    isCommitting.value = true
    try {
      const response = await commitBoughtItemImport(payload(), lookup.value)
      const handled = new Set(response.handled_row_indexes ?? [])
      rows.value = rows.value.filter((_, index) => !handled.has(index))
      results.value = {}
      stale.value = true
      if (rows.value.length === 0) discardDraft()
      return (response.created_item_ids ?? []).length
    } finally {
      isCommitting.value = false
    }
  }

  function discardDraft(): void {
    step.value = 'upload'
    lookup.value = false
    headers.value = []
    rawRows.value = []
    mapping.value = {}
    rows.value = []
    results.value = {}
    stale.value = true
    cancelDraftWrite(BOUGHT_ITEM_IMPORT_DRAFT_STORAGE_KEY)
    safeStorage.remove(BOUGHT_ITEM_IMPORT_DRAFT_STORAGE_KEY)
  }

  return {
    step,
    lookup,
    headers,
    rawRows,
    mapping,
    rows,
    results,
    stale,
    isValidating,
    isCommitting,
    hasDraft,
    readyCount,
    loadFile,
    confirmMapping,
    updateRow,
    pinPart,
    skipLookup,
    removeRow,
    validate,
    commit,
    discardDraft,
  }
})
