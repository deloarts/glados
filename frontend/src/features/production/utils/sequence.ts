/** Anything the backend orders by a 1-based `sequence`: positions and steps. */
interface Sequenced {
  sequence: number
}

/** Comparator for `Array.prototype.sort`, ascending by `sequence`. */
export function bySequence(a: Sequenced, b: Sequenced): number {
  return a.sequence - b.sequence
}

/**
 * A sorted copy of `list` ascending by `sequence`, the original untouched.
 * A missing list gives an empty one.
 */
export function sortedBySequence<T extends Sequenced>(list: readonly T[] | null | undefined): T[] {
  return [...(list ?? [])].sort(bySequence)
}
