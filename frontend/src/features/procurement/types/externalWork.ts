import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

export type ExternalWorkRow = Schemas['ExternalWorkRowResult']
export type ExternalWorkAlert = Schemas['ExternalWorkAlert']
export type ExternalWorkQuery = QueryOf<'/external-work/'>

// How the list groups its rows: by fabrication method or by supplier.
export type ExternalWorkGroupBy = 'method' | 'supplier'

// Where a position stands with its supplier, derived from its line.
export type ExternalWorkStage = Schemas['ExternalWorkStage']
