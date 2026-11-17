// Shared helpers for the boundary-toggle grouping chain UI (see
// GroupingChain.vue): a group is an ordered run of ids; the set of
// "boundaries" is the ids (other than the first) that start a new group.

export function computeGroups(orderedIds: number[], boundaries: Set<number>): number[][] {
  const result: number[][] = []
  let current: number[] = []
  for (const id of orderedIds) {
    if (current.length > 0 && boundaries.has(id)) {
      result.push(current)
      current = []
    }
    current.push(id)
  }
  if (current.length > 0) result.push(current)
  return result
}

export function boundariesFromGroups(groups: number[][]): Set<number> {
  const set = new Set<number>()
  for (const group of groups.slice(1)) {
    if (group.length > 0) set.add(group[0]!)
  }
  return set
}

// Recomputes contiguous, 0-based group indexes for items already in their
// final order, preserving adjacent same-group runs and splitting any run
// torn apart by e.g. a reorder or delete: a new group starts whenever an
// item's group_index differs from its predecessor's, and a null/undefined
// value always starts its own new group. Mirrors the backend's
// normalize_process_groups / staged create-time resolution.
export function normalizeGroupIndexes<T extends { group_index?: number | null }>(items: T[]): T[] {
  const result: T[] = []
  let nextIndex = -1
  let prevRaw: number | null | undefined
  let isFirst = true
  for (const item of items) {
    const raw = item.group_index
    if (isFirst || raw === null || raw === undefined || raw !== prevRaw) {
      nextIndex += 1
    }
    result.push({ ...item, group_index: nextIndex })
    prevRaw = raw
    isFirst = false
  }
  return result
}
