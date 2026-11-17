import { reactive } from 'vue'
import { defineStore } from 'pinia'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { fetchPdmPreview } from './api'

import type { PdmItemKind, PdmPreviewFileResponse, PdmPreviewNewerResponse } from './api'

interface PdmPreviewKindState {
  enabled: boolean
  unlinked: PdmPreviewFileResponse[]
  // Keyed by the linked item's public_id rather than a real Map: every
  // store's state in this app is plain JSON-shaped data, since
  // resetOnLogout.ts's clonePlainState() walks state with Object.keys() and
  // silently turns a Map into `{}` on snapshot/restore. See that module's
  // own doc comment.
  newer: Record<string, PdmPreviewNewerResponse>
}

function emptyKindState(): PdmPreviewKindState {
  return { enabled: false, unlinked: [], newer: {} }
}

/**
 * Catalogue-facing PDM preview: files PDM has that the made/bought
 * catalogue hasn't (fully) caught up with, per kind. Shared across
 * features (unlike a feature's own createCatalogueEditStore-style
 * per-instance store) because the same data backs the toggle button and
 * panel in both made-items and bought-items catalogue views, plus the
 * "newer" badge on their tables and detail fields.
 */
export const usePdmPreviewStore = defineStore('pdmPreview', () => {
  const state = reactive<Record<PdmItemKind, PdmPreviewKindState>>({
    made: emptyKindState(),
    bought: emptyKindState(),
  })

  // Two independent sequenced fetches, one per kind, so a slow "made"
  // refresh in flight can never be superseded by (or race) a "bought" one;
  // see useSequencedFetch's own doc comment for what a single shared
  // instance would get wrong here.
  const madeFetch = useSequencedFetch(fetchPdmPreview)
  const boughtFetch = useSequencedFetch(fetchPdmPreview)

  async function load(kind: PdmItemKind): Promise<void> {
    const response = await (kind === 'made' ? madeFetch : boughtFetch).run(kind)
    if (!response) return

    const newer: Record<string, PdmPreviewNewerResponse> = {}
    for (const row of response.newer) newer[row.item_public_id] = row
    state[kind] = { enabled: response.enabled, unlinked: response.unlinked, newer }
  }

  /**
   * The preview row for `publicId` under `kind`, if the vault has a
   * release ahead of what was last ingested for it, undefined otherwise
   * (including while the preview hasn't been loaded yet).
   */
  function isNewer(kind: PdmItemKind, publicId: string): PdmPreviewNewerResponse | undefined {
    return state[kind].newer[publicId]
  }

  return {
    state,
    loadingMade: madeFetch.loading,
    loadingBought: boughtFetch.loading,
    load,
    isNewer,
  }
})
