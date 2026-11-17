import type { QueryOf } from '@/core/api/webRequest'

// Query parameters shared by every /production-kpi/* endpoint. machine_id
// and machine_pool_id are mutually exclusive on the backend; the store only
// ever sets one of the two.
export type ProductionKpiFilterParams = QueryOf<'/production-kpi/summary'>
