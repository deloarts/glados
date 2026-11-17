/**
 * Where a dragged row of a hand-ordered list lands: directly after one
 * neighbour, or directly before one when it was dropped at the top of the
 * page. Neither puts it first.
 */
export interface ListPlaceTarget {
  after_id?: number | null
  before_id?: number | null
}
