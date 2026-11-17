import { webApi } from '@/core/api/webRequest'
import type { SaveTenantHolidayCommand, TenantHoliday } from '../types/holidayTypes'

export async function getTenantHolidays(): Promise<TenantHoliday[]> {
  return webApi.get('/holidays/')
}

export async function createTenantHoliday(cmd: SaveTenantHolidayCommand): Promise<TenantHoliday> {
  return webApi.post('/holidays/', { body: cmd })
}

export async function updateTenantHoliday(
  holidayId: number,
  cmd: SaveTenantHolidayCommand,
): Promise<TenantHoliday> {
  return webApi.put('/holidays/{holiday_id}', {
    path: { holiday_id: holidayId },
    body: cmd,
  })
}

export async function deleteTenantHoliday(holidayId: number): Promise<void> {
  await webApi.delete('/holidays/{holiday_id}', {
    path: { holiday_id: holidayId },
  })
}
