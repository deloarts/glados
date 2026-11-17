import type { LotSummaryResponse } from '../../types/productionLotsResponse'
import type { LotStepGroup } from '../utils/lotPositionGroups'

// Column Mode's DataTable :value shape: one row per (lot, position), flattened
// from the lot list so OpenVue's rowGroupMode="rowspan" can merge the
// lot-level columns down each lot's position rows. `group: null` is a
// placeholder row for a lot with zero steps, so it doesn't disappear
// entirely from the flattened table.
export interface FlatPositionRow {
  rowKey: string
  lotId: number
  lot: LotSummaryResponse
  group: LotStepGroup | null
}
