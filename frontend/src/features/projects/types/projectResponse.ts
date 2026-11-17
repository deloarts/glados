import type { Schemas } from '@/core/api/generated'

export type ProjectStatus = Schemas['ProjectStatus']

// The web read of a project: the shared fields plus its edit version, the
// status moves and delete the reading user may take now, and its live work.
export type ProjectResponse = Schemas['ProjectWebResponse']

export type ProjectLiveWork = Schemas['ProjectLiveWorkResponse']

export type ProjectCostBySupplier = Schemas['ProjectCostBySupplier']

export type ProjectSummaryResponse = Schemas['ProjectSummaryResponse']
