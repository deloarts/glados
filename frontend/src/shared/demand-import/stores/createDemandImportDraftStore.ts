import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'

import type { Ref } from 'vue'

import { cancelDraftWrite, scheduleDraftWrite } from '@/core/stores/draftWrites'
import { safeStorage } from '@/core/utils/safeStorage'
import { buildRowsFromMapping, readSpreadsheet } from '@/shared/spreadsheet-import'

import type { ColumnMapping } from '@/shared/spreadsheet-import'
import type {
  DemandImportAdapter,
  DemandImportRow,
  DraftRow,
  ImportCommitResponse,
  ImportRowValidation,
  ImportStep,
} from '../types/demandImport'

const IMPORT_STEPS: ImportStep[] = ['upload', 'mapColumns', 'review']

function newClientId(): string {
  return crypto.randomUUID()
}

interface PersistedDraftState<K extends string, TRow, R> {
  step: ImportStep
  headers: string[]
  rawRows: Record<string, unknown>[]
  columnMapping: ColumnMapping<K>
  rows: DraftRow<TRow>[]
  validationResults: Record<string, R>
}

function emptyState<K extends string, TRow, R>(): PersistedDraftState<K, TRow, R> {
  return {
    step: 'upload',
    headers: [],
    rawRows: [],
    columnMapping: {},
    rows: [],
    validationResults: {},
  }
}

// Guards against both unparsable JSON and a differently-shaped draft left
// over from a previous storage-key version. In either case an old or
// malformed draft is discarded rather than migrated (each adapter can bump
// its own storageKey to invalidate old drafts).
function isPersistedDraftState<K extends string, TRow, R>(
  value: unknown,
): value is Partial<PersistedDraftState<K, TRow, R>> {
  if (value === null || typeof value !== 'object') return false
  const candidate = value as Partial<PersistedDraftState<K, TRow, R>>
  if (candidate.step !== undefined && !IMPORT_STEPS.includes(candidate.step)) return false
  if (candidate.rows !== undefined && !Array.isArray(candidate.rows)) return false
  return true
}

function loadPersisted<K extends string, TRow, R>(
  storageKey: string,
): PersistedDraftState<K, TRow, R> {
  const raw = safeStorage.get(storageKey)
  if (!raw) return emptyState()
  try {
    const parsed: unknown = JSON.parse(raw)
    if (!isPersistedDraftState<K, TRow, R>(parsed)) return emptyState()
    return { ...emptyState<K, TRow, R>(), ...parsed }
  } catch {
    return emptyState()
  }
}

/**
 * Builds a Pinia draft store for one demand-import adapter. The state,
 * computed values and actions are generic over the adapter's row, item and
 * validation-result types instead of hardcoding
 * BatchDemandRowInput/BoughtItemResponse/etc.
 *
 * The store id is namespaced per adapter (`demandImportDraft:${adapter.id}`)
 * so two adapters (bought-items, made-items, ...) can be registered in the
 * same app without colliding in Pinia's store registry. Persistence uses
 * `adapter.storageKey`. Register every adapter's storage key in
 * src/core/stores/resetOnLogout.ts's clearPersistedDrafts() so a draft never
 * survives logout.
 */
export function createDemandImportDraftStore<
  K extends string,
  TRow extends DemandImportRow,
  TItem,
  R extends ImportRowValidation<TItem>,
