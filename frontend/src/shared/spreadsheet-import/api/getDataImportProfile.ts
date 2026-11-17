import { webApi } from '@/core/api/webRequest'

import type { DataImportProfile, DataImportType } from '../types/spreadsheetImport'

export async function getDataImportProfile(importType: DataImportType): Promise<DataImportProfile> {
  return webApi.get('/data-import/profiles/{import_type}', { path: { import_type: importType } })
}
