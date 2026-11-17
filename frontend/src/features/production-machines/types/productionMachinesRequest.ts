import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

export type ProductionMachineFilterParams = QueryOf<'/production-machines'>
export type ProductionMachineSortBy = NonNullable<ProductionMachineFilterParams['order_by']>
export type ProductionMachineSortDir = NonNullable<ProductionMachineFilterParams['order_dir']>

export type ProductionMachineCreateRequest = Schemas['ProductionMachineCreateRequest']

export type ProductionMachineUpdateRequest = Schemas['ProductionMachineUpdateRequest']
