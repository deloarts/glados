import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

export type PrinterKind = Schemas['PrinterKind']
export type PrinterTransport = Schemas['PrinterTransport']

export type PrinterFilterParams = QueryOf<'/printers'>
export type PrinterSortBy = NonNullable<PrinterFilterParams['order_by']>
export type PrinterSortDir = NonNullable<PrinterFilterParams['order_dir']>

export type PrinterCreateRequest = Schemas['PrinterCreateRequest']

export type PrinterUpdateRequest = Schemas['PrinterUpdateRequest']
