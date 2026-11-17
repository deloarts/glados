import { webApi } from '@/core/api/webRequest'

export async function deleteCalculation(id: number): Promise<void> {
  await webApi.delete('/calculations/{calculation_id}', { path: { calculation_id: id } })
}
