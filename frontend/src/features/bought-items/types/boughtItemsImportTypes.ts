import type { Schemas } from '@/core/api/generated'

// The bought-item batch create (Import from file).
export type BoughtItemImportRow = Schemas['BatchBoughtItemRowSchema']
export type BoughtItemImportResult = Schemas['BatchBoughtItemRowResponse']
export type BoughtItemImportRowStatus = BoughtItemImportResult['row_status']
export type BoughtItemImportDivergence = Schemas['BatchBoughtItemDivergenceResponse']
export type ValidateBoughtItemImportResponse = Schemas['ValidateBatchBoughtItemsResponse']
export type CommitBoughtItemImportResponse = Schemas['CommitBatchBoughtItemsResponse']
