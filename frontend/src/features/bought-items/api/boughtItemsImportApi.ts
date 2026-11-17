import { webApi } from '@/core/api/webRequest'

import type {
  BoughtItemImportRow,
  CommitBoughtItemImportResponse,
  ValidateBoughtItemImportResponse,
} from '../types/boughtItemsImportTypes'

export async function validateBoughtItemImport(
  rows: BoughtItemImportRow[],
  lookup: boolean,
): Promise<ValidateBoughtItemImportResponse> {
  return webApi.post('/bought-items-import/validate', { body: { rows, lookup } })
}

export async function commitBoughtItemImport(
  rows: BoughtItemImportRow[],
  lookup: boolean,
): Promise<CommitBoughtItemImportResponse> {
  return webApi.post('/bought-items-import/commit', { body: { rows, lookup } })
}
