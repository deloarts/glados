// eslint-disable-next-line no-restricted-syntax -- the material source picker's selection, one of three item ids
export interface MaterialSource {
  bought_item_id: number | null
  source_item_id: number | null
  made_item_id: number | null
}

/**
 * Which fields the revision policy locks, see MaterialSourceSelect.
 * made_item_id has no policy field.
 */
export interface MaterialSourceFieldLocks {
  bought: boolean
  source: boolean
}
