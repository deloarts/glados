/**
 * Shared shape behind OpenVue DataTable's `groupRowsBy` (subheader mode):
 * map every row to a group-label field, then sort by it, since subheader
 * mode expects same-group rows to already be contiguous.
 *
 * `OrderItemsTable.vue`'s `groupedItems` and `LotsTable.vue`'s `groupedLots`
 * each retyped this computation branch-by-branch (one per grouping field)
 * despite the first admitting in its own comment that it mirrors the
 * second. This is the one implementation both use.
 */
export function groupRowsByLabel<T extends object, K extends string>(
  items: T[],
  groupField: K,
  labelFor: (item: T) => string,
): (T & Record<K, string>)[] {
  const mapped = items.map((item) => ({ ...item, [groupField]: labelFor(item) }) as T & Record<K, string>)
  return mapped.sort((a, b) => a[groupField].localeCompare(b[groupField]))
}
