import type { MenuItem } from 'openvue/menuitem'

/**
 * The "Add to bucket" submenu of the demand tables' context menus: one entry
 * per known bucket, a divider, then the entry that clears the bucket.
 * Buckets are created from the views bar, not from here.
 */
export function demandBucketMenuItems(
  buckets: { id: number; name: string }[],
  assign: (bucketId: number | null) => unknown,
  noBucketLabel: string,
): MenuItem[] {
  const items: MenuItem[] = buckets.map((bucket) => ({
    label: bucket.name,
    command: () => assign(bucket.id),
  }))

  items.push({ separator: true }, { label: noBucketLabel, command: () => assign(null) })

  return items
}
