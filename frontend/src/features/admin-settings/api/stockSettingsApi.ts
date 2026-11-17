import { webApi } from '@/core/api/webRequest'
import type {
  AdminStockSettings,
  StockServiceTestResult,
  UpdateStockSettingsCommand,
  VerifyStockServiceCommand,
} from '../types/adminSettingsTypes'

export async function getStockSettings(): Promise<AdminStockSettings> {
  return webApi.get('/admin/settings/stock')
}

export async function updateStockSettings(
  cmd: UpdateStockSettingsCommand,
): Promise<AdminStockSettings> {
  return webApi.put('/admin/settings/stock', { body: cmd })
}

/**
 * Tests the given, possibly unsaved, stock service: its version and
 * contract, and the system behind it. Stores nothing.
 */
export async function testStockService(
  cmd: VerifyStockServiceCommand,
): Promise<StockServiceTestResult> {
  return webApi.post('/admin/settings/stock/test', { body: cmd })
}
