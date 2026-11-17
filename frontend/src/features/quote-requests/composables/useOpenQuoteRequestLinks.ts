import { ref, watch } from 'vue'

import { LiveResource } from '@/core/realtime/resources'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import { getOpenQuoteRequestLinks } from '../api/getOpenQuoteRequestLinks'
import type { OpenQuoteRequestRef } from '../types/quoteRequestsResponse'

export interface OpenQuoteRequestIds {
  boughtDemandIds?: number[]
  sourceDemandIds?: number[]
  lotPositionIds?: number[]
}

type LinkMap = Record<number, OpenQuoteRequestRef[]>

/**
 * The open quote requests that ask for the demands or lot positions a table
 * shows, for its "in quotation" markers. Fetched again when the shown ids
 * change and when a quote request changes anywhere. A failed fetch leaves
 * the markers as they were; they are a hint, not the record.
 */
export function useOpenQuoteRequestLinks(ids: () => OpenQuoteRequestIds) {
  const boughtDemands = ref<LinkMap>({})
  const sourceDemands = ref<LinkMap>({})
  const lotPositions = ref<LinkMap>({})
  let latest = 0

  async function refetch(): Promise<void> {
    const wanted = ids()
    const request = ++latest
    const empty =
      !wanted.boughtDemandIds?.length &&
      !wanted.sourceDemandIds?.length &&
      !wanted.lotPositionIds?.length
    if (empty) {
      boughtDemands.value = {}
      sourceDemands.value = {}
      lotPositions.value = {}
      return
    }
    try {
      const links = await getOpenQuoteRequestLinks({
        bought_demand_ids: wanted.boughtDemandIds ?? [],
        source_demand_ids: wanted.sourceDemandIds ?? [],
        lot_position_ids: wanted.lotPositionIds ?? [],
      })
      if (request !== latest) return
      // A response without a map, such as a stubbed one, shows no markers.
      boughtDemands.value = links?.bought_demands ?? {}
      sourceDemands.value = links?.source_demands ?? {}
      lotPositions.value = links?.lot_positions ?? {}
    } catch {
      // The markers keep what they showed.
    }
  }

  watch(
    () => JSON.stringify(ids()),
    () => void refetch(),
    { immediate: true },
  )
  useLiveRefresh(
    [LiveResource.QUOTE_REQUESTS, LiveResource.BOUGHT_ITEM_DEMANDS, LiveResource.SOURCE_ITEM_DEMANDS],
    refetch,
  )

  return { boughtDemands, sourceDemands, lotPositions, refetch }
}
