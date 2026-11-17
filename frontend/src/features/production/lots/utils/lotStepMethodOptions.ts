interface MethodLike {
  id: number
  archived: boolean
}

interface MethodOptionsSource<T extends MethodLike> {
  items: T[]
}

// Archived methods stay selectable, sorted after live ones.
export function methodOptions<T extends MethodLike>(store: MethodOptionsSource<T>): T[] {
  const live: T[] = []
  const archived: T[] = []
  for (const item of store.items) {
    ;(item.archived ? archived : live).push(item)
  }
  return [...live, ...archived]
}
