import axios from 'axios'

import { webApi } from '@/core/api/webRequest'

import type { BoughtItemResponse } from '../types/boughtItemsResponse'
import type { EdpItemLookup, EdpLookupField, EdpSearchHit } from '../types/boughtItemsEdpTypes'

export async function searchEdpParts(query: string, limit = 10): Promise<EdpSearchHit[]> {
  const response = await webApi.get('/bought-items-edp/search', { query: { q: query, limit } })
  return response.hits
}

export async function lookupItemInEdp(itemId: number, partId?: number): Promise<EdpItemLookup> {
  return webApi.get('/bought-items-edp/items/{item_id}/lookup', {
    path: { item_id: itemId },
    query: partId === undefined ? {} : { part_id: partId },
  })
}

export async function applyEdpLookup(
  itemId: number,
  partId: number,
  fields: EdpLookupField[],
): Promise<BoughtItemResponse> {
  return webApi.post('/bought-items-edp/items/{item_id}/apply', {
    path: { item_id: itemId },
    body: { part_id: partId, fields },
  })
}

/** The part's product picture through Glados, null when it has none. */
export async function getEdpPartPicture(partId: number): Promise<Blob | null> {
  try {
    // The schema declares no body type for an image route, so the blob is cast.
    return (await webApi.get('/bought-items-edp/parts/{part_id}/picture', {
      path: { part_id: partId },
      config: { responseType: 'blob' },
    })) as Blob
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) return null
    throw error
  }
}