>(adapter: DemandImportAdapter<K, TRow, TItem, R>) {
  return defineStore(`demandImportDraft:${adapter.id}`, () => {
    const initial = loadPersisted<K, TRow, R>(adapter.storageKey)

    const step = ref<ImportStep>(initial.step)
    const headers = ref<string[]>(initial.headers)
    const rawRows = ref<Record<string, unknown>[]>(initial.rawRows)
    // Explicit `Ref<...>` casts below: Vue's ref() return type runs its
    // value type through UnwrapRef<T>, a distributive mapped type that
    // can't be proven equal to T while K/TRow/R are still open generic
    // parameters at this call site (verified empirically: vue-tsc reports
    // e.g. `data: UnwrapRef<TRow>` mismatching `data: TRow` on every
    // read/write otherwise). None of these ever hold an actual Ref as an
    // element, so the plain, non-unwrapped type is exactly correct. The
    // cast just tells the checker what ref()'s own generic-unaware
    // inference can't work out on its own.
    const columnMapping = ref(initial.columnMapping) as Ref<ColumnMapping<K>>
    const rows = ref(initial.rows) as Ref<DraftRow<TRow>[]>
    const validationResults = ref(initial.validationResults) as Ref<Record<string, R>>
    // Drafts can be hand-edited or reloaded after a refresh, so any cached
    // validation result must be treated as stale until re-checked, the
    // Create button stays gated on a fresh server-side Validate either way.
    const validationStale = ref(true)
    const isValidating = ref(false)
    const isCommitting = ref(false)

    const hasDraft = computed(() => rows.value.length > 0 || step.value !== 'upload')

    const allRowsValid = computed(() => {
      if (validationStale.value || rows.value.length === 0) return false
      return rows.value.every(
        (row) => validationResults.value[row.clientId]?.row_status === 'matched',
      )
    })

    // Rows with a (non-stale) validation result that didn't come back
    // matched. Drives the "N rows blocked" footer summary.
    const blockedRowCount = computed(() => {
      return rows.value.filter((row) => {
        const result = validationResults.value[row.clientId]
        return !!result && result.row_status !== 'matched'
      }).length
    })

    // Matched rows the backend still flagged a file/catalogue divergence on:
    // never blocking, just surfaced to the user.
    const warningRowCount = computed(() => {
      return rows.value.filter((row) => {
        const result = validationResults.value[row.clientId]
        return !!result && result.row_status === 'matched' && result.divergences.length > 0
      }).length
    })

    function snapshot(): PersistedDraftState<K, TRow, R> {
      return {
        step: step.value,
        headers: headers.value,
        rawRows: rawRows.value,
        columnMapping: columnMapping.value,
        rows: rows.value,
        validationResults: validationResults.value,
      }
    }

    watch(
      [step, headers, rawRows, columnMapping, rows, validationResults],
      () => scheduleDraftWrite(adapter.storageKey, snapshot),
      { deep: true },
    )

    function applyMapping(mapping: ColumnMapping<K>): void {
      columnMapping.value = mapping
      const built = buildRowsFromMapping(rawRows.value, mapping, adapter)
      rows.value = built.map((data) => ({ clientId: newClientId(), data }))
      validationResults.value = {}
      validationStale.value = true
    }

    // Throws SpreadsheetImportError for a sheet the import cannot use (no
    // recognisable header, no data, more rows than the profile allows).
    async function loadFile(file: File): Promise<void> {
      const { headers: parsedHeaders, rows: parsedRows, mapping } = await readSpreadsheet(
        file,
        adapter.importType,
        adapter.fields,
      )
      headers.value = parsedHeaders
      rawRows.value = parsedRows

      if (adapter.isMappingComplete(mapping)) {
        applyMapping(mapping)
        step.value = 'review'
      } else {
        columnMapping.value = mapping
        step.value = 'mapColumns'
      }
    }

    function confirmMapping(mapping: ColumnMapping<K>): void {
      applyMapping(mapping)
      step.value = 'review'
    }

    function addRow(data: TRow): void {
      rows.value.push({ clientId: newClientId(), data })
      validationStale.value = true
    }

    function removeRow(clientId: string): void {
      rows.value = rows.value.filter((r) => r.clientId !== clientId)
      delete validationResults.value[clientId]
      validationStale.value = true
    }

    function updateRow(clientId: string, patch: Partial<TRow>): void {
      const row = rows.value.find((r) => r.clientId === clientId)
      if (!row) return
      row.data = { ...row.data, ...patch }
      validationStale.value = true
    }

    async function validate(): Promise<void> {
      isValidating.value = true
      try {
        const payloadRows = rows.value.map(
          (r, index) => ({ ...r.data, row_index: index }) as TRow,
        )
        const response = await adapter.validate(payloadRows)
        const nextResults: Record<string, R> = {}
        rows.value.forEach((r, index) => {
          const result = response.results[index]
          if (result) nextResults[r.clientId] = result
        })
        validationResults.value = nextResults
        validationStale.value = false
      } finally {
        isValidating.value = false
      }
    }

    async function commit(): Promise<ImportCommitResponse> {
      isCommitting.value = true
      try {
        const payloadRows = rows.value.map(
          (r, index) => ({ ...r.data, row_index: index }) as TRow,
        )
        const response = await adapter.commit(payloadRows)
        discardDraft()
        return response
      } finally {
        isCommitting.value = false
      }
    }

    function discardDraft(): void {
      step.value = 'upload'
      headers.value = []
      rawRows.value = []
      columnMapping.value = {}
      rows.value = []
      validationResults.value = {}
      validationStale.value = true
      cancelDraftWrite(adapter.storageKey)
      safeStorage.remove(adapter.storageKey)
    }

    return {
      step,
      headers,
      rawRows,
      columnMapping,
      rows,
      validationResults,
      validationStale,
      isValidating,
      isCommitting,
      hasDraft,
      allRowsValid,
      blockedRowCount,
      warningRowCount,
      loadFile,
      confirmMapping,
      addRow,
      removeRow,
      updateRow,
      validate,
      commit,
      discardDraft,
    }
  })
}

/**
 * The public shape of a store built by createDemandImportDraftStore(adapter).
 * Components type their `store` prop with this rather than
 * `ReturnType<ReturnType<typeof createDemandImportDraftStore<...>>>`:
 * Pinia's own setup-store return type uses mapped types
 * (_StoreWithState/_StoreWithGetters) that don't resolve cleanly while
 * K/TRow/TItem/R are still open generic parameters at the *call site*
 * (verified empirically: vue-tsc reports every property as missing when a
 * component's own generics are threaded through that route). A store
 * returned by createDemandImportDraftStore(adapter)() is structurally
 * assignable to this interface regardless, because Pinia unwraps a setup store's
 * refs onto the store instance itself, so `store.step` is `ImportStep`, not
 * `Ref<ImportStep>`, exactly as this interface declares.
 */
export interface DemandImportDraftStore<
  K extends string,
  TRow extends DemandImportRow,
  TItem,
  R extends ImportRowValidation<TItem>,
> {
  step: ImportStep
  headers: string[]
  rawRows: Record<string, unknown>[]
  columnMapping: ColumnMapping<K>
  rows: DraftRow<TRow>[]
  validationResults: Record<string, R>
  validationStale: boolean
  isValidating: boolean
  isCommitting: boolean
  readonly hasDraft: boolean
  readonly allRowsValid: boolean
  readonly blockedRowCount: number
  readonly warningRowCount: number
  loadFile(file: File): Promise<void>
  confirmMapping(mapping: ColumnMapping<K>): void
  addRow(data: TRow): void
  removeRow(clientId: string): void
  updateRow(clientId: string, patch: Partial<TRow>): void
  validate(): Promise<void>
  commit(): Promise<ImportCommitResponse>
  discardDraft(): void
}
