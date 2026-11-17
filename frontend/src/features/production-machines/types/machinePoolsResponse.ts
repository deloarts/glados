import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

export type MachinePoolResponse = Schemas['MachinePoolResponse']

export type MachinePoolFilterParams = QueryOf<'/production-machine-pools'>
export type MachinePoolSortBy = NonNullable<MachinePoolFilterParams['order_by']>
export type MachinePoolSortDir = NonNullable<MachinePoolFilterParams['order_dir']>

export type MachinePoolCreateRequest = Schemas['MachinePoolCreateRequest']

export type MachinePoolUpdateRequest = Schemas['MachinePoolUpdateRequest']
