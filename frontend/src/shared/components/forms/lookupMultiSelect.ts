/**
 * Option shape for `LookupMultiSelect`. Callers map their own API rows onto
 * it inside the `fetch` function they pass in, so the component stays free
 * of any feature import.
 */
export interface LookupOption {
  id: number
  /** Primary text, shown in the option row and as the chip label. */
  label: string
  /** Optional muted second line under the label in the option row. */
  sublabel?: string
}

export type LookupFetch = (query: string) => Promise<LookupOption[]>

/**
 * Resolves ids that are selected but not yet known to the component, so a
 * selection restored from outside (a persisted store, a deep link) gets its
 * labels. Ids the backend no longer knows may simply be missing from the
 * result.
 */
export type LookupFetchByIds = (ids: number[]) => Promise<LookupOption[]>
