import type { Schemas } from '@/core/api/generated'

export type TenantHoliday = Schemas['TenantHolidayResponse']

export type SaveTenantHolidayCommand = Schemas['SaveTenantHolidayRequest']

export type HolidayCategory = TenantHoliday['category']
