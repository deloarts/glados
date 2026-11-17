import { webApi } from '@/core/api/webRequest'

import type { Schemas } from '@/core/api/generated'

/** The two item kinds PDM ingests. */
export type PdmItemKind = 'made' | 'bought'

export type PdmPreviewResponse = Schemas['PdmPreviewResponse']
export type PdmPreviewFileResponse = Schemas['PdmPreviewFileResponse']
export type PdmPreviewNewerResponse = Schemas['PdmPreviewNewerResponse']

/**
 * GET /pdm/preview?kind=made|bought: PDM files not yet (fully) reflected
 * in the catalogue: `unlinked` (never ingested) and `newer` (ingested but
 * behind the vault's latest release). `enabled` is false, with both lists
 * empty, whenever the PDM integration is off or unconfigured.
 */
export async function fetchPdmPreview(kind: PdmItemKind): Promise<PdmPreviewResponse> {
  return webApi.get('/pdm/preview', { query: { kind } })
}
