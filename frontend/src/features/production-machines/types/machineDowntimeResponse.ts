import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

export type MachineDowntimeReason = Schemas['MachineDowntimeReason']

export type MachineDowntimeResponse = Schemas['MachineDowntimeResponse']

// Denormalized onto ProductionMachineResponse.open_downtime.
export type OpenMachineDowntimeResponse = Schemas['OpenMachineDowntimeResponse']

export type MachineDowntimeCreateRequest = Schemas['MachineDowntimeCreateRequest']

export type MachineDowntimeEndRequest = Schemas['MachineDowntimeEndRequest']

export type MachineDowntimeFilterParams = QueryOf<'/production-machines/downtimes'>
export type MachineDowntimeSortBy = NonNullable<MachineDowntimeFilterParams['order_by']>
export type MachineDowntimeSortDir = NonNullable<MachineDowntimeFilterParams['order_dir']>
